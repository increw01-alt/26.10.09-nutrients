# 영양제.kr 로컬 개발 서버 (Windows PowerShell)
# 사용법: 폴더에서 마우스 오른쪽 → "PowerShell에서 열기" 후  .\dev.ps1
#   처음 실행 시 "실행 정책" 오류가 나면:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
param([int]$Port = 8080, [switch]$Build)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Host "Python 이 필요합니다: https://www.python.org/downloads/ (설치 시 'Add python.exe to PATH' 체크)" -ForegroundColor Red; exit 1 }

if (-not (Test-Path ".venv")) {
  Write-Host "가상환경 생성 중..." -ForegroundColor Cyan
  python -m venv .venv
}
& ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt

if ($Build) {
  if (Get-Command npm -ErrorAction SilentlyContinue) {
    if (-not (Test-Path "node_modules")) { npm ci }
    Write-Host "Tailwind CSS·아이콘 번들 생성 (npm run assets)..." -ForegroundColor Cyan
    npm run assets
  } else { Write-Host "[안내] npm 이 없어 CSS·아이콘 번들은 건너뜁니다. push 하면 GitHub Actions 가 자동 생성합니다." -ForegroundColor Yellow }
  Write-Host "정적 페이지 생성 (build_site.py)..." -ForegroundColor Cyan
  & ".venv\Scripts\python.exe" scripts\build_site.py
}

Write-Host "로컬 서버: http://localhost:$Port  (종료: Ctrl+C)" -ForegroundColor Green
Start-Process "http://localhost:$Port"
& ".venv\Scripts\python.exe" -m http.server $Port --bind 127.0.0.1
