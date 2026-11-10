@echo off
chcp 65001 >nul
title Configurateur Simulation Boids ^& DTN
cd /d "%~dp0"

set "PY312=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if exist "%PY312%" (
    "%PY312%" configurateur_gui.py
) else (
    python configurateur_gui.py
)

