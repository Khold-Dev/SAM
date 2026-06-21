#!/usr/bin/env python3
"""
Fix subprocess calls to work with PyInstaller bundles.
Remove cwd parameters from subprocess.Popen calls.
"""
import re

with open('voice_machine.py', 'r') as f:
    content = f.read()

# Replace all occurrences of "cwd=SAM_DIR," with ""
content = content.replace('cwd=SAM_DIR,\n', '')
content = content.replace('cwd=PIPER_DIR,\n', '')

with open('voice_machine.py', 'w') as f:
    f.write(content)

print("[OK] Fixed subprocess calls for PyInstaller compatibility")
