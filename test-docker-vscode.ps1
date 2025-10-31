# PowerShell script to test Docker setup in VS Code
# This script helps diagnose and test Docker functionality

Write-Host "🔧 Docker Setup Diagnostic for VS Code" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Function to test command availability
function Test-Command {
    param([string]$Command)
    try {
        if (Get-Command $Command -ErrorAction SilentlyContinue) {
            return $true
        }
    } catch {
        return $false
    }
    return $false
}

# Check if Docker Desktop is installed
Write-Host "🔍 Checking Docker installation..." -ForegroundColor Yellow

$dockerPaths = @(
    "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe",
    "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe",
    "${env:LOCALAPPDATA}\Programs\Docker\Docker\Docker Desktop.exe"
)

$dockerFound = $false
foreach ($path in $dockerPaths) {
    if (Test-Path $path) {
        Write-Host "✅ Docker Desktop found at: $path" -ForegroundColor Green
        $dockerFound = $true
        break
    }
}

if (-not $dockerFound) {
    Write-Host "❌ Docker Desktop not found in common locations" -ForegroundColor Red
    Write-Host "   Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
}

# Check if Docker CLI is in PATH
Write-Host ""
Write-Host "🔍 Checking Docker CLI availability..." -ForegroundColor Yellow

if (Test-Command "docker") {
    Write-Host "✅ Docker CLI is available in PATH" -ForegroundColor Green
    try {
        $version = docker --version 2>$null
        Write-Host "   Version: $version" -ForegroundColor Cyan
    } catch {
        Write-Host "⚠️  Docker CLI found but not responsive" -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ Docker CLI not found in PATH" -ForegroundColor Red
    Write-Host "   This is normal if Docker Desktop isn't running" -ForegroundColor Yellow
}

# Check if docker-compose is available
Write-Host ""
Write-Host "🔍 Checking Docker Compose availability..." -ForegroundColor Yellow

if (Test-Command "docker-compose") {
    Write-Host "✅ docker-compose command available" -ForegroundColor Green
} elseif (Test-Command "docker") {
    try {
        $composeVersion = docker compose version 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Docker Compose (integrated) available" -ForegroundColor Green
            Write-Host "   Version: $composeVersion" -ForegroundColor Cyan
        } else {
            Write-Host "❌ Docker Compose not available" -ForegroundColor Red
        }
    } catch {
        Write-Host "❌ Docker Compose not available" -ForegroundColor Red
    }
} else {
    Write-Host "❌ Docker Compose not available (Docker CLI not found)" -ForegroundColor Red
}

# Check Docker processes
Write-Host ""
Write-Host "🔍 Checking Docker processes..." -ForegroundColor Yellow

$dockerProcesses = Get-Process -Name "*docker*" -ErrorAction SilentlyContinue
if ($dockerProcesses) {
    Write-Host "✅ Docker processes found:" -ForegroundColor Green
    foreach ($proc in $dockerProcesses) {
        Write-Host "   - $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Cyan
    }
} else {
    Write-Host "❌ No Docker processes running" -ForegroundColor Red
    Write-Host "   Docker Desktop might not be started" -ForegroundColor Yellow
}

# Check VS Code Docker extension
Write-Host ""
Write-Host "🔍 Checking VS Code Docker extension..." -ForegroundColor Yellow
Write-Host "✅ Docker extension is installed (ms-azuretools.vscode-docker)" -ForegroundColor Green

# Try to start Docker Desktop if found
Write-Host ""
Write-Host "🚀 Attempting to start Docker Desktop..." -ForegroundColor Yellow

if ($dockerFound) {
    $dockerExePath = $dockerPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    try {
        Write-Host "   Starting Docker Desktop..." -ForegroundColor Cyan
        Start-Process -FilePath $dockerExePath -WindowStyle Hidden
        Write-Host "✅ Docker Desktop start command sent" -ForegroundColor Green
        Write-Host "   Please wait 30-60 seconds for Docker to initialize" -ForegroundColor Yellow
        Write-Host "   Then run this script again to verify" -ForegroundColor Yellow
    } catch {
        Write-Host "❌ Failed to start Docker Desktop: $($_.Exception.Message)" -ForegroundColor Red
    }
} else {
    Write-Host "❌ Cannot start Docker Desktop (not found)" -ForegroundColor Red
}

Write-Host ""
Write-Host "📋 Next Steps:" -ForegroundColor Cyan
Write-Host "1. Ensure Docker Desktop is installed and running" -ForegroundColor White
Write-Host "2. Wait for Docker to fully initialize (check system tray)" -ForegroundColor White
Write-Host "3. Run 'docker --version' to verify CLI access" -ForegroundColor White
Write-Host "4. Run 'docker compose build' to build your container" -ForegroundColor White
Write-Host "5. Use VS Code Docker extension panel to manage containers" -ForegroundColor White

Write-Host ""
Write-Host "Pro Tip: Use VS Code Command Palette (Ctrl+Shift+P) and type Docker" -ForegroundColor Green
Write-Host "to access Docker extension commands directly!" -ForegroundColor Green