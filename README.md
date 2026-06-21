# Khold Voices

Khold Voices is a Windows desktop text-to-speech app combining the retro SAM voice engine with Piper neural voices.

## Requirements

- Windows 10 or 11 (64-bit)
- Python 3.10 or newer from [python.org](https://www.python.org/downloads/)
- Internet access for the first setup

The SAM and Piper executables and voice models are included in the repository.

## Run after cloning

```bat
git clone https://github.com/Khold-Dev/SAM.git
cd SAM
run.bat
```

The first run creates `.venv`, installs the required packages, and launches the app. Later runs start immediately. If `requirements.txt` changes, delete `.venv` and run `run.bat` again.

## Build the standalone app

Double-click `build.bat`. It sets up everything it needs and creates `dist\KholdVoices.exe`. Open that file to run the finished app without Python.

The first build requires internet access and can take several minutes. The `build` and `dist` directories are generated locally and are not committed.

## Repository layout

- `voice_machine.py` - desktop application
- `SAM/` - SAM executable and runtime library
- `piper/piper/` - Piper executable and runtime data
- `piper/voices/` - bundled ONNX voice models
- `src/` - SAM C source
- `legacyreadmeforsam.md` - original SAM documentation and license notes

## Distribution note

This repository contains third-party SAM, Piper, and voice-model files. Review their respective license terms before redistributing the application or a packaged executable.
