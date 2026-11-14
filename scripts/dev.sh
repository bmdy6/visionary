#!/usr/bin/env bash
# Run from any directory. Bind only to loopback; Ctrl+C stops both services.
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"
command -v python3 >/dev/null || { echo 'Install Python 3.10+ first.' >&2; exit 1; }
command -v npm >/dev/null || { echo 'Install Node.js and npm first.' >&2; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (!((major === 22 && minor >= 13) || major >= 24)) { throw Error("Node.js 22.13+ or 24+ required"); }'
# Refuse occupied ports before starting or modifying local setup.
python3 - <<'PY'
import socket
for port in (8000, 5173):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"Port {port} is occupied; stop that service before running dev.sh.")
PY
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python - <<'PY'
from pathlib import Path
import secrets
p = Path(".env")
if not p.exists():
    p.write_text(Path(".env.example").read_text().replace(
        "SECRET_KEY=replace-with-a-new-random-secret-at-least-32-characters",
        "SECRET_KEY=" + secrets.token_urlsafe(48)))
    p.chmod(0o600)
    print("Created .env with a random SECRET_KEY; external service credentials are empty.")
else:
    print("Preserving existing .env.")
PY
.venv/bin/python -m scripts.init_db --admin local-admin --if-missing
(cd frontend && npm ci)
backend_pid=''
frontend_pid=''
cleanup() {
  trap - EXIT INT TERM
  if [ -n "$frontend_pid" ]; then kill "$frontend_pid" 2>/dev/null || true; fi
  if [ -n "$backend_pid" ]; then kill "$backend_pid" 2>/dev/null || true; fi
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
.venv/bin/python -m uvicorn api.index:app --host 127.0.0.1 --port 8000 &
backend_pid=$!
# Wait for the API before exposing the frontend health check.
.venv/bin/python - <<'PY'
import time
import urllib.request
for attempt in range(100):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=1) as r:
            if r.status == 200:
                break
    except OSError:
        time.sleep(0.1)
else:
    raise SystemExit("Backend did not become ready.")
PY
node frontend/node_modules/vite/bin/vite.js frontend --host 127.0.0.1 --port 5173 --strictPort &
frontend_pid=$!
echo 'Open http://127.0.0.1:5173 and log in as local-admin with the password you just set. Ctrl+C stops both services.'
while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do sleep 1; done
# One service exited: EXIT trap stops the other, rather than leaving it behind.
exit 1
