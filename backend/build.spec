# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# Collect all necessary data files
frontend_dist = os.path.join(SPECPATH, '..', 'frontend', 'dist')

# Bundle .skills/ (prompt skills) and .tools/ (function tools) so they ship with the exe
skills_dir = os.path.join(SPECPATH, '.skills')
tools_dir = os.path.join(SPECPATH, '.tools')

# Optional: Tesseract OCR engine (skip if not installed)
datas = [(frontend_dist, 'frontend/dist')]
if os.path.isdir(skills_dir):
    datas.append((skills_dir, '.skills'))
if os.path.isdir(tools_dir):
    datas.append((tools_dir, '.tools'))

# Search for Tesseract in known locations
tesseract_candidates = [
    os.path.join(os.environ.get('PROGRAMFILES', 'C:/Program Files'), 'Tesseract-OCR'),
    os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)'), 'Tesseract-OCR'),
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Tesseract-OCR'),
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TRAE SOLO CN', 'ModularData', 'ai-agent', 'vm', 'tools', 'app', 'tesseract'),
]

tesseract_dir = None
for d in tesseract_candidates:
    exe = os.path.join(d, 'tesseract.exe')
    if os.path.exists(exe):
        tesseract_dir = d
        break

if tesseract_dir:
    # tesseract.exe → tesseract/  (匹配 ocr_service.py 中的路径)
    datas.append((os.path.join(tesseract_dir, 'tesseract.exe'), 'tesseract'))
    # 仅打包中文 + 英文语言包
    for lang in ('chi_sim.traineddata', 'eng.traineddata'):
        src = os.path.join(tesseract_dir, 'tessdata', lang)
        if os.path.exists(src):
            datas.append((src, 'tessdata'))
    print(f"Tesseract found at {tesseract_dir}, bundled chi_sim+eng.")
else:
    print("Tesseract not found, building without OCR support.")

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'uvicorn',
        'sqlalchemy',
        'openai',
        'pytesseract',
        'PIL',
        'PIL._imaging',
        'duckduckgo_search',
        'deep_translator',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'cv2',
        'cryptography',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='deepseek-agent-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
