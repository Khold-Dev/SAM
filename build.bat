@echo off
REM Build standalone KholdVoices.exe

echo Building Khold Voices...
echo.

REM Install dependencies
echo [1/3] Installing build tools...
python -m pip install --quiet pyinstaller pillow
if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

REM Convert PNG to ICO
echo [2/3] Converting PNG to ICO...
python build_setup.py
if errorlevel 1 (
    echo Error: Failed to convert PNG to ICO
    pause
    exit /b 1
)

REM Build EXE
echo [3/3] Building executable...
python -m PyInstaller voice_machine.spec --noconfirm --clean
if errorlevel 1 (
    echo Error: Failed to build executable
    pause
    exit /b 1
)

echo.
echo ✓ Build complete!
echo.
echo Your executable is ready at: dist\KholdVoices.exe
echo.
pause
