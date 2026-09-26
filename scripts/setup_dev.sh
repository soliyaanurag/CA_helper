#!/usr/bin/env bash
# =============================================================================
# CA Helper one-command developer setup:  make setup  (or: bash scripts/setup_dev.sh)
#
# Safe to re-run (idempotent). It asks before installing anything system-level.
# Works on Linux / WSL2 and macOS (Intel + Apple Silicon), including macOS's
# default bash 3.2: no bash-4 features and no GNU-only flags on purpose.
#
# Steps:
#   1. detect OS / architecture            6. npm ci in frontend/ (env's Node)
#   2. find conda (or offer Miniforge)     7. create .env with random dev secrets
#   3. create / update the conda env       8. install git pre-commit hooks
#   4. verify Python 3.12, Tesseract and   then print a checklist
#      Node 22.22+ inside the env
#   5. check Docker and git
#
# Node.js comes from the conda env (environment.yml), like Python. Every node/npm
# command below runs through `conda run -n ca-helper`; no system Node is needed.
#
# Options:  -y / --yes   answer "yes" to confirmation prompts (non-interactive)
# =============================================================================

set -u

ENV_NAME="ca-helper"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

# ---- output helpers ----------------------------------------------------------
CHECKLIST=""
step()  { printf '\n\033[1;34m==> %s\033[0m\n' "$1"; }
info()  { printf '    %s\n' "$1"; }
warn()  { printf '    \033[33mWARNING: %s\033[0m\n' "$1"; }
ok_item()   { CHECKLIST="${CHECKLIST}✅ $1
"; }
warn_item() { CHECKLIST="${CHECKLIST}⚠️  $1
"; }

confirm() {
  # confirm "question" -> returns 0 for yes
  if [ "$ASSUME_YES" -eq 1 ]; then return 0; fi
  if [ ! -t 0 ]; then
    warn "Not an interactive terminal; re-run with --yes to allow this step."
    return 1
  fi
  printf '    %s [y/N] ' "$1"
  read -r answer
  case "$answer" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

# =============================================================================
# 1. OS and architecture
# =============================================================================
step "1/8 Detecting operating system"
OS_NAME="$(uname -s)"
ARCH="$(uname -m)"
IS_WSL=0
case "$OS_NAME" in
  Linux)
    if grep -qi microsoft /proc/version 2>/dev/null; then IS_WSL=1; fi
    ;;
  Darwin) ;;
  MINGW*|MSYS*|CYGWIN*)
    echo "Native Windows is not supported. Use WSL2:"
    echo "  1. In PowerShell (as Administrator): wsl --install -d Ubuntu"
    echo "  2. Open Ubuntu, then clone the repo INSIDE Linux, e.g. ~/projects/ca-helper"
    echo "  3. Run 'make setup' there."
    exit 1
    ;;
  *) warn "Unrecognised OS '$OS_NAME'; continuing as if it were Linux." ;;
esac

if [ "$IS_WSL" -eq 1 ]; then
  info "Linux on WSL2 ($ARCH)"
  case "$REPO_ROOT" in
    /mnt/*)
      warn "The repo is under $REPO_ROOT (the Windows filesystem). This is very slow and"
      warn "breaks file watching. Clone it inside Linux instead, e.g. ~/projects/ca-helper"
      warn_item "Repo location: under /mnt/ (move it into the Linux filesystem)"
      ;;
    *) ok_item "Repo location: Linux filesystem ($REPO_ROOT)" ;;
  esac
elif [ "$OS_NAME" = "Darwin" ]; then
  info "macOS ($ARCH)"
else
  info "Linux ($ARCH)"
fi

# =============================================================================
# 2. conda (Miniforge / Miniconda / Anaconda)
# =============================================================================
step "2/8 Looking for conda"
CONDA_BIN=""
find_conda() {
  if [ -n "${CONDA_EXE:-}" ] && [ -x "${CONDA_EXE}" ]; then CONDA_BIN="$CONDA_EXE"; return 0; fi
  if command -v conda >/dev/null 2>&1; then CONDA_BIN="$(command -v conda)"; return 0; fi
  for dir in "$HOME/miniforge3" "$HOME/mambaforge" "$HOME/miniconda3" "$HOME/anaconda3" \
             "/opt/homebrew/Caskroom/miniforge/base" "/usr/local/Caskroom/miniforge/base" \
             "/opt/miniforge3" "/opt/miniconda3" "/opt/anaconda3"; do
    if [ -x "$dir/condabin/conda" ]; then CONDA_BIN="$dir/condabin/conda"; return 0; fi
    if [ -x "$dir/bin/conda" ]; then CONDA_BIN="$dir/bin/conda"; return 0; fi
  done
  return 1
}

CONDA_JUST_INSTALLED=0
if find_conda; then
  info "Found $("$CONDA_BIN" --version) at $CONDA_BIN"
  ok_item "conda: $("$CONDA_BIN" --version) ($CONDA_BIN)"
else
  INSTALLER="Miniforge3-${OS_NAME}-${ARCH}.sh"
  URL="https://github.com/conda-forge/miniforge/releases/latest/download/${INSTALLER}"
  info "conda was not found. I can install Miniforge (conda-forge's official, free distribution):"
  info "  download: $URL"
  info "  install to: $HOME/miniforge3   (your home folder only, no sudo)"
  info "  then run 'conda init' for your shell ($(basename "${SHELL:-bash}"))"
  if confirm "Install Miniforge now?"; then
    TMP_INSTALLER="$(mktemp -t miniforge.XXXXXX)" || exit 1
    if curl -fL -o "$TMP_INSTALLER" "$URL" && bash "$TMP_INSTALLER" -b -p "$HOME/miniforge3"; then
      rm -f "$TMP_INSTALLER"
      CONDA_BIN="$HOME/miniforge3/bin/conda"
      SHELL_NAME="$(basename "${SHELL:-bash}")"
      "$CONDA_BIN" init "$SHELL_NAME"
      CONDA_JUST_INSTALLED=1
      ok_item "conda: Miniforge installed to $HOME/miniforge3"
    else
      rm -f "$TMP_INSTALLER"
      echo "Miniforge installation failed. Install it manually from https://conda-forge.org/download/"
      exit 1
    fi
  else
    echo "conda is required. Install Miniforge from https://conda-forge.org/download/ and re-run 'make setup'."
    exit 1
  fi
fi

# =============================================================================
# 3. Create or update the ca-helper env
# =============================================================================
step "3/8 Creating / updating conda env '$ENV_NAME' (first run takes a few minutes)"
if "$CONDA_BIN" env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  info "Env exists; syncing it with environment.yml"
  "$CONDA_BIN" env update -n "$ENV_NAME" -f environment.yml --prune
else
  "$CONDA_BIN" env create -f environment.yml
fi
if [ $? -eq 0 ]; then ok_item "conda env '$ENV_NAME' up to date"; else warn_item "conda env '$ENV_NAME' create/update FAILED (see output above)"; fi

# =============================================================================
# 4. Verify the env
# =============================================================================
step "4/8 Verifying the env (Python, Tesseract, Node)"
PY_VERSION="$("$CONDA_BIN" run -n "$ENV_NAME" python --version 2>&1)"
case "$PY_VERSION" in
  "Python 3.12."*) info "$PY_VERSION"; ok_item "Python: $PY_VERSION" ;;
  *) warn "Expected Python 3.12.x, got: $PY_VERSION"; warn_item "Python 3.12 not available in env" ;;
esac
TESS_VERSION="$("$CONDA_BIN" run -n "$ENV_NAME" tesseract --version 2>&1 | head -n 1)"
case "$TESS_VERSION" in
  tesseract*) info "$TESS_VERSION"; ok_item "Tesseract: $TESS_VERSION" ;;
  *) warn "tesseract not working in env: $TESS_VERSION"; warn_item "Tesseract missing in env" ;;
esac

NODE_OK=0
NODE_VERSION="$("$CONDA_BIN" run -n "$ENV_NAME" node --version 2>/dev/null)"   # e.g. v22.23.2
case "$NODE_VERSION" in
  v*)
    NODE_MAJOR="$(echo "$NODE_VERSION" | sed 's/^v//' | cut -d. -f1)"
    NODE_MINOR="$(echo "$NODE_VERSION" | sed 's/^v//' | cut -d. -f2)"
    if [ "$NODE_MAJOR" -gt 22 ] || { [ "$NODE_MAJOR" -eq 22 ] && [ "$NODE_MINOR" -ge 22 ]; }; then
      info "Node $NODE_VERSION, npm $("$CONDA_BIN" run -n "$ENV_NAME" npm --version 2>/dev/null)"
      ok_item "Node.js: $NODE_VERSION (conda env)"
      NODE_OK=1
    else
      warn "Node $NODE_VERSION in the env is too old; the frontend needs 22.22+. Run: make env-update"
      warn_item "Node.js in env too old ($NODE_VERSION); need 22.22+"
    fi
    ;;
  *) warn "node not found in env '$ENV_NAME'. Run: make env-update"; warn_item "Node.js missing in env" ;;
esac

# Stable path for VS Code: .conda-env -> <your env prefix> (gitignored).
ENV_PREFIX="$("$CONDA_BIN" run -n "$ENV_NAME" python -c 'import sys; print(sys.prefix)' 2>/dev/null)"
if [ -n "$ENV_PREFIX" ] && [ -d "$ENV_PREFIX" ]; then
  ln -sfn "$ENV_PREFIX" "$REPO_ROOT/.conda-env"
  info "VS Code interpreter link: .conda-env -> $ENV_PREFIX"
fi

# =============================================================================
# 5. Docker, Node, git (never auto-installed)
# =============================================================================
step "5/8 Checking Docker and git"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  DOCKER_INFO="$(docker info 2>&1)"
  if [ $? -eq 0 ]; then
    info "$(docker --version); $(docker compose version)"
    ok_item "Docker + Compose running"
  elif echo "$DOCKER_INFO" | grep -qi "permission denied"; then
    warn "Docker is running but this terminal may not use it (permission denied)."
    warn "Open a NEW terminal (you were probably just added to the 'docker' group)."
    if [ "$IS_WSL" -eq 1 ]; then warn "If that does not help: run 'wsl --shutdown' in PowerShell, then reopen Ubuntu."; fi
    warn_item "Docker permission denied (open a new terminal)"
  else
    warn "Docker is installed but the daemon is not running. Start Docker Desktop."
    warn_item "Docker installed but not running"
  fi
else
  warn "Docker with the Compose plugin was not found."
  if [ "$IS_WSL" -eq 1 ]; then
    info "Install Docker Desktop for Windows: https://docs.docker.com/desktop/setup/install/windows-install/"
    info "Then: Docker Desktop > Settings > Resources > WSL integration > enable your Ubuntu distro."
  elif [ "$OS_NAME" = "Darwin" ]; then
    info "Install Docker Desktop for Mac: https://docs.docker.com/desktop/setup/install/mac-install/"
  else
    info "Install Docker Engine + Compose plugin: https://docs.docker.com/engine/install/"
  fi
  warn_item "Docker not installed (needed for make infra / make up)"
fi

if command -v git >/dev/null 2>&1; then
  ok_item "git: $(git --version)"
else
  if [ "$OS_NAME" = "Darwin" ]; then
    info "Install Apple's command line tools (git + make): xcode-select --install"
  else
    info "Install git: sudo apt install git"
  fi
  warn_item "git not installed"
fi
if ! command -v make >/dev/null 2>&1; then
  if [ "$OS_NAME" = "Darwin" ]; then info "Install make: xcode-select --install"; else info "Install make: sudo apt install make"; fi
  warn_item "make not installed"
fi

# =============================================================================
# 6. Frontend packages
# =============================================================================
step "6/8 Installing frontend packages"
if [ "$NODE_OK" -eq 1 ]; then
  if [ -f frontend/package-lock.json ]; then
    "$CONDA_BIN" run --no-capture-output -n "$ENV_NAME" --cwd frontend npm ci
  else
    "$CONDA_BIN" run --no-capture-output -n "$ENV_NAME" --cwd frontend npm install
  fi
  if [ $? -eq 0 ]; then ok_item "npm packages installed"; else warn_item "npm install FAILED (see output above)"; fi
else
  warn "Skipped: needs Node.js 22.22+ in the conda env"
  warn_item "npm packages NOT installed (fix the env, then re-run make setup)"
fi

# =============================================================================
# 7. .env
# =============================================================================
step "7/8 Checking .env"
if [ -f .env ]; then
  info ".env already exists; leaving it unchanged"
  ok_item ".env present"
else
  cp .env.example .env
  # Fill in random development secrets. Python keeps this portable (no `sed -i`);
  # the script is passed with -c because `conda run` does not forward stdin.
  # (`read -d ''` returns non-zero at end of input; that is expected.)
  read -r -d '' FILL_SECRETS <<'PY'
import re
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

path = Path(".env")
text = path.read_text()
values = {
    "SECRET_KEY": secrets.token_urlsafe(48),
    "JWT_SECRET_KEY": secrets.token_urlsafe(48),
    "FIELD_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "BLIND_INDEX_KEY": secrets.token_hex(32),
}
for key, value in values.items():
    text = re.sub(rf"^{key}=.*$", f"{key}={value}", text, flags=re.MULTILINE)
path.write_text(text)
PY
  if "$CONDA_BIN" run -n "$ENV_NAME" python -c "$FILL_SECRETS"; then
    info "Created .env with random development secrets."
  else
    warn "Could not generate secrets; edit SECRET_KEY etc. in .env by hand."
  fi
  ok_item ".env created from .env.example"
fi
if grep -q '^GEMINI_API_KEY=$' .env; then
  warn "Add your own GEMINI_API_KEY to .env (https://aistudio.google.com/apikey); needed for the AI features."
  warn_item "GEMINI_API_KEY is empty in .env"
fi

# =============================================================================
# 8. Git hooks
# =============================================================================
step "8/8 Installing pre-commit git hooks"
if "$CONDA_BIN" run -n "$ENV_NAME" pre-commit install; then
  ok_item "pre-commit hooks installed"
else
  warn_item "pre-commit install FAILED"
fi

printf '\n\033[1m================ Setup summary ================\033[0m\n'
printf '%s' "$CHECKLIST"
echo
if [ "$CONDA_JUST_INSTALLED" -eq 1 ]; then
  echo "Miniforge was just installed: restart your terminal and VS Code so 'conda' is on PATH."
fi
echo "Next steps:"
echo "  make infra         # start Postgres + Mailpit (Docker)"
echo "  make migrate       # apply database migrations"
echo "  make dev-backend   # API on http://localhost:8000 (docs: /api/docs)"
echo "  make dev-frontend  # app on http://localhost:5173"
echo "  make test          # run all tests"
