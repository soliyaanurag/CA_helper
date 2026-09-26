#!/usr/bin/env bash
# CA Helper developer setup:  make setup  (safe to re-run)
#
#   1. check that conda is installed (if not: print how to install it, then stop)
#   2. create or update the `ca-helper` conda env (Python, Tesseract, Node, pip packages)
#   3. install the frontend's npm packages with the env's Node
#   4. create .env from .env.example with random dev secrets (only if .env is missing)
#   5. generate the frontend API types (make gen-api)
#
# Works on Linux / WSL2 and macOS (bash 3.2 compatible).

set -euo pipefail
cd "$(dirname "$0")/.."
ENV_NAME="ca-helper"

echo "==> 1/5 Checking conda"
if ! command -v conda >/dev/null 2>&1; then
  echo "conda was not found. Install Miniforge, restart your terminal, then re-run 'make setup':"
  echo '  curl -fLO "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"'
  echo '  bash "Miniforge3-$(uname)-$(uname -m).sh"'
  exit 1
fi
conda --version

echo "==> 2/5 Creating / updating conda env '$ENV_NAME' (first run takes a few minutes)"
if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  conda env update -n "$ENV_NAME" -f environment.yml --prune
else
  conda env create -f environment.yml
fi
# Stable path for VS Code (.vscode/settings.json): .conda-env -> the env (gitignored).
ln -sfn "$(conda run -n "$ENV_NAME" python -c 'import sys; print(sys.prefix)')" .conda-env

echo "==> 3/5 Installing frontend packages"
conda run --no-capture-output -n "$ENV_NAME" --cwd frontend npm ci

echo "==> 4/5 Checking .env"
if [ -f .env ]; then
  echo ".env already exists; leaving it unchanged"
else
  cp .env.example .env
  # Replace the `change-me` placeholders with random values. (`conda run` does not
  # forward stdin, so the script is passed with -c.)
  conda run -n "$ENV_NAME" python -c '
import re, secrets
from pathlib import Path
env = Path(".env")
text = env.read_text()
for key in ("SECRET_KEY", "JWT_SECRET_KEY"):
    text = re.sub(rf"^{key}=.*$", f"{key}={secrets.token_urlsafe(48)}", text, flags=re.M)
env.write_text(text)
'
  echo "Created .env with random development secrets"
fi

echo "==> 5/5 Generating frontend API types"
make gen-api

command -v docker >/dev/null 2>&1 || echo "WARNING: Docker not found; 'make infra' needs it (see README)."
echo
echo "Setup done. Next:"
echo "  make infra         # start Postgres + Mailpit (Docker)"
echo "  make migrate       # apply database migrations"
echo "  make seed          # demo users"
echo "  make dev-backend   # API on http://localhost:8000 (docs: /api/docs)"
echo "  make dev-frontend  # app on http://localhost:5173"
