@echo off
chcp 65001 >nul
title Compilation en .EXE autonome (PyInstaller)
cd /d "%~dp0"

set "PY312=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if exist "%PY312%" (
    set "PY_CMD=%PY312%"
) else (
    set "PY_CMD=python"
)

echo [1/2] Verification / Installation de PyInstaller...
"%PY_CMD%" -m pip install pyinstaller pygame

echo.
echo [2/2] Generation de l'executable autonome SwarmDTN_Simulator.exe...
"%PY_CMD%" -m PyInstaller --noconfirm --onefile --windowed --name "SwarmDTN_Simulator" swarm_dtn_simulation.py

echo.
if exist "dist\SwarmDTN_Simulator.exe" (
    copy /Y "dist\SwarmDTN_Simulator.exe" "SwarmDTN_Simulator.exe" >nul
    echo [SUCCES] L'executable "SwarmDTN_Simulator.exe" a ete cree a la racine du dossier !
) else (
    echo [ERREUR] La compilation a echoue.
)
pause

