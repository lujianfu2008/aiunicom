@echo off
chcp 65001 >nul
title Work Order Knowledge Base System V3
echo.
echo ============================================
echo      Work Order Knowledge Base V3
echo ============================================
echo.

echo [1/5] Checking Python...
python --version
if errorlevel 1 (
    echo [ERROR] Python not found, please install Python 3.8+
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)
echo [OK] Python is available
echo.

echo [2/5] Checking Redis...
python check_redis.py
if errorlevel 1 (
    echo [WARNING] Redis connection failed
    echo          Please ensure Redis Stack is running
    echo          host: 127.0.0.1, port: 6380
    echo.
    echo Continue anyway? (Y/N)
    choice /c YN /n
    if errorlevel 2 exit /b 1
)
echo.

echo [3/5] Checking dependencies...
python check_deps.py
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        echo.
        echo Press any key to exit...
        pause >nul
        exit /b 1
    )
)
echo [OK] Dependencies installed
echo.

echo [4/5] Checking config file...
if not exist config.ini (
    echo [ERROR] config.ini not found
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)
echo [OK] Config file exists
echo.

echo [5/5] Starting system...
echo.
echo ============================================
python query_tool.py
if errorlevel 1 (
    echo.
    echo [ERROR] Program failed to start
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

echo.
echo ============================================
echo      System exited
echo ============================================
echo.
echo Press any key to exit...
pause >nul
