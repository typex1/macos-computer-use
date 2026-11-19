#!/usr/bin/env bash
# One-time setup and self-check for the macos-computer-use skill.
# Safe to re-run. Creates a venv next to this script, installs the Python
# dependencies and the chrome-devtools CLI, then verifies permissions.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/.venv"
PY="$VENV/bin/python"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This skill only works on macOS." >&2; exit 1
fi

step() { printf '\n== %s\n' "$*"; }
ok()   { printf '   ok   %s\n' "$*"; }
warn() { printf '   WARN %s\n' "$*"; }

step "Python environment"
if [[ ! -x "$PY" ]]; then
  python3 -m venv "$VENV"
fi
"$PY" -m pip install -q --upgrade pip >/dev/null
"$PY" -m pip install -q -r "$HERE/requirements.txt"
ok "venv at $VENV ($("$PY" --version))"

step "Chrome DevTools CLI (optional, for the Chrome layer)"
if command -v npm >/dev/null; then
  if ! command -v chrome-devtools >/dev/null; then
    npm install -g chrome-devtools-mcp@latest >/dev/null 2>&1 && ok "installed chrome-devtools-mcp" || warn "npm install of chrome-devtools-mcp failed"
  else
    ok "chrome-devtools $(chrome-devtools --version 2>/dev/null) present"
  fi
else
  warn "npm not found; Chrome layer unavailable until Node.js is installed"
fi
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [[ -x "$CHROME" ]]; then
  ver="$("$CHROME" --version 2>/dev/null | grep -oE '[0-9]+' | head -1 || true)"
  if [[ -n "$ver" && "$ver" -ge 144 ]]; then
    ok "Chrome $ver supports chrome://inspect/#remote-debugging (enable it there once)"
  else
    warn "Chrome ${ver:-?} < 144: --autoConnect unavailable; use a side profile with --remote-debugging-port"
  fi
else
  warn "Google Chrome not found"
fi

step "macOS permissions for the process hosting this shell"
HOST="$(ps -o comm= -p "$PPID" 2>/dev/null || true)"
echo "   shell host process: ${HOST:-unknown}  (grant permissions to the app that owns it, e.g. Kiro, iTerm, Terminal)"
if "$PY" -c 'import ApplicationServices as A, sys; sys.exit(0 if A.AXIsProcessTrusted() else 1)'; then
  ok "Accessibility granted (synthetic input and AX tree)"
else
  warn "Accessibility missing: System Settings > Privacy & Security > Accessibility"
  open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" 2>/dev/null || true
fi
if "$PY" - <<'EOF'
import Quartz, sys
img = Quartz.CGWindowListCreateImage(Quartz.CGRectMake(0,0,10,10), Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID, 0)
infos = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
named = any(w.get("kCGWindowName") for w in infos if w.get("kCGWindowOwnerName") not in (None, "Window Server"))
sys.exit(0 if img is not None and named else 1)
EOF
then
  ok "Screen Recording granted (window capture and titles)"
else
  warn "Screen Recording missing: System Settings > Privacy & Security > Screen Recording"
  open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture" 2>/dev/null || true
fi

step "Smoke test"
"$PY" "$HERE/scripts/ax.py" apps | head -3
"$PY" "$HERE/scripts/cu.py" windows | head -3

cat <<EOF

Done. Use the tools as:
  $PY $HERE/scripts/ax.py  ...
  $PY $HERE/scripts/cu.py  ...
  $PY $HERE/scripts/ocr.py ...
Screenshots go to ./.computer-use/screenshots (newest 20 kept); add that folder to .gitignore.
EOF
