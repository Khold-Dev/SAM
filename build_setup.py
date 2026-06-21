#!/usr/bin/env python3
"""
Convert PNG to ICO and create PyInstaller spec file
"""
import os
from PIL import Image

# Convert PNG to ICO
png_path = "32x32KholdDev.png"
ico_path = "start.ico"

if os.path.exists(png_path):
    img = Image.open(png_path)
    # Ensure it's at least 32x32
    if img.size[0] >= 32 and img.size[1] >= 32:
        img_resized = img.resize((256, 256), Image.Resampling.LANCZOS)
        img_resized.save(ico_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
        print(f"[OK] Created {ico_path} from {png_path}")
    else:
        print(f"[ERROR] Image too small: {img.size}")
else:
    print(f"[ERROR] {png_path} not found")

print("\nNext steps:")
print("1. Run: python -m pip install pyinstaller")
print("2. Run: pyinstaller voice_machine.spec")
