@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3 is required. Install it from https://www.python.org/downloads/
        pause
        exit /b 1
    )

    echo Setting up Khold Voices...
    python -m venv .venv || goto :error
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)

start "" ".venv\Scripts\pythonw.exe" voice_machine.py
exit /b 0

:error
echo Setup failed. Check the error above and try again.
pause
exit /b 1
