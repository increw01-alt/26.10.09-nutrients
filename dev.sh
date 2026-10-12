#!/usr/bin/env bash
# 영양제.kr 로컬 개발 서버 (WSL2 Ubuntu / macOS / Linux)
# 사용법: ./dev.sh [--build] [포트]
set -euo pipefail
cd "$(dirname "$0")"
PORT=8080; BUILD=0
for a in "$@"; do case "$a" in --build) BUILD=1;; *) PORT="$a";; esac; done
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
if [ "$BUILD" = 1 ]; then
  if command -v npm >/dev/null 2>&1; then [ -d node_modules ] || npm ci; npm run assets; else echo "[안내] npm 이 없어 CSS·아이콘 번들은 건너뜁니다. push 하면 GitHub Actions 가 자동 생성합니다."; fi
  .venv/bin/python scripts/build_site.py
fi
echo "로컬 서버: http://localhost:$PORT  (종료: Ctrl+C)"
.venv/bin/python -m http.server "$PORT" --bind 127.0.0.1
