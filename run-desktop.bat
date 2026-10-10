@echo off
setlocal enabledelayedexpansion
title Bloggers Desktop Studio

echo =====================================================================
echo                Starting Bloggers Desktop Studio
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
    echo [INFO] Installing required Python dependencies...
    venv\Scripts\pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install Python dependencies.
        pause
        exit /b 1
    )
)

REM Check or copy .env
if not exist ".env" (
    echo [INFO] No .env file found. Creating .env from .env.example...
    copy .env.example .env >nul
)

REM Ensure data folder exists
if not exist "data" mkdir data

REM Check if node_modules exists
if not exist "node_modules" (
    echo [INFO] Installing Node.js & Electron dependencies...
    call npm install
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install npm dependencies.
        pause
        exit /b 1
    )
)

echo [INFO] Launching Bloggers Desktop App...
call npm start
