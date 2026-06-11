$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$appDir = Join-Path $root "AMM-simulation"

Write-Host "================================================"
Write-Host "  AMM Simulation - One Click Launcher"
Write-Host "================================================"
Write-Host ""

if (-not (Test-Path -LiteralPath (Join-Path $appDir "run.py"))) {
    Write-Host "[ERROR] Cannot find run.py under: $appDir" -ForegroundColor Red
    Write-Host "Please keep start.bat/start.ps1 in the AMM-simulation-main folder."
    Read-Host "Press Enter to exit"
    exit 1
}

$pythonCandidates = @(
    (Join-Path $env:USERPROFILE "AppData\Local\Python\bin\python.exe"),
    (Join-Path $env:USERPROFILE "AppData\Local\Python\pythoncore-3.14-64\python.exe"),
    (Join-Path $env:USERPROFILE "AppData\Local\Programs\Python\Python314\python.exe")
)

$pythonExe = $pythonCandidates | Where-Object {
    Test-Path -LiteralPath $_
} | Select-Object -First 1

if (-not $pythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -notlike "*Microsoft\WindowsApps*" } |
        Select-Object -First 1
    if ($cmd) {
        $pythonExe = $cmd.Source
    }
}

if (-not $pythonExe) {
    Write-Host "[ERROR] Python was not found." -ForegroundColor Red
    Write-Host "Please install Python or add it to PATH, then run this script again."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[INFO] Using Python:"
& $pythonExe -V
Write-Host ""

Push-Location $appDir
try {
    Write-Host "[INFO] Checking dependencies..."
    & $pythonExe -c "import flask" *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[INFO] Flask is missing. Installing requirements..."
        & $pythonExe -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Failed to install dependencies." -ForegroundColor Red
            Read-Host "Press Enter to exit"
            exit 1
        }
    }

    if ($args.Count -gt 0 -and $args[0] -ieq "--check") {
        Write-Host "[OK] Environment check passed." -ForegroundColor Green
        exit 0
    }

    Write-Host ""
    Write-Host "[INFO] Starting AMM simulation..."
    Write-Host "[INFO] Browser will open http://127.0.0.1:5000"
    Write-Host "[INFO] Press Ctrl+C in this window to stop the server."
    Write-Host ""

    & $pythonExe run.py
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "[INFO] Server stopped."
Read-Host "Press Enter to exit"
