# -*- coding: utf-8 -*-
# Work Order Knowledge Base System V3 - PowerShell Startup Script

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "     Work Order Knowledge Base V3" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "   $pythonVersion" -ForegroundColor Green
    Write-Host "   [OK] Python is available" -ForegroundColor Green
} catch {
    Write-Host "   [ERROR] Python not found, please install Python 3.8+" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Check Redis
Write-Host "[2/5] Checking Redis..." -ForegroundColor Yellow
$redisCheck = python check_redis.py 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   $redisCheck" -ForegroundColor Green
} else {
    Write-Host "   [WARNING] Redis connection failed" -ForegroundColor Yellow
    Write-Host "              Please ensure Redis Stack is running" -ForegroundColor Yellow
    Write-Host "              host: 127.0.0.1, port: 6380" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "Continue anyway? (Y/N)"
    if ($continue -ne "Y") {
        exit 1
    }
}
Write-Host ""

# Check dependencies
Write-Host "[3/5] Checking dependencies..." -ForegroundColor Yellow
$depsCheck = python check_deps.py 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   $depsCheck" -ForegroundColor Green
    Write-Host "   [OK] Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "   [INFO] Installing dependencies..." -ForegroundColor Cyan
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   [ERROR] Failed to install dependencies" -ForegroundColor Red
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 1
    }
}
Write-Host ""

# Check config file
Write-Host "[4/5] Checking config file..." -ForegroundColor Yellow
if (Test-Path "config.ini") {
    Write-Host "   [OK] Config file exists" -ForegroundColor Green
} else {
    Write-Host "   [ERROR] config.ini not found" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Start system
Write-Host "[5/5] Starting system..." -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
python query_tool.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "   [ERROR] Program failed to start" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "     System exited" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
