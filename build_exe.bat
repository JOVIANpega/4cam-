@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   Splicing Check System - DYNAMIC VERSION BUILD
echo ===================================================
echo.

:: Extract version from main.py
for /f "usebackq tokens=*" %%I in (`powershell -NoProfile -Command "(Get-Content main.py | Select-String 'VERSION =').Split('\""')[1]"`) do set APP_VERSION=%%I

if "%APP_VERSION%"=="" (
    set APP_VERSION=Unknown
    echo [!] Could not detect version from main.py, using 'Unknown'
) else (
    echo [OK] Detected Version: %APP_VERSION%
)

set DIST_NAME=SplicingCheckSystem_V%APP_VERSION%
set DIST_PATH=dist\!DIST_NAME!

echo.
echo [1/3] Performance Optimization...
:: Using --onedir (Folder mode) for instant startup
set BUILD_MODE=--onedir
echo Defaulting to FOLDER MODE.

echo.
echo [2/3] Building Package...
pyinstaller %BUILD_MODE% --noconsole --clean ^
            --name "!DIST_NAME!" ^
            --hidden-import scipy.signal ^
            --collect-submodules scipy ^
            --collect-all ttkbootstrap ^
            --collect-all cv2 ^
            --collect-all PIL ^
            --exclude-module matplotlib ^
            --exclude-module notebook ^
            --exclude-module jedi ^
            main.py

echo.
echo [3/3] Deploying Assets...
echo [+] Copying MANUAL.html...
copy /Y "MANUAL.html" "!DIST_PATH!\"

echo [+] Copying pic folder...
xcopy /E /I /Y "pic" "!DIST_PATH!\pic"

echo.
echo [4/4] Finalizing...
rmdir /s /q build
del /q "!DIST_NAME!.spec"

echo.
echo ===================================================
echo   BUILD COMPLETE!
echo   Version: %APP_VERSION%
echo   Location: !DIST_PATH!
echo ===================================================
pause
