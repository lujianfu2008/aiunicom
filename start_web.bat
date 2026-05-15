@echo off
chcp 65001 >nul
echo ========================================
echo   知识库查询系统 - Web服务
echo ========================================
echo.
echo 正在启动Web服务器...
echo.
python api_server.py
pause
