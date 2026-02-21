param(
  [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -Path "backend\.venv\Scripts\python.exe")) {
  Write-Host "Creating venv (Python 3.12) and installing deps..."
  py -3.12 -m venv backend\.venv
  backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
}

Write-Host "Starting SnapDish API on http://127.0.0.1:$Port ..."
backend\.venv\Scripts\python.exe -m uvicorn backend.snapdish.main:app --reload --port $Port
