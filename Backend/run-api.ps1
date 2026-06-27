# Run Simple Tech API locally (Windows)
# Usage: powershell -ExecutionPolicy Bypass -File run-api.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -q

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example — edit JWT_SECRET_KEY before production."
}

Write-Host "Starting API at http://localhost:8000 (docs: /docs)"
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
