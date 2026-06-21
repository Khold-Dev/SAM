# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    ['voice_machine.py'],
    pathex=[],
    binaries=[
        ('SAM\\sam.exe', 'SAM'),
        ('SAM\\SDL.dll', 'SAM'),
        ('piper\\piper\\piper.exe', 'piper/piper'),
    ],
    datas=[
        ('start.ico', '.'),
        ('piper\\voices', 'piper/voices'),
        ('SAM', 'SAM'),
        ('piper', 'piper'),
    ],
    hiddenimports=['customtkinter', 'numpy', 'winsound'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='KholdVoices',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='start.ico',
)
