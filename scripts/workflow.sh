#!/usr/bin/env bash
# Team workflow, one command per step. Run it through make (README "Team workflow"):
#
#   make doctor                                       check this machine and say how to fix each problem
#   make feature branch=anurag/documents-ack-upload   start a task: latest main, sync, new branch
#   make sync                                         after a pull (or any time): make this machine match the code
#   make check                                        before pushing: lint, migrations, tests, frontend build
#   make pr                                           check, push the branch, open (or update) its pull request
#   make merge                                        squash-merge the approved, green pull request, then sync main
#
# Safety: it never force-pushes, pulls only fast-forward, refuses to switch branches with
# uncommitted changes and never edits .env. Every failure says which step failed and how to
# fix it. Only `doctor` changes nothing at all. Linux / WSL2 and macOS.

set -Eeuo pipefail
cd "$(dirname "$0")/.."

ENV_NAME="ca-helper"
RUN="conda run --no-capture-output -n $ENV_NAME"
FLASK="$RUN --cwd backend flask --app app"
# Fingerprints of the dependency files at the last install. They live inside .git/, so they
# belong to this machine and are never committed.
PY_STAMP=".git/ca-helper-python-deps"
NPM_STAMP=".git/ca-helper-npm-deps"
PY_DEP_FILES="environment.yml backend/requirements.txt backend/requirements-dev.txt"
NPM_DEP_FILE="frontend/package-lock.json"

STEP="start"
step() {
  STEP="$*"
  printf '\n==> %s\n' "$*"
}

fail() {
  printf '\nERROR in step "%s":\n%s\n' "$STEP" "$*" >&2
  exit 1
}

# Anything that fails without its own message above lands here.
trap 'printf "\nERROR in step \"%s\": the command above failed (line %s).\nRead its output, fix the cause, then run the same make command again. make doctor checks the whole setup.\n" "$STEP" "$LINENO" >&2' ERR

# A fingerprint of some files' contents (git's hash works the same on Linux and macOS).
fingerprint() { cat "$@" | git hash-object --stdin; }

current_branch() { git branch --show-current; }

require_clean_tree() {
  if [ -n "$(git status --porcelain)" ]; then
    git status --short >&2
    fail "You have uncommitted changes (listed above). Commit them, or put them aside with 'git stash', then run this again."
  fi
}

require_conda_env() {
  command -v conda >/dev/null 2>&1 || fail "conda was not found. Install Miniforge and run 'make setup' (README \"Setup\")."
  conda env list | awk '{print $1}' | grep -qx "$ENV_NAME" || fail "The conda env '$ENV_NAME' does not exist. Run: make setup"
}

require_docker() {
  docker info >/dev/null 2>&1 ||
    fail "Docker is not running, so Postgres and Mailpit are down.
Start Docker Desktop (on Windows: with WSL integration on for this distro), wait until it says it is running, then run this again."
}

require_gh() {
  command -v gh >/dev/null 2>&1 ||
    fail "The GitHub CLI (gh) is not installed. Install it (Ubuntu/WSL: sudo apt install gh; macOS: brew install gh), then: gh auth login"
  gh auth status >/dev/null 2>&1 || fail "The GitHub CLI is not logged in. Run: gh auth login"
}

fetch_origin() {
  git fetch origin --prune --quiet ||
    fail "Cannot reach GitHub (no internet, or no access to the repository). Check your connection and try again."
}

# The names of variables in .env.example that .env does not set.
missing_env_vars() {
  grep -oE '^[A-Z][A-Z0-9_]*=' .env.example | tr -d '=' | while read -r name; do
    grep -qE "^${name}=" .env || echo "$name"
  done
}

# Run a make target quietly; on failure show its output and a fix for the usual causes.
make_step() {
  local target="$1" output
  if output=$(make --no-print-directory -s "$target" 2>&1); then
    printf '%s\n' "$output" | grep -vE '^INFO +\[alembic' || true
    return 0
  fi
  printf '%s\n' "$output" >&2
  if grep -q "Can't locate revision" <<<"$output"; then
    fail "The database has a migration that this code does not know. It usually came from main while you are on an
older branch. Fix: git rebase origin/main, then make sync. (On main: git pull, then make sync.)"
  elif grep -qiE "connection refused|could not connect|connection failed" <<<"$output"; then
    fail "Cannot connect to Postgres. Run make infra (Docker Desktop must be running), then try again."
  elif grep -qiE "port is already allocated|address already in use" <<<"$output"; then
    fail "A port Docker needs is taken (5432 Postgres, 1025/8025 Mailpit). Stop the other program using it, or change
DB_HOST_PORT (and the URLs) in .env, then run this again."
  fi
  fail "'make $target' failed (output above)."
}

# --- sync: make this machine match the checked-out code ------------------------------

sync() {
  local restart=0 branch
  branch=$(current_branch)

  step "Code"
  fetch_origin
  if [ "$branch" = "main" ]; then
    local ahead
    ahead=$(git rev-list --count origin/main..main)
    if [ "$ahead" -gt 0 ]; then
      fail "Your local main has $ahead commit(s) that are not on GitHub. main only changes through pull requests.
Keep them on a branch, then reset main to GitHub's:
  git branch <name>/<module>-<task>    # the commits are now safe on this branch
  git reset --hard origin/main         # (only after the line above)
then: git switch <name>/<module>-<task> && make pr"
    fi
    git pull --ff-only --quiet ||
      fail "git could not update main (see above). Usually uncommitted changes touch the same files: commit or 'git stash' them, then run make sync again."
    echo "main is up to date with GitHub ($(git log -1 --format='%h %s'))."
  elif [ -z "$branch" ]; then
    echo "You are not on a branch (detached HEAD). Syncing the checked-out code as it is."
  else
    local behind
    behind=$(git rev-list --count HEAD..origin/main)
    if [ "$behind" -gt 0 ]; then
      echo "NOTE: $branch is $behind commit(s) behind main. To bring them in: git rebase origin/main (then make sync)."
    else
      echo "$branch has everything from main."
    fi
  fi

  step "Python packages (conda env '$ENV_NAME')"
  require_conda_env
  local py_now
  # shellcheck disable=SC2086
  py_now=$(fingerprint $PY_DEP_FILES)
  if [ "$(cat "$PY_STAMP" 2>/dev/null)" != "$py_now" ]; then
    # Without a fingerprint (first run on this machine) this only confirms the env.
    if [ -f "$PY_STAMP" ]; then
      restart=1
      echo "Dependency files changed: updating the env."
    else
      echo "First sync on this machine: checking the env once."
    fi
    conda env update -n "$ENV_NAME" -f environment.yml --prune >/dev/null ||
      fail "Updating the conda env failed (see above). Check your connection, then run make sync again."
    echo "$py_now" >"$PY_STAMP"
    echo "Done."
  else
    echo "Up to date."
  fi

  step "npm packages"
  local npm_now npm_needed=0
  npm_now=$(fingerprint "$NPM_DEP_FILE")
  if [ ! -d frontend/node_modules ]; then
    npm_needed=1
  elif [ ! -f "$NPM_STAMP" ]; then
    # First sync on this machine: reinstall only if what is installed does not fit package.json.
    $RUN --cwd frontend npm ls >/dev/null 2>&1 || npm_needed=1
  elif [ "$(cat "$NPM_STAMP")" != "$npm_now" ]; then
    npm_needed=1
  fi
  if [ "$npm_needed" -eq 1 ]; then
    echo "Installing (the Vite dev server must be restarted afterwards)."
    $RUN --cwd frontend npm ci --no-audit --no-fund ||
      fail "npm ci failed (see above). Check your connection, then run make sync again."
    restart=1
  else
    echo "Up to date."
  fi
  echo "$npm_now" >"$NPM_STAMP"

  step ".env"
  [ -f .env ] || fail ".env is missing. Run: make setup (it creates .env with random secrets)."
  local missing
  missing=$(missing_env_vars)
  if [ -n "$missing" ]; then
    echo "WARNING: your .env lacks these variables from .env.example. Copy each line (with its comment) from"
    echo ".env.example into .env; the app uses a default until you do:"
    echo "$missing" | sed 's/^/  /'
  else
    echo "Has every variable from .env.example."
  fi

  step "Postgres + Mailpit"
  require_docker
  make_step infra

  step "Database migrations"
  make_step migrate

  step "Seed data"
  make_step seed

  echo
  if [ "$restart" -eq 1 ]; then
    echo "Synced. Packages changed: restart make dev-backend, make dev-worker and make dev-frontend if they are running."
  else
    echo "Synced. Running dev servers reload code changes by themselves."
  fi
}

# --- feature: start a new task on its own branch ---------------------------------------

feature() {
  local branch="${1:-}"
  step "New branch name"
  [[ "$branch" =~ ^[a-z0-9]+/[a-z0-9][a-z0-9_-]*$ ]] ||
    fail "Give a branch name <name>/<module>-<short-task> in lowercase, e.g.:
  make feature branch=anurag/documents-ack-upload"
  require_clean_tree
  fetch_origin
  if git show-ref --quiet "refs/heads/$branch"; then
    fail "Branch $branch already exists here. To continue it: git switch $branch && git rebase origin/main && make sync"
  fi
  if git show-ref --quiet "refs/remotes/origin/$branch"; then
    fail "Branch $branch already exists on GitHub (maybe a teammate's). Pick another name, or continue it:
  git switch $branch && make sync"
  fi

  git switch --quiet main
  sync
  step "New branch"
  git switch --quiet -c "$branch"
  echo "Now on $branch, starting from the latest main."
  echo "Next: build the feature (docs/PATTERNS.md), commit, then run make pr."
}

# --- check: everything CI checks, plus migrations ---------------------------------------

check() {
  step "Lint and format"
  make --no-print-directory -s lint ||
    fail "Lint or formatting failed (output above). Run make format, fix what remains by hand, commit, and run make check again."

  step "Migrations"
  require_conda_env
  require_docker
  make_step migrate
  local heads
  heads=$($FLASK db heads 2>/dev/null | grep -c "(head)" || true)
  [ "$heads" -eq 1 ] ||
    fail "Alembic has $heads migration heads: two branches each added a migration. Merge them into one:
  conda run -n $ENV_NAME --cwd backend flask --app app db merge heads -m \"merge\"
then commit the new migration file and run make check again."
  $FLASK db check >/dev/null 2>&1 ||
    fail "A model changed but no migration covers it (or the database is not at the latest migration).
Create the migration: make migration name=\"<module>: <what changed>\", review it, run make migrate, commit it."
  echo "Migrations are complete and in one line."

  step "Tests (pytest, then Vitest)"
  make --no-print-directory -s test ||
    fail "Tests failed (output above). Fix them, commit, and run make check again. Never push a red branch."

  step "Frontend build"
  $RUN --cwd frontend npm run build >/dev/null ||
    fail "The frontend does not build. Run: conda run -n $ENV_NAME --cwd frontend npm run build (to see the error), fix it, commit."
  echo "Builds."

  printf '\nAll checks passed.\n'
}

# --- pr: push the branch and open its pull request ---------------------------------------

pr() {
  local branch commits
  step "Before pushing"
  branch=$(current_branch)
  [ -n "$branch" ] && [ "$branch" != "main" ] ||
    fail "You are on ${branch:-no branch}. Nobody pushes to main: switch to your feature branch (git switch <branch>)."
  require_gh
  require_clean_tree
  fetch_origin
  git merge-base --is-ancestor origin/main HEAD ||
    fail "main has new commits since you branched. Bring them in first:
  git rebase origin/main     (on a conflict: fix the files, git add them, git rebase --continue)
then run make pr again."
  commits=$(git rev-list --count origin/main..HEAD)
  [ "$commits" -gt 0 ] || fail "Nothing to send: $branch has no commits beyond main. Commit your work first."
  echo "$branch: $commits commit(s) to send. If any check fails, nothing is pushed."

  check

  step "Push"
  git push --quiet -u origin HEAD ||
    fail "GitHub refused the push (see above). If you rebased this branch and nobody else works on it:
  git push --force-with-lease
then run make pr again. Never force-push main."
  echo "Pushed $branch."

  step "Pull request"
  if [ "$(gh pr view --json state --jq .state 2>/dev/null || true)" = "OPEN" ]; then
    echo "The pull request is updated: $(gh pr view --json url --jq .url)"
  else
    gh pr create --base main --head "$branch" \
      --title "$(git log --reverse --format=%s origin/main..HEAD | head -1)" \
      --body-file .github/pull_request_template.md ||
      fail "Could not create the pull request (see above). The branch is pushed; you can open it on GitHub instead."
    echo "Next: on GitHub, fill in the template (summary, ticks) and ask a teammate to review."
  fi
  echo "When CI is green and a teammate approved: make merge"
}

# --- merge: squash-merge an approved, green pull request ---------------------------------

merge() {
  local branch state url mergeable checks approved changes
  step "Pull request"
  branch=$(current_branch)
  [ -n "$branch" ] && [ "$branch" != "main" ] ||
    fail "Run this on the feature branch whose pull request you want to merge (git switch <branch>)."
  require_gh
  require_clean_tree
  state=$(gh pr view --json state --jq .state 2>/dev/null) ||
    fail "$branch has no pull request yet. Run: make pr"
  [ "$state" = "OPEN" ] || fail "The pull request of $branch is $state, not open. Nothing to merge."
  url=$(gh pr view --json url --jq .url)
  echo "$url"
  fetch_origin
  [ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$branch" 2>/dev/null || true)" ] ||
    fail "Your local $branch differs from the one on GitHub. Run make pr first, wait for CI, then make merge."

  step "Conflicts"
  mergeable=$(gh pr view --json mergeable --jq .mergeable)
  case "$mergeable" in
  MERGEABLE) echo "None." ;;
  CONFLICTING)
    fail "The pull request conflicts with main. Fix it on your branch:
  git rebase origin/main     (fix the files, git add them, git rebase --continue)
  git push --force-with-lease
then wait for CI and run make merge again."
    ;;
  *) fail "GitHub has not finished checking for conflicts yet. Wait a minute, then run make merge again." ;;
  esac

  step "CI"
  checks=$(gh pr checks 2>/dev/null || true)
  echo "$checks" | cut -f1,2 | sed 's/^/  /'
  if [ -z "$checks" ]; then
    fail "GitHub shows no CI checks yet. Wait a minute (see the Checks tab: $url), then run make merge again."
  elif grep -qE $'\t(fail|cancel)' <<<"$checks"; then
    fail "CI failed. Open the failed job on GitHub ($url/checks), fix it, commit, run make pr, then make merge."
  elif grep -qE $'\tpending' <<<"$checks"; then
    fail "CI is still running. Wait until it is green, then run make merge again."
  fi
  echo "Green."

  step "Review"
  changes=$(gh pr view --json latestReviews --jq '[.latestReviews[] | select(.state == "CHANGES_REQUESTED") | .author.login] | join(", ")')
  [ -z "$changes" ] || fail "$changes asked for changes. Make them, run make pr, and ask them to approve."
  approved=$(gh pr view --json latestReviews --jq '[.latestReviews[] | select(.state == "APPROVED") | .author.login] | join(", ")')
  [ -n "$approved" ] ||
    fail "No teammate has approved yet (every change to main needs one review). Ask one to review: $url"
  echo "Approved by $approved."

  step "Squash-merge"
  gh pr merge "$url" --squash --delete-branch ||
    fail "GitHub refused the merge (see above). Nothing changed on main."
  git switch --quiet main 2>/dev/null || true
  echo "Merged into main as one commit; the branch is deleted."

  sync
}

# --- doctor: check the whole setup, change nothing -------------------------------------

PROBLEMS=0
d_ok() { echo "  ok    $*"; }
d_note() { echo "  note  $*"; }
d_fix() {
  echo "  FIX   $*"
  PROBLEMS=$((PROBLEMS + 1))
}

doctor() {
  local branch
  step "Git"
  branch=$(current_branch)
  d_ok "branch: ${branch:-(detached HEAD)}"
  if [ -n "$(git status --porcelain)" ]; then
    d_note "$(git status --porcelain | wc -l | tr -d ' ') uncommitted change(s) (git status)"
  fi
  if git fetch origin --prune --quiet 2>/dev/null; then
    if [ "$branch" = "main" ]; then
      local ahead behind
      ahead=$(git rev-list --count origin/main..main)
      behind=$(git rev-list --count main..origin/main)
      [ "$ahead" -eq 0 ] || d_fix "local main has $ahead commit(s) not on GitHub: run make sync for the way out"
      [ "$behind" -eq 0 ] && d_ok "main is up to date with GitHub" || d_fix "main is $behind commit(s) behind GitHub: make sync"
    elif [ -n "$branch" ]; then
      local behind
      behind=$(git rev-list --count HEAD..origin/main)
      [ "$behind" -eq 0 ] && d_ok "$branch has everything from main" ||
        d_note "$branch is $behind commit(s) behind main: git rebase origin/main, then make sync"
    fi
  else
    d_fix "cannot reach GitHub: check your connection"
  fi

  step "Tools"
  if ! command -v conda >/dev/null 2>&1; then
    d_fix "conda not found: install Miniforge, then make setup"
  elif ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    d_fix "conda env '$ENV_NAME' missing: make setup"
  else
    d_ok "conda env '$ENV_NAME'"
    local py node
    py=$($RUN python -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "?")
    [ "$py" = "3.12" ] && d_ok "Python $py" || d_fix "Python in the env is $py, not 3.12: make env-update"
    node=$($RUN node -p 'process.versions.node' 2>/dev/null || echo "?")
    [ "${node%%.*}" = "22" ] && d_ok "Node $node" || d_fix "Node in the env is $node, not 22: make env-update"
  fi
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    d_ok "GitHub CLI logged in"
  else
    d_note "GitHub CLI missing or not logged in (needed only by make pr / make merge): gh auth login"
  fi

  step "Packages"
  # shellcheck disable=SC2086
  if [ "$(cat "$PY_STAMP" 2>/dev/null)" = "$(fingerprint $PY_DEP_FILES)" ]; then
    d_ok "Python packages match the requirements files"
  else
    d_fix "Python packages not synced with the requirements files: make sync"
  fi
  if [ ! -d frontend/node_modules ]; then
    d_fix "frontend/node_modules missing: make sync"
  elif [ "$(cat "$NPM_STAMP" 2>/dev/null)" = "$(fingerprint "$NPM_DEP_FILE")" ]; then
    d_ok "npm packages match package-lock.json"
  else
    d_fix "npm packages not synced with package-lock.json: make sync"
  fi

  step ".env"
  if [ ! -f .env ]; then
    d_fix ".env missing: make setup"
  else
    local missing
    missing=$(missing_env_vars | tr '\n' ' ')
    [ -z "$missing" ] && d_ok "every variable from .env.example is set" ||
      d_note "not set in .env (a default is used): $missing- copy them from .env.example"
  fi

  step "Docker services"
  if ! docker info >/dev/null 2>&1; then
    d_fix "Docker is not running: start Docker Desktop (WSL integration on), then make infra"
  else
    d_ok "Docker is running"
    local running
    running=$(docker compose ps --status running --services 2>/dev/null || true)
    grep -qx db <<<"$running" && d_ok "Postgres is running" || d_fix "Postgres is not running: make infra"
    grep -qx mailpit <<<"$running" && d_ok "Mailpit is running (http://localhost:8025)" || d_fix "Mailpit is not running: make infra"

    step "Database"
    if grep -qx db <<<"$running" && [ -f .env ] && conda env list 2>/dev/null | awk '{print $1}' | grep -qx "$ENV_NAME"; then
      local current
      current=$($FLASK db current 2>&1 || true)
      if grep -q "(head)" <<<"$current"; then
        d_ok "database is at the latest migration"
      elif grep -q "Can't locate revision" <<<"$current"; then
        d_fix "the database has a migration this code does not know: git rebase origin/main (or git pull on main), then make sync"
      elif grep -qiE "connection refused|connection failed" <<<"$current"; then
        d_fix "cannot connect to Postgres: make infra"
      else
        d_fix "the database is not at the latest migration: make migrate"
      fi
    else
      d_note "skipped (needs Postgres, .env and the conda env)"
    fi
  fi

  step "Dev servers (information only)"
  local health
  health=$(curl -s -m 3 http://localhost:8000/api/health 2>/dev/null || true)
  if grep -q '"status": *"ok"' <<<"$health"; then
    d_ok "API running on http://localhost:8000 (database ok)"
  elif [ -n "$health" ]; then
    d_note "API running on :8000 but reports the database unavailable: make infra"
  else
    d_note "API not running: make dev-backend"
  fi
  if curl -s -m 3 -o /dev/null http://localhost:5173/ 2>/dev/null; then
    d_ok "frontend running on http://localhost:5173"
  else
    d_note "frontend not running: make dev-frontend"
  fi

  echo
  if [ "$PROBLEMS" -eq 0 ]; then
    echo "Everything needed is in place."
  else
    echo "$PROBLEMS problem(s): follow the FIX lines above, then run make doctor again."
    exit 1
  fi
}

case "${1:-}" in
doctor) doctor ;;
sync) sync ;;
feature) feature "${2:-}" ;;
check) check ;;
pr) pr ;;
merge) merge ;;
*) fail "Usage: make doctor | make sync | make feature branch=<name>/<module>-<task> | make check | make pr | make merge" ;;
esac
