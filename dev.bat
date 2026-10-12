@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 이 필요합니다: https://www.python.org/downloads/ & pause & exit /b 1)
if not exist ".venv" python -m venv .venv
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if /i "%1"=="build" (
  where npm >nul 2>nul && (if not exist "node_modules" call npm ci) && call npm run assets || echo [안내] npm 이 없어 Tailwind CSS·아이콘 번들은 건너뜁니다. push 하면 GitHub Actions 가 자동 생성합니다.
  ".venv\Scripts\python.exe" scripts\build_site.py
)
echo 로컬 서버: http://localhost:8080  (종료: Ctrl+C)
start "" http://localhost:8080
".venv\Scripts\python.exe" -m http.server 8080 --bind 127.0.0.1
