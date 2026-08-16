@echo off
setlocal enableextensions
title Fusion to Blender Bridge - Installer

REM ── Folder that contains this script = the add-in folder ─────────────────────
set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
for %%I in ("%SRC%") do set "ADDIN_NAME=%%~nxI"

set "ADDINS=%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns"
set "DEST=%ADDINS%\%ADDIN_NAME%"

echo.
echo   Fusion to Blender Bridge - one-click installer
echo   ----------------------------------------------
echo   Copying the add-in into Fusion 360's AddIns folder:
echo     From: %SRC%
echo     To:   %DEST%
echo.

if not exist "%ADDINS%\" mkdir "%ADDINS%"

xcopy "%SRC%" "%DEST%\" /E /I /Y /Q >nul
if errorlevel 1 (
    echo   [!] Copy failed.
    echo       If Fusion 360 is open, close it ^(or Stop the add-in^) and run this again.
    echo.
    pause
    exit /b 1
)

echo   [OK] Installed.
echo.
echo   Next steps in Fusion 360:
echo     1) Open Fusion 360
echo     2) Utilities ^(or Tools^) ^> Add-Ins ^> "Scripts and Add-Ins"
echo     3) Open the Add-Ins tab, select "%ADDIN_NAME%", click Run
echo.
echo   The bridge server then starts automatically. In Blender, just press Sync.
echo.
pause
