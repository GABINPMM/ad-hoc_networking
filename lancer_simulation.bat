@echo off
chcp 65001 >nul
title Swarm Robotics ^& DTN Simulator - Launcher
cd /d "%~dp0"

set "PY312=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if exist "%PY312%" (
    echo [INFO] Lancement avec Python 3.12 ^(%PY312%^)
    "%PY312%" main.py
) else (
    echo [INFO] Lancement avec le Python du systeme...
    python main.py
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERREUR] La simulation s'est arretee avec un code d'erreur.
    pause
)

