# LegacyBridge — One-Click Demo Launcher
# ----------------------------------------
# Starts the backend server and generates mock screens for the demo.
#
# Usage:
#   Right-click this file → Run with PowerShell
#   OR from terminal: .\demo\start_demo.ps1
#
# Before running:
#   1. Set GOOGLE_APPLICATION_CREDENTIALS in your .env or below
#   2. Ensure .venv is set up: pip install -r server/requirements.txt

param(
    [string]$KeyPath = "C:\Users\User\Downloads\key.json",
    [string]$BackendUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         LegacyBridge — DEMO LAUNCHER  🎬                ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Activate virtual environment ─────────────────────────────────────
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Yellow
$venvPath = Join-Path $PSScriptRoot ".." ".venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    & $venvPath
    Write-Host "   ✅ Virtual environment active" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  .venv not found. Using system Python." -ForegroundColor Yellow
}

# ── Step 2: Set credentials ───────────────────────────────────────────────────
Write-Host ""
Write-Host "🔑 Setting Google credentials..." -ForegroundColor Yellow
if (Test-Path $KeyPath) {
    $env:GOOGLE_APPLICATION_CREDENTIALS = $KeyPath
    Write-Host "   ✅ Credentials set: $KeyPath" -ForegroundColor Green
} else {
    Write-Host "   ❌ key.json not found at: $KeyPath" -ForegroundColor Red
    Write-Host "      Update -KeyPath parameter or set GOOGLE_APPLICATION_CREDENTIALS manually."
    exit 1
}

# ── Step 3: Generate mock screens ─────────────────────────────────────────────
Write-Host ""
Write-Host "🎨 Generating demo mock screens..." -ForegroundColor Yellow
$rootPath = Join-Path $PSScriptRoot ".."
Push-Location $rootPath
python demo/mock_screen_generator.py
Pop-Location

# ── Step 4: Start backend server in a new window ──────────────────────────────
Write-Host ""
Write-Host "🚀 Starting backend server..." -ForegroundColor Yellow
$serverPath = Join-Path $rootPath "server"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$serverPath'; `$env:GOOGLE_APPLICATION_CREDENTIALS='$KeyPath'; uvicorn app.main:app --reload --port 8000"
) -WindowStyle Normal

# ── Step 5: Wait for backend to come online ────────────────────────────────────
Write-Host "   ⏳ Waiting for backend to start..." -ForegroundColor Yellow
$maxWait = 30
$waited = 0
do {
    Start-Sleep -Seconds 2
    $waited += 2
    try {
        $resp = Invoke-RestMethod -Uri "$BackendUrl/" -TimeoutSec 2 -ErrorAction Stop
        Write-Host "   ✅ Backend online: $($resp.status)" -ForegroundColor Green
        break
    } catch {
        Write-Host "   ...waiting ($waited/$maxWait s)" -ForegroundColor Gray
    }
} while ($waited -lt $maxWait)

if ($waited -ge $maxWait) {
    Write-Host "   ❌ Backend did not start in time. Check the server window for errors." -ForegroundColor Red
    exit 1
}

# ── Step 6: Print demo instructions ───────────────────────────────────────────
Write-Host ""
Write-Host "══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ LegacyBridge is ready for demo recording!" -ForegroundColor Green
Write-Host "══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  📹 Now start your screen recorder (OBS, etc.)" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Then run one of these:" -ForegroundColor White
Write-Host "    python demo/demo_runner.py              (run ALL scenarios)" -ForegroundColor Yellow
Write-Host "    python demo/demo_runner.py --scenario 0 (Home Screen)" -ForegroundColor Yellow
Write-Host "    python demo/demo_runner.py --scenario 2 (Confusion Demo)" -ForegroundColor Yellow
Write-Host "    python demo/demo_runner.py --list        (list all)" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Backend API docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
