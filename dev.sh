#!/usr/bin/env bash
# 영양제.kr 로컬 개발 서버 (WSL2 Ubuntu / macOS / Linux)
# 사용법: ./dev.sh [--build] [포트]
set -euo pipefail
cd "$(dirname "$0")"
PORT=8080; BUILD=0
for a in "$@"; do case "$a" in --build) BUILD=1;; *) PORT="$a";; esac; done
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
[ "$BUILD" = 1 ] && .venv/bin/python scripts/build_site.py
echo "로컬 서버: http://localhost:$PORT  (종료: Ctrl+C)"
.venv/bin/python -m http.server "$PORT" --bind 127.0.0.1
