#!/usr/bin/env bash
# Team git workflow, one command per step. Run it through make (`make help`):
#
#   make feature branch=anurag/documents-ack-upload   start a task: latest main, set up, new branch
#   make sync                                         after a pull (or any time): make this machine match the code
#   make check                                        before pushing: lint, tests, frontend build, migrations
#   make pr                                           check, push the branch, open (or update) its pull request
#   make merge                                        squash-merge the approved, green pull request, then sync main
#
# Every step stops at the first problem and never throws work away: it refuses to switch
# branches with uncommitted changes, pulls only fast-forward and never force-pushes.
# Linux / WSL2 and macOS.

set -euo pipefail
cd "$(dirname "$0")/.."

ENV_NAME="ca-helper"
RUN="conda run --no-capture-output -n $ENV_NAME"
# Fingerprints of the dependency files at the last install. They live inside .git/, so they
# belong to this machine and are never committed.
PY_STAMP=".git/ca-helper-python-deps"
NPM_STAMP=".git/ca-helper-npm-deps"

step() { printf '\n==> %s\n' "$*"; }
fail() {
  echo "ERROR: $*" >&2
  exit 1
}

# A fingerprint of some files' contents (git's hash works the same on Linux and macOS).
fingerprint() { cat "$@" | git hash-object --stdin; }

current_branch() { git branch --show-current; }

require_clean_tree() {
  if [ -n "$(git status --porcelain)" ]; then
    git status --short
    fail "You have uncommitted changes. Commit them (or 'git stash') first."
  fi
}

require_docker() {
  docker info >/dev/null 2>&1 ||
    fail "Docker is not running. Start Docker Desktop (on Windows with WSL integration on), then run this again."
}

# --- sync: make this machine match the checked-out code ------------------------------

sync() {
  local restart=0

  step "Code"
  git fetch origin --prune
  if [ "$(current_branch)" = "main" ]; then
    git pull --ff-only # refuses (and changes nothing) if your local main has its own commits
  else
    local behind
    behind=$(git rev-list --count HEAD..origin/main)
    if [ "$behind" -gt 0 ]; then
      echo "Your branch is $behind commit(s) behind main. To bring them in: git rebase origin/main"
    else
      echo "Your branch has everything from main."
    fi
  fi

  step "Python packages (conda env '$ENV_NAME')"
  conda env list | awk '{print $1}' | grep -qx "$ENV_NAME" || fail "No conda env '$ENV_NAME'. Run: make setup"
  local py_now
  py_now=$(fingerprint environment.yml backend/requirements.txt backend/requirements-dev.txt)
  if [ "$(cat "$PY_STAMP" 2>/dev/null)" != "$py_now" ]; then
    # Without a fingerprint (first run on this machine) this only confirms the env.
    [ -f "$PY_STAMP" ] && restart=1
    conda env update -n "$ENV_NAME" -f environment.yml --prune
    echo "$py_now" >"$PY_STAMP"
  else
    echo "Up to date."
  fi

  step "npm packages"
  local npm_now
  npm_now=$(fingerprint frontend/package-lock.json)
  if [ ! -d frontend/node_modules ]; then
    $RUN --cwd frontend npm ci
    restart=1
  elif [ ! -f "$NPM_STAMP" ] && $RUN --cwd frontend npm ls >/dev/null 2>&1; then
    echo "Up to date." # first run on this machine: what is installed already fits
  elif [ "$(cat "$NPM_STAMP" 2>/dev/null)" != "$npm_now" ]; then
    $RUN --cwd frontend npm ci
    restart=1
  else
    echo "Up to date."
  fi
  echo "$npm_now" >"$NPM_STAMP"

  step ".env"
  [ -f .env ] || fail ".env is missing. Run: make setup"
  local missing
  missing=$(grep -oE '^[A-Z][A-Z0-9_]*=' .env.example | tr -d '=' | while read -r name; do
    grep -qE "^${name}=" .env || echo "$name"
  done)
  if [ -n "$missing" ]; then
    echo "WARNING: your .env lacks these variables from .env.example. Copy them over (with their comments):"
    echo "$missing" | sed 's/^/  /'
  else
    echo "Has every variable from .env.example."
  fi

  step "Postgres + Mailpit"
  require_docker
  make --no-print-directory -s infra

  step "Database"
  make --no-print-directory -s migrate
  make --no-print-directory -s seed

  echo
  if [ "$restart" -eq 1 ]; then
    echo "Synced. Packages changed: restart make dev-backend, dev-worker and dev-frontend if they are running."
  else
    echo "Synced. Running servers reload code changes by themselves."
  fi
}

# --- feature: start a new task on its own branch ---------------------------------------

feature() {
  local branch="${1:-}"
  [[ "$branch" =~ ^[a-z0-9]+/[a-z0-9][a-z0-9_-]*$ ]] ||
    fail "Usage: make feature branch=<name>/<module>-<short-task>   e.g. anurag/documents-ack-upload"
  require_clean_tree
  git fetch origin --prune
  if git show-ref --quiet "refs/heads/$branch"; then
    fail "Branch $branch already exists. To continue it: git switch $branch && git rebase origin/main"
  fi

  git switch main
  sync
  step "New branch"
  git switch -c "$branch"
  echo "On $branch. Build the feature (docs/PATTERNS.md), commit, then: make pr"
}

# --- check: everything CI checks, plus migrations ---------------------------------------

check() {
  step "Lint and format"
  make --no-print-directory -s lint

  step "Migrations"
  require_docker
  make --no-print-directory -s migrate
  local heads
  heads=$($RUN --cwd backend flask --app app db heads 2>/dev/null | grep -c "(head)" || true)
  [ "$heads" -eq 1 ] ||
    fail "Alembic has $heads heads (two branches each added a migration). Fix it with:
  conda run -n $ENV_NAME --cwd backend flask --app app db merge heads -m \"merge\""
  $RUN --cwd backend flask --app app db check ||
    fail "The models changed but no migration covers it. Create one: make migration name=\"<module>: <what changed>\""

  step "Tests"
  make --no-print-directory -s test

  step "Frontend build"
  $RUN --cwd frontend npm run build

  printf '\nAll checks passed.\n'
}

# --- pr: push the branch and open its pull request ---------------------------------------

pr() {
  local branch
  branch=$(current_branch)
  [ -n "$branch" ] && [ "$branch" != "main" ] || fail "Switch to your feature branch first. Nobody pushes to main."
  require_clean_tree
  git fetch origin --prune
  git merge-base --is-ancestor origin/main HEAD ||
    fail "main has new commits since you branched. Bring them in first: git rebase origin/main"
  [ "$(git rev-list --count origin/main..HEAD)" -gt 0 ] || fail "Nothing to send: this branch has no commits beyond main."

  check

  step "Push"
  git push -u origin HEAD ||
    fail "GitHub refused the push. If you rebased this branch and nobody else uses it: git push --force-with-lease, then make pr again."

  step "Pull request"
  if [ "$(gh pr view --json state --jq .state 2>/dev/null || true)" = "OPEN" ]; then
    echo "Updated: $(gh pr view --json url --jq .url)"
  else
    gh pr create --base main --head "$branch" \
      --title "$(git log --reverse --format=%s origin/main..HEAD | head -1)" \
      --body-file .github/pull_request_template.md
    echo "Now fill in the template on GitHub (summary and ticks) and ask a teammate to review."
  fi
}

# --- merge: squash-merge an approved, green pull request ---------------------------------

merge() {
  local branch state approvals
  branch=$(current_branch)
  [ -n "$branch" ] && [ "$branch" != "main" ] || fail "Run this on the feature branch whose pull request you want to merge."
  require_clean_tree
  state=$(gh pr view --json state --jq .state 2>/dev/null) || fail "This branch has no pull request yet. Run: make pr"
  [ "$state" = "OPEN" ] || fail "This branch's pull request is $state, not open."
  git fetch origin --prune
  [ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$branch" 2>/dev/null)" ] ||
    fail "Your branch differs from the one on GitHub. Run make pr first."

  step "CI"
  gh pr checks || fail "CI is not green (failed or still running). Wait for it, or fix it and run make pr."

  step "Review"
  approvals=$(gh pr view --json reviews --jq '[.reviews[] | select(.state == "APPROVED")] | length')
  [ "$approvals" -gt 0 ] || fail "No teammate has approved this pull request yet. Ask for a review on GitHub."

  step "Squash-merge"
  gh pr merge --squash --delete-branch
  git switch main
  sync
}

case "${1:-}" in
sync) sync ;;
feature) feature "${2:-}" ;;
check) check ;;
pr) pr ;;
merge) merge ;;
*) fail "Usage: bash scripts/workflow.sh sync | feature <branch> | check | pr | merge (or the make targets)" ;;
esac
