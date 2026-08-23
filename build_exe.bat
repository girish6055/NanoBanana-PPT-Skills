@echo off
REM Build CCTVAnalyticsManager.exe on Windows.
REM Requires Python 3.9+ from python.org (the installer includes tkinter).

setlocal
cd /d "%~dp0"

echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on PATH. Install it from https://python.org
    echo        and tick "Add python.exe to PATH" during setup.
    exit /b 1
)

echo [2/3] Installing PyInstaller...
python -m pip install --upgrade pip >nul
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: could not install PyInstaller.
    exit /b 1
)

echo [3/3] Building the executable...
python -m PyInstaller --clean --noconfirm CCTVAnalyticsManager.spec
if errorlevel 1 (
    echo ERROR: build failed.
    exit /b 1
)

echo.
echo Done. Your executable is here:
echo    %cd%\dist\CCTVAnalyticsManager.exe
endlocal
