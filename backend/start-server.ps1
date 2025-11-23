# PowerShell script to start the backend FastAPI server
# Usage: .\start-server.ps1

# Get the script directory (backend folder)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "Starting backend server..." -ForegroundColor Green
Write-Host "Working directory: $ScriptDir" -ForegroundColor Gray

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python version: $pythonVersion" -ForegroundColor Gray
} catch {
    Write-Host "Error: Python not found. Please ensure Python is installed and in your PATH." -ForegroundColor Red
    exit 1
}

# Check if virtual environment exists
$venvPath = Join-Path $ScriptDir ".venv"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"

if (Test-Path $venvActivate) {
    Write-Host "Activating virtual environment..." -ForegroundColor Gray
    & $venvActivate
} else {
    Write-Host "No virtual environment found. Using system Python." -ForegroundColor Yellow
}

# Check if requirements are installed (quick check for uvicorn)
try {
    python -c "import uvicorn" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: uvicorn not found. Installing requirements..." -ForegroundColor Yellow
        pip install -r requirements.txt
    }
} catch {
    Write-Host "Warning: Could not verify uvicorn installation." -ForegroundColor Yellow
}

# Start the server using uvicorn
Write-Host "Starting FastAPI server on http://0.0.0.0:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

try {
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
} catch {
    Write-Host "Error starting server: $_" -ForegroundColor Red
    exit 1
}

