# Simple Docker diagnostic script for VS Code
Write-Host "Docker Setup Diagnostic for VS Code" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

# Check Docker Desktop installation
Write-Host ""
Write-Host "Checking Docker Desktop installation..." -ForegroundColor Yellow

$dockerPaths = @(
    "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe",
    "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe"
)

$dockerFound = $false
foreach ($path in $dockerPaths) {
    if (Test-Path $path) {
        Write-Host "Docker Desktop found at: $path" -ForegroundColor Green
        $dockerFound = $true
        break
    }
}

if (-not $dockerFound) {
    Write-Host "Docker Desktop not found. Please install from docker.com" -ForegroundColor Red
    exit 1
}

# Check Docker processes
Write-Host ""
Write-Host "Checking Docker processes..." -ForegroundColor Yellow

$dockerProcesses = Get-Process -Name "*docker*" -ErrorAction SilentlyContinue
if ($dockerProcesses) {
    Write-Host "Docker processes found:" -ForegroundColor Green
    foreach ($proc in $dockerProcesses) {
        Write-Host "  - $($proc.ProcessName)" -ForegroundColor Cyan
    }
} else {
    Write-Host "No Docker processes running. Starting Docker Desktop..." -ForegroundColor Yellow
    $dockerExe = $dockerPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    Start-Process -FilePath $dockerExe
    Write-Host "Docker Desktop started. Please wait 30-60 seconds..." -ForegroundColor Cyan
}

# Test Docker CLI
Write-Host ""
Write-Host "Testing Docker CLI..." -ForegroundColor Yellow

try {
    $dockerVersion = & docker --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Docker CLI working: $dockerVersion" -ForegroundColor Green
    } else {
        Write-Host "Docker CLI not responding. Please wait for Docker to initialize." -ForegroundColor Yellow
    }
} catch {
    Write-Host "Docker CLI not available. Please wait for Docker to initialize." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Wait for Docker to fully start" -ForegroundColor White
Write-Host "2. Run: docker --version" -ForegroundColor White
Write-Host "3. Run: docker compose build" -ForegroundColor White
Write-Host "4. Use VS Code Docker extension panel" -ForegroundColor White