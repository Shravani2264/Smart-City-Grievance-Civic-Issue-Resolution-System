# One-command launcher: builds the dashboard and serves API + UI on http://localhost:8000
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path node_modules)) { npm install }
npm run build
pip install -q -r backend/requirements.txt
Set-Location backend
Write-Host "CivicPulse running at http://localhost:8000" -ForegroundColor Green
python -m uvicorn app.main:app --port 8000
