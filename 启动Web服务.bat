@echo off
chcp 65001 >nul
title Knowledge Base Web Server
color 0A

echo.
echo ========================================
echo   Knowledge Base Web Server
echo ========================================
echo.
echo [Features]
echo   - Smart Search: Vector semantic search
echo   - Content Search: Exact keyword match
echo   - Smart QA: AI analysis + vector search
echo   - File View: View full file content
echo.
echo [Access URL]
echo   http://localhost:5000
echo.
echo [Tips]
echo   - Press Ctrl+C to stop service
echo   - Closing this window will also stop service
echo.
echo ========================================
echo.

:START
python api_server.py
if %errorlevel% neq 0 (
    echo.
    echo [Error] Service startup failed, error code: %errorlevel%
    echo.
    echo [Possible Causes]
    echo   1. Python not installed or not in PATH
    echo   2. Port 5000 already in use
    echo   3. Dependencies not installed
    echo.
    echo [Solutions]
    echo   1. Check Python: python --version
    echo   2. Check port: netstat -ano ^| findstr :5000
    echo   3. Install dependencies: pip install -r requirements.txt
    echo.
    pause
)
