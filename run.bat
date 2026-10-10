@echo off
setlocal enabledelayedexpansion
title Blogger AI Agent

echo =====================================================================
echo                Starting Blogger AI Agent (Local Studio)
echo =====================================================================
echo.

REM Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in PATH.
    echo Please install Python 3.12+ from https://www.python.org/
    pause
    exit /b 1
)

REM Check or create virtual environment
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Creating 'venv'...
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [INFO] Installing required dependencies...
    venv\Scripts\pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

REM Check or copy .env
if not exist ".env" (
    echo [INFO] No .env file found. Creating .env from .env.example with Demo Mode enabled...
    copy .env.example .env >nul
)

REM Ensure data folder exists
if not exist "data" mkdir data

echo [INFO] Starting Blogger AI Agent server on http://127.0.0.1:8000 ...
echo [INFO] Press Ctrl+C in this window to stop the server anytime.
echo.

REM Open browser in 2 seconds
start "" timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000

REM Launch application
venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

pause
