@echo off
chcp 65001 >nul
echo ==========================================
echo   Belarusian Railway Ticket Bot (BZHd)
echo ==========================================

if not exist .env (
    echo [ERROR] File .env not found!
    echo Create it from .env.example
    pause
    exit /b 1
)

echo Starting bot...
python -m bot.main

if errorlevel 1 (
    echo [ERROR] Bot stopped with error!
    pause
)
