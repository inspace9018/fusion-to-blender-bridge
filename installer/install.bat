@echo off
REM ============================================================================
REM  Fusion to Blender Lite - Windows Installer
REM ----------------------------------------------------------------------------
REM  WHAT THIS SCRIPT DOES (plain language):
REM    It sets up the bridge that syncs Fusion 360 models into Blender by
REM    copying TWO add-on folders into the right places:
REM      1) Fusion 360 add-in -> %APPDATA%\Autodesk\...\API\AddIns
REM      2) Blender add-on    -> %APPDATA%\Blender Foundation\Blender\<ver>\scripts\addons
REM    It does NOT touch anything else on your PC, does NOT need the internet,
REM    and does NOT require administrator rights (everything goes in your user
REM    profile). Uninstall removes ONLY those two named folders.
REM
REM  It reads the two add-on folders that sit next to this script:
REM      fusion_to_blender_addon_fusion\   and   fusion_to_blender_addon_blender\
REM ============================================================================
setlocal enableextensions enabledelayedexpansion
title Fusion to Blender Lite - Installer
color 0F

set "ROOT=%~dp0"
set "FUSION_NAME=fusion_to_blender_addon_fusion"
set "BLENDER_NAME=fusion_to_blender_addon_blender"
set "FUSION_SRC=%ROOT%%FUSION_NAME%"
set "BLENDER_SRC=%ROOT%%BLENDER_NAME%"

REM Bridge Pro bundle: the same installer serves the paid download, which
REM carries a third folder next to these two. Absent in the free bundle, and
REM then everything below simply skips it.
set "PRO_NAME=bridge_pro"
set "PRO_SRC=%ROOT%%PRO_NAME%"
set "HAS_PRO="
if exist "%PRO_SRC%\" set "HAS_PRO=1"
if defined HAS_PRO title Bridge Pro - Installer

set "FUSION_ADDINS=%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns"
set "FUSION_DEST=%FUSION_ADDINS%\%FUSION_NAME%"
set "BLENDER_BASE=%APPDATA%\Blender Foundation\Blender"

REM Optional non-interactive mode (for scripted/silent installs):
REM     install.bat install     install.bat update     install.bat uninstall
set "MODE="
if /i "%~1"=="install"   set "MODE=install"
if /i "%~1"=="update"    set "MODE=install"
if /i "%~1"=="repair"    set "MODE=install"
if /i "%~1"=="uninstall" set "MODE=uninstall"
if defined MODE goto %MODE%

:menu
cls
echo.
echo  ========================================================
if defined HAS_PRO (
    echo    Fusion to Blender Bridge  -  Installer
) else (
    echo    Fusion to Blender Lite  -  Installer
)
echo  ========================================================
echo.
echo    This sets up the bridge that brings your Fusion 360
echo    models into Blender. It installs TWO parts:
echo.
echo      [1] Fusion 360 add-in
if defined HAS_PRO (
    echo      [2] Blender add-on  ^(Bridge Pro - the sync is inside it^)
) else (
    echo      [2] Blender add-on
)
echo.
echo    BEFORE YOU START:
echo      * Please CLOSE Fusion 360 and Blender first
echo        (open files can block the copy).
echo.
echo    Safe to run anytime: nothing else on your PC is
echo    changed, and Uninstall removes only these two parts.
echo.
echo  --------------------------------------------------------
echo    What would you like to do?
echo.
echo      [I]  Install
echo      [U]  Update / Repair   (reinstall over existing)
echo      [X]  Uninstall         (remove both parts)
echo      [Q]  Quit
echo  --------------------------------------------------------
echo.
set "CHOICE="
set /p "CHOICE=   Choose (I/U/X/Q): "

if /i "%CHOICE%"=="I" goto install
if /i "%CHOICE%"=="U" goto install
if /i "%CHOICE%"=="X" goto uninstall
if /i "%CHOICE%"=="Q" goto end
goto menu

REM ----------------------------------------------------------------------------
:install
cls
echo.
if defined HAS_PRO (
    echo   Installing Fusion to Blender Bridge...
) else (
    echo   Installing Fusion to Blender Lite...
)
echo.

REM --- Sanity: the two source folders must sit next to this script ----------
if not exist "%FUSION_SRC%\" (
    echo   [!] Missing folder next to this installer: %FUSION_NAME%
    echo       Re-extract the downloaded ZIP and run install.bat from inside it.
    goto done
)
REM  The paid bundle has no free Blender folder -- bridge_pro contains it.
if not defined HAS_PRO if not exist "%BLENDER_SRC%\" (
    echo   [!] Missing folder next to this installer: %BLENDER_NAME%
    echo       Re-extract the downloaded ZIP and run install.bat from inside it.
    goto done
)

REM --- Part 1: Fusion 360 add-in -------------------------------------------
echo   [1/2] Fusion 360 add-in
if not exist "%FUSION_ADDINS%\" mkdir "%FUSION_ADDINS%"
call :clean_replace "%FUSION_SRC%" "%FUSION_DEST%" "%FUSION_NAME%"
if errorlevel 1 ( echo        ^-^> FAILED  & set "FAIL=1" ) else ( echo        ^-^> OK  ^(%FUSION_DEST%^) )

REM --- Part 2: Blender add-on (every detected version) ----------------------
REM  Bridge Pro CONTAINS the free add-on, so the paid path removes an older
REM  free install rather than adding one. With both present every operator id
REM  is claimed twice: two panels, and every body synced twice.
if defined HAS_PRO goto blender_pro

echo   [2/2] Blender add-on
set "BL_COUNT=0"
if exist "%BLENDER_BASE%\" (
    for /d %%V in ("%BLENDER_BASE%\*") do (
        set "DEST=%%~fV\scripts\addons\%BLENDER_NAME%"
        if not exist "%%~fV\scripts\addons\" mkdir "%%~fV\scripts\addons"
        call :clean_replace "%BLENDER_SRC%" "!DEST!" "%BLENDER_NAME%"
        REM Judge by the outcome, not the errorlevel. Inside a for-block the
        REM errorlevel from a called label is not reliable -- this said FAILED
        REM on installs that had in fact worked.
        if exist "!DEST!\__init__.py" ( echo        ^-^> %%~nxV  OK & set /a BL_COUNT+=1 ) else ( echo        ^-^> %%~nxV  FAILED & set "FAIL=1" )
    )
)
if "%BL_COUNT%"=="0" (
    echo        ^-^> No Blender user folder found automatically.
    echo           Open Blender once ^(so it creates its folder^), or install the
    echo           add-on via Blender: Edit ^> Preferences ^> Add-ons ^> Install from Disk,
    echo           pointing at the %BLENDER_NAME% folder.
)

goto blender_done

:blender_pro
echo   [2/2] Blender add-on ^(Bridge Pro^)
if exist "%BLENDER_BASE%\" (
    for /d %%V in ("%BLENDER_BASE%\*") do (
        set "OLD=%%~fV\scripts\addons\%BLENDER_NAME%"
        if exist "!OLD!\" (
            call :remove_dir "!OLD!" "%BLENDER_NAME%"
            echo        ^-^> %%~nxV  removed the free add-on ^(Pro contains it^)
        )
    )
)

REM --- Bridge Pro ----------------------------------------------------------
if defined HAS_PRO (
    set "PRO_COUNT=0"
    if exist "%BLENDER_BASE%\" (
        for /d %%V in ("%BLENDER_BASE%\*") do (
            set "PDEST=%%~fV\scripts\addons\%PRO_NAME%"
            if not exist "%%~fV\scripts\addons\" mkdir "%%~fV\scripts\addons"
            call :clean_replace "%PRO_SRC%" "!PDEST!" "%PRO_NAME%"
            if exist "!PDEST!\__init__.py" ( echo        ^-^> %%~nxV  OK & set /a PRO_COUNT+=1 ) else ( echo        ^-^> %%~nxV  FAILED & set "FAIL=1" )
        )
    )
    if "!PRO_COUNT!"=="0" (
        echo        ^-^> No Blender user folder found automatically.
        echo           Install via Blender: Edit ^> Preferences ^> Add-ons ^> Install from Disk,
        echo           pointing at the %PRO_NAME% folder.
    )
)

:blender_done
echo.
if defined FAIL (
    echo   [!] Finished with some errors. If Fusion/Blender were open, close them and run Update/Repair.
) else (
    echo   [OK] Done.
)
echo.
echo   NEXT STEPS:
echo     - Fusion 360:  Utilities ^(or Tools^) ^> Add-Ins ^> "Scripts and Add-Ins"
echo                    ^> Add-Ins tab ^> select "%FUSION_NAME%" ^> Run
if defined HAS_PRO (
    echo     - Blender:     Edit ^> Preferences ^> Add-ons ^> enable
    echo                    "Fusion to Blender Bridge"  ^(then restart Blender^)
) else (
    echo     - Blender:     Edit ^> Preferences ^> Add-ons ^> enable
    echo                    "Fusion to Blender Lite"  ^(then restart Blender^)
)
echo     - Then in Blender just press Sync. Connection is automatic.
echo.
if defined MODE goto end
goto done

REM ----------------------------------------------------------------------------
:uninstall
cls
echo.
echo   Uninstall - this removes ONLY these folders:
echo     - %FUSION_DEST%
echo     - %BLENDER_BASE%\^<version^>\scripts\addons\%BLENDER_NAME%
if defined HAS_PRO echo     - %BLENDER_BASE%\^<version^>\scripts\addons\%PRO_NAME%
echo.
if not defined MODE (
    set "OK="
    if defined HAS_PRO ( set /p "OK=   Remove Fusion to Blender Bridge? (Y/N): " ) else ( set /p "OK=   Remove Fusion to Blender Lite? (Y/N): " )
    if /i not "!OK!"=="Y" goto menu
)

echo.
echo   [1/2] Fusion 360 add-in
call :remove_dir "%FUSION_DEST%" "%FUSION_NAME%"
if errorlevel 1 ( echo        ^-^> not found / nothing to remove ) else ( echo        ^-^> removed )

echo   [2/2] Blender add-ons
set "BL_RM=0"
if exist "%BLENDER_BASE%\" (
    for /d %%V in ("%BLENDER_BASE%\*") do (
        set "DEST=%%~fV\scripts\addons\%BLENDER_NAME%"
        if exist "!DEST!\" (
            call :remove_dir "!DEST!" "%BLENDER_NAME%"
            if not errorlevel 1 ( echo        ^-^> %%~nxV  removed & set /a BL_RM+=1 )
        )
    )
)
if "%BL_RM%"=="0" echo        ^-^> none found

if defined HAS_PRO (
    echo        Bridge Pro
    set "PRO_RM=0"
    if exist "%BLENDER_BASE%\" (
        for /d %%V in ("%BLENDER_BASE%\*") do (
            set "PDEST=%%~fV\scripts\addons\%PRO_NAME%"
            if exist "!PDEST!\" (
                call :remove_dir "!PDEST!" "%PRO_NAME%"
                if not errorlevel 1 ( echo        ^-^> %%~nxV  removed & set /a PRO_RM+=1 )
            )
        )
    )
    if "!PRO_RM!"=="0" echo        ^-^> none found
)
echo.
echo   [OK] Uninstall complete. ^(Disable the add-on in Blender if it is still listed.^)
echo.
if defined MODE goto end
goto done

REM ----------------------------------------------------------------------------
REM  :clean_replace  SRC  DEST  EXPECTED_NAME
REM  Remove DEST (if it's the expected named folder) then copy SRC into it, so
REM  no stale files survive an update. Returns errorlevel 1 on failure.
:clean_replace
set "_SRC=%~1"
set "_DEST=%~2"
set "_NAME=%~3"
REM Guard: never delete a path that doesn't end with the expected add-on name.
for %%P in ("%_DEST%") do if /i not "%%~nxP"=="%_NAME%" exit /b 1
if exist "%_DEST%\" rmdir /s /q "%_DEST%" 2>nul
xcopy "%_SRC%" "%_DEST%\" /E /I /Y /Q >nul
if errorlevel 1 exit /b 1
exit /b 0

REM  :remove_dir  DEST  EXPECTED_NAME  -> safe rmdir guarded by folder name
:remove_dir
set "_DEST=%~1"
set "_NAME=%~2"
for %%P in ("%_DEST%") do if /i not "%%~nxP"=="%_NAME%" exit /b 1
if not exist "%_DEST%\" exit /b 1
rmdir /s /q "%_DEST%" 2>nul
if exist "%_DEST%\" exit /b 1
exit /b 0

REM ----------------------------------------------------------------------------
:done
echo.
pause
goto menu

:end
endlocal
