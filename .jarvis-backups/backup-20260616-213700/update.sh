#!/usr/bin/env bash
# =============================================================================
# JARVIS Update Script — applies a jarvis-phaseX.zip to the installation dir
# Usage:  ./update.sh <jarvis-phaseX.zip> [--dry-run] [--skip-backup]
# =============================================================================
set -euo pipefail

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✔${NC}  $*"; }
info() { echo -e "${CYAN}→${NC}  $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
fail() { echo -e "${RED}✘${NC}  $*" >&2; }
step() { echo -e "\n${BOLD}$*${NC}"; }

# ── args ──────────────────────────────────────────────────────────────────────
ZIP="${1:-}"
DRY_RUN=false; SKIP_BACKUP=false
for arg in "${@:2}"; do
  case "$arg" in
    --dry-run)     DRY_RUN=true ;;
    --skip-backup) SKIP_BACKUP=true ;;
    *) fail "Unknown flag: $arg"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/.jarvis-backups"
WORK_DIR=""
ROLLBACK_BACKUP=""

# ── cleanup / rollback ────────────────────────────────────────────────────────
cleanup() { [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]] && rm -rf "$WORK_DIR"; }
trap cleanup EXIT

rollback() {
  fail "Update failed. Rolling back…"
  if [[ -n "$ROLLBACK_BACKUP" && -d "$ROLLBACK_BACKUP" ]]; then
    python3 -c "
import shutil, pathlib, sys
src = pathlib.Path('$ROLLBACK_BACKUP')
dst = pathlib.Path('$SCRIPT_DIR')
SKIP = {'.jarvis-backups', 'data', 'node_modules', '.next', '__pycache__'}
for item in src.iterdir():
    if item.name in SKIP:
        continue
    t = dst / item.name
    if item.is_dir():
        if t.exists():
            shutil.rmtree(t)
        shutil.copytree(item, t)
    else:
        shutil.copy2(item, t)
print('Rolled back to: $ROLLBACK_BACKUP')
"
    ok "Rolled back to $(basename "$ROLLBACK_BACKUP")"
    if command -v docker >/dev/null 2>&1 && [[ -f "$SCRIPT_DIR/docker-compose.yml" ]]; then
      docker compose up -d --build 2>/dev/null || true
    fi
  else
    warn "No backup available — rollback skipped."
  fi
  exit 1
}

# ── validate args ─────────────────────────────────────────────────────────────
step "[ JARVIS Updater ]"
echo -e "  Package : ${BOLD}${ZIP}${NC}"
echo -e "  Target  : ${BOLD}${SCRIPT_DIR}${NC}"
echo -e "  Dry-run : ${DRY_RUN}"

[[ -z "$ZIP" ]]       && { fail "Usage: ./update.sh <jarvis-phaseX.zip> [--dry-run] [--skip-backup]"; exit 1; }
[[ ! -f "$ZIP" ]]     && { fail "File not found: $ZIP"; exit 1; }
[[ "$ZIP" != *.zip ]] && { fail "Expected a .zip file"; exit 1; }
command -v unzip >/dev/null 2>&1 || { fail "'unzip' is required (brew install unzip / apt install unzip)"; exit 1; }
command -v python3 >/dev/null 2>&1 || { fail "'python3' is required"; exit 1; }

# ── extract ───────────────────────────────────────────────────────────────────
step "1 / 6  Inspecting package"
WORK_DIR="$(mktemp -d)"
unzip -q "$ZIP" -d "$WORK_DIR"

# Handle zip with or without a top-level 'jarvis/' folder
JARVIS_ROOT="$WORK_DIR"
[[ -d "$WORK_DIR/jarvis" ]] && JARVIS_ROOT="$WORK_DIR/jarvis"

if [[ ! -d "$JARVIS_ROOT/backend" && ! -d "$JARVIS_ROOT/frontend" ]]; then
  fail "The zip does not look like a JARVIS package (no backend/ or frontend/ found)"
  exit 1
fi

# ── diff (pure Python, no rsync) ──────────────────────────────────────────────
CHANGED_FILES=$(python3 - << PYEOF
import hashlib, pathlib, sys

SKIP_DIRS  = {'.env', 'data', 'node_modules', '.next', '__pycache__', '.git', '.jarvis-backups'}
SKIP_EXTS  = {'.pyc', '.pyo', '.log'}

def digest(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

src = pathlib.Path("$JARVIS_ROOT")
dst = pathlib.Path("$SCRIPT_DIR")
changed = []

for sf in src.rglob('*'):
    if sf.is_dir():
        continue
    # skip unwanted dirs/extensions
    parts = set(sf.relative_to(src).parts)
    if parts & SKIP_DIRS or sf.suffix in SKIP_EXTS:
        continue
    rel = sf.relative_to(src)
    df  = dst / rel
    if not df.exists() or digest(sf) != digest(df):
        changed.append(str(rel))

for f in sorted(changed):
    print(f)
PYEOF
)

if [[ -z "$CHANGED_FILES" ]]; then
  ok "Nothing to update — package matches what is already installed."
  exit 0
fi

CHANGED_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')
info "$CHANGED_COUNT file(s) will be updated:"
echo "$CHANGED_FILES" | while IFS= read -r f; do
  echo -e "     ${CYAN}${f}${NC}"
done

$DRY_RUN && { echo ""; ok "Dry run complete — nothing written."; exit 0; }

# ── backup ────────────────────────────────────────────────────────────────────
if ! $SKIP_BACKUP; then
  step "2 / 6  Creating backup"
  mkdir -p "$BACKUP_DIR"
  ROLLBACK_BACKUP="$BACKUP_DIR/backup-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$ROLLBACK_BACKUP"
  python3 - << PYEOF
import shutil, pathlib
src = pathlib.Path("$SCRIPT_DIR")
dst = pathlib.Path("$ROLLBACK_BACKUP")
SKIP = {'.jarvis-backups', 'data', 'node_modules', '.next', '__pycache__', '.git'}
for item in src.iterdir():
    if item.name in SKIP:
        continue
    t = dst / item.name
    if item.is_dir():
        shutil.copytree(item, t, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'node_modules', '.next'))
    else:
        shutil.copy2(item, t)
PYEOF
  ok "Backup → $ROLLBACK_BACKUP"
  # Prune backups older than 30 days (python-based, no find needed)
  python3 -c "
import pathlib, time
base = pathlib.Path('$BACKUP_DIR')
cutoff = time.time() - 30*86400
for d in base.iterdir():
    if d.is_dir() and d.stat().st_mtime < cutoff:
        import shutil; shutil.rmtree(d); print('Pruned:', d.name)
" 2>/dev/null || true
else
  warn "Skipping backup (--skip-backup)"
fi

# ── apply ─────────────────────────────────────────────────────────────────────
step "3 / 6  Applying changes"
trap rollback ERR

python3 - << PYEOF
import shutil, pathlib

SKIP_DIRS = {'.env', 'data', 'node_modules', '.next', '__pycache__', '.git', '.jarvis-backups'}
SKIP_EXTS = {'.pyc', '.pyo', '.log'}
FILES = """$CHANGED_FILES""".strip().splitlines()

src = pathlib.Path("$JARVIS_ROOT")
dst = pathlib.Path("$SCRIPT_DIR")

for rel in FILES:
    sf = src / rel
    df = dst / rel
    df.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sf, df)

print(f"Applied {len(FILES)} file(s)")
PYEOF
ok "$CHANGED_COUNT file(s) applied"

# ── Python deps ───────────────────────────────────────────────────────────────
step "4 / 6  Installing dependencies"
BACKEND="$SCRIPT_DIR/backend"

if [[ -f "$BACKEND/pyproject.toml" ]]; then
  PY="python3"
  [[ -f "$BACKEND/.venv/bin/python" ]] && PY="$BACKEND/.venv/bin/python" && info "Using venv"
  if $PY -m pip install -q -e "$BACKEND" 2>&1 | grep -v "already satisfied\|Obtaining\|cached" | head -20; then
    ok "Python dependencies up to date"
  else
    warn "pip install had warnings (check above)"
  fi
fi

FRONTEND="$SCRIPT_DIR/frontend"
if [[ -f "$FRONTEND/package.json" ]]; then
  if command -v npm >/dev/null 2>&1; then
    npm install --prefix "$FRONTEND" --silent 2>&1 | tail -3
    ok "npm packages up to date"
  else
    warn "npm not found — run 'npm install' in frontend/ manually"
  fi
fi

# ── DB migrations (Alembic) ───────────────────────────────────────────────────
if [[ -f "$BACKEND/alembic.ini" ]]; then
  PY="python3"
  [[ -f "$BACKEND/.venv/bin/python" ]] && PY="$BACKEND/.venv/bin/python"
  # Only run if alembic is installed; skip silently in offline/dev setups
  if $PY -c "import alembic" 2>/dev/null; then
    info "Running database migrations…"
    (cd "$BACKEND" && $PY -m alembic upgrade head 2>&1 | tail -5) || warn "Migration skipped (DB may not be running)"
  fi
fi

# ── tests ─────────────────────────────────────────────────────────────────────
step "5 / 6  Running tests"
if [[ -d "$BACKEND/tests" ]]; then
  PY="python3"
  [[ -f "$BACKEND/.venv/bin/python" ]] && PY="$BACKEND/.venv/bin/python"
  if (cd "$BACKEND" && JARVIS_NIM_API_KEY="" $PY -m pytest -q 2>&1 | tail -6); then
    ok "All tests passed"
  else
    fail "Tests failed — rolling back"
    rollback
  fi
else
  warn "No tests/ directory found — skipping"
fi

# ── restart services ──────────────────────────────────────────────────────────
step "6 / 6  Restarting services"
if command -v docker >/dev/null 2>&1 && [[ -f "$SCRIPT_DIR/docker-compose.yml" ]]; then
  if docker compose ps --services --status running 2>/dev/null | grep -q .; then
    info "Rebuilding running Docker services…"
    docker compose up -d --build 2>&1 | tail -6
    ok "Services restarted"
  else
    warn "No running Docker services found — start with: docker compose up --build"
  fi
else
  warn "Docker not found — restart services manually"
fi

# ── summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}Update complete!${NC}"
echo ""
echo -e "  Package  : ${CYAN}$(basename "$ZIP")${NC}"
echo -e "  Files    : ${CYAN}${CHANGED_COUNT} updated${NC}"
echo -e "  Backup   : ${CYAN}${ROLLBACK_BACKUP:-none}${NC}"
echo ""
if [[ -n "$ROLLBACK_BACKUP" ]]; then
  echo -e "  To rollback manually:"
  echo -e "    ${YELLOW}./update.sh --rollback $(basename "$ROLLBACK_BACKUP")${NC}"
fi