# Run SnapDish backend and mobile app locally so you can view it.
# Run from repo root: .\run-local.ps1

$ErrorActionPreference = 'Stop'
$RepoRoot = $PSScriptRoot

# 1. Backend venv and deps
$venvPy = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating backend venv and installing deps..."
    Set-Location $RepoRoot
    py -3.12 -m venv backend\.venv
    & backend\.venv\Scripts\pip.exe install -q -r backend\requirements.txt
    Set-Location $RepoRoot
}

# 2. Start backend in a new window
Write-Host "Starting backend in a new window (http://127.0.0.1:8000)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RepoRoot\backend'; .\.venv\Scripts\python.exe -m uvicorn snapdish.main:app --reload --port 8000"

Start-Sleep -Seconds 3

# 3. Start Expo (web) in this window so you can view in browser
Write-Host "Starting mobile app (Expo web)..."
Write-Host "When ready, open the URL shown (e.g. http://localhost:8081) in your browser."
Write-Host "In the app: Settings tab -> set API URL to http://localhost:8000"
Write-Host ""
Set-Location (Join-Path $RepoRoot "mobile")
npx expo start --web
