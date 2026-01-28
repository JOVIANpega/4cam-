@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   Splicing Check System - HIGH SPEED EXE BUILD
echo ===================================================
echo.

echo [1/3] Performance Optimization...
:: Using --onedir (Folder mode) for instant startup
set BUILD_MODE=--onedir
echo Defaulting to FOLDER MODE.

echo.
echo [2/3] Building Package...
:: Added more robust collection for cv2 and PIL
pyinstaller %BUILD_MODE% --noconsole --clean ^
            --name "SplicingCheckSystem_V1" ^
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
echo [3/3] Finalizing...
rmdir /s /q build
del /q SplicingCheckSystem_V1.spec

echo.
echo ===================================================
echo   BUILD COMPLETE!
echo   Location: dist\SplicingCheckSystem_V1
echo ===================================================
pause
