param(
    [int]$Port = 8011,
    [string]$BindHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "Missing virtual environment: $PythonExe" -ForegroundColor Red
    Write-Host "Create it first with: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
    Write-Host "Missing .env file in project root." -ForegroundColor Red
    Write-Host "Create it from .env.example first." -ForegroundColor Yellow
    exit 1
}

Write-Host "Project root: $ProjectRoot" -ForegroundColor Cyan
Write-Host "Starting CyberIdol backend on http://${BindHost}:$Port" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow

& $PythonExe -m uvicorn app:app --host $BindHost --port $Port
