@echo off
echo ===================================================
echo   Splicing Check System - EXE Build Script
echo ===================================================
echo.

echo [1/3] Checking dependencies...
pip install pyinstaller ttkbootstrap Pillow opencv-python numpy scipy

echo.
echo [2/3] Building EXE...
echo This may take a few minutes. Please wait...

:: PyInstaller Command:
:: --onefile: Bundle everything into a single EXE
:: --noconsole: Hide the terminal window when running the GUI
:: --name: Specify the name of the output EXE
:: --clean: Clean PyInstaller cache before building
:: --hidden-import: Ensure scipy.signal is included as it's often missed
pyinstaller --noconsole --onefile --clean ^
            --name "SplicingCheckSystem_V1" ^
            --hidden-import scipy.signal ^
            main.py

echo.
echo [3/3] Cleaning up temporary files...
:: Optional: Keep the 'dist' folder but remove build/spec
rmdir /s /q build
del /q SplicingCheckSystem_V1.spec

echo.
echo ===================================================
echo   BUILD COMPLETE!
echo   Your EXE is located in the 'dist' folder.
echo ===================================================
pause
