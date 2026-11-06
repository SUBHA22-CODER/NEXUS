# Starts NEXUS on Windows: the API and the frontend each get their own window, then the browser opens.
# Run from PowerShell:  .\start.ps1
# If scripts are blocked: powershell -ExecutionPolicy Bypass -File .\start.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

function Test-Port($port) {
    [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Port($port, $name) {
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-Port $port) { return }
        Start-Sleep -Seconds 1
    }
    throw "$name did not start on port $port. Check its window for the error."
}

if (-not (Test-Path $python)) {
    Write-Host "Setting up the backend (first run only)..."
    Push-Location $backend
    try {
        python -m venv .venv
        & $python -m pip install -r requirements-dev.txt
        if ($LASTEXITCODE -ne 0) { throw "Installing backend packages failed." }
    } finally { Pop-Location }
}

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Setting up the frontend (first run only)..."
    Push-Location $frontend
    try {
        npm.cmd install
        if ($LASTEXITCODE -ne 0) { throw "Installing frontend packages failed." }
    } finally { Pop-Location }
}

if (Test-Port 8000) {
    Write-Host "API already running on port 8000."
} else {
    Start-Process powershell -WorkingDirectory $backend -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'NEXUS API'; & '$python' -m uvicorn app.main:app --port 8000"
    Wait-Port 8000 "The API"
}

if (Test-Port 5173) {
    Write-Host "Frontend already running on port 5173."
} else {
    Start-Process powershell -WorkingDirectory $frontend -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'NEXUS frontend'; npm.cmd run dev"
    Wait-Port 5173 "The frontend"
}

Write-Host "NEXUS is running at http://localhost:5173 (close the two server windows to stop it)."
Start-Process "http://localhost:5173"
