@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3 is required. Install it from https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating the local Python environment...
    python -m venv .venv || goto :error
)

echo Installing build requirements...
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller pillow || goto :error

echo Creating the application icon...
".venv\Scripts\python.exe" build_setup.py || goto :error

echo Building Khold Voices...
".venv\Scripts\python.exe" -m PyInstaller voice_machine.spec --noconfirm --clean || goto :error

echo.
echo Build complete: dist\KholdVoices.exe
pause
exit /b 0

:error
echo.
echo Build failed. Check the error above and try again.
pause
exit /b 1
