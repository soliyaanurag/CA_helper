#!/usr/bin/env bash
# CA Helper developer setup:  make setup  (or: bash scripts/setup_dev.sh)
# Safe to re-run. Linux / WSL2 and macOS.
#
#   1. create or update the `ca-helper` conda env (Python 3.12, Node 22, pip packages)
#   2. install the frontend's npm packages with the env's Node
#   3. create .env from .env.example with random secrets (an existing .env is kept)

set -euo pipefail
cd "$(dirname "$0")/.."

ENV_NAME="ca-helper"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda was not found. Install Miniforge, open a new terminal, then run 'make setup' again:"
  echo '  curl -fLO "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"'
  echo '  bash "Miniforge3-$(uname)-$(uname -m).sh"'
  exit 1
fi

echo "==> Conda env '$ENV_NAME'"
if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  conda env update -n "$ENV_NAME" -f environment.yml --prune
else
  conda env create -f environment.yml
fi
# VS Code finds the env through this link (.vscode/settings.json; gitignored).
ln -sfn "$(conda run -n "$ENV_NAME" python -c 'import sys; print(sys.prefix)')" .conda-env

echo "==> npm packages"
conda run --no-capture-output -n "$ENV_NAME" --cwd frontend npm ci

echo "==> .env"
if [ -f .env ]; then
  echo ".env already exists; left unchanged."
else
  # Python (not sed) so it works the same on Linux and macOS.
  conda run -n "$ENV_NAME" python -c '
import re, secrets
from pathlib import Path

text = Path(".env.example").read_text()
for key in ("SECRET_KEY", "JWT_SECRET_KEY"):
    text = re.sub(rf"^{key}=.*$", f"{key}={secrets.token_urlsafe(48)}", text, flags=re.M)
Path(".env").write_text(text)
'
  echo "Created .env with random secrets."
fi

echo
echo "Done. Next: make infra, make migrate, make seed, then make dev-backend and make dev-frontend."
