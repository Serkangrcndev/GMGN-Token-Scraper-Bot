@echo off
chcp 65001 >nul
title GMGN ETH Telegram Bot

cd /d "%~dp0gmgn_scraper"

echo ========================================
echo   GMGN ETH Telegram Bot
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$existing = Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','python3.exe','py.exe') -and $_.CommandLine -like '*main.py*' }; if ($existing) { Write-Host '[!] Bot zaten calisiyor. Cakisma olmamasi icin yeni kopya acilmadi.' -ForegroundColor Yellow; $existing | Select-Object ProcessId,Name,CommandLine | Format-Table -AutoSize; exit 1 }"

if errorlevel 1 (
    echo.
    echo Eski bot penceresini kapatin ya da gorev yoneticisinden python/py main.py surecini durdurun.
    echo Sonra bu dosyayi tekrar calistirin.
    echo.
    pause
    exit /b 1
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

where py >nul 2>nul
if %errorlevel%==0 (
    py main.py
) else (
    python main.py
)

echo.
echo Bot kapandi.
pause
