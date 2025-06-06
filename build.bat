@echo off
chcp 65001 >nul
color 0A

echo =====================================
echo    StreamCap Build Tool
echo =====================================
echo.
echo Select build mode:
echo 1: GUI mode (no console window)
echo 2: Console mode (with console window)
echo.
set /p mode="Enter option (1/2): "

if "%mode%"=="1" (
    set "spec_file=main_gui.spec"
    set "mode_name=GUI mode"
) else if "%mode%"=="2" (
    set "spec_file=main_console.spec"
    set "mode_name=Console mode"
) else (
    echo Invalid option, using Console mode
    set "spec_file=main_console.spec"
    set "mode_name=Console mode"
    timeout /t 3 >nul
)

echo.
echo =====================================
echo    Building StreamCap...
echo    Mode: %mode_name%
echo =====================================

REM Check icon file
if not exist assets\icon.ico (
    echo [Warning] Icon file not found: assets\icon.ico
    echo Using default icon
    timeout /t 3 >nul
)

REM Install dependencies
echo [Step 1] Installing dependencies...
pip install -r requirements.txt

REM Clean previous build
echo [Step 2] Cleaning build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build with selected spec
echo [Step 3] Building...
echo - Using %mode_name%
echo - Using custom icon
pyinstaller "%spec_file%"

REM Copy required folders
echo [Step 4] Copying folders...
xcopy /E /I /Y assets dist\StreamCap\assets
xcopy /E /I /Y config dist\StreamCap\config
xcopy /E /I /Y downloads dist\StreamCap\downloads
xcopy /E /I /Y locales dist\StreamCap\locales
xcopy /E /I /Y logs dist\StreamCap\logs

echo =====================================
echo    Build complete! 
echo    Program is in dist/StreamCap directory
echo    Mode: %mode_name%
if "%mode%"=="1" echo    Memory cleanup logs: logs/memory_clean.log
echo =====================================
pause 