# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['PDF editor tool.py'],
    pathex=[],
    binaries=[],
    datas=[('bin', 'bin'), ('engine pdf.ico', '.')],
    hiddenimports=['win32com.client', 'pythoncom'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'scipy', 'matplotlib', 'pandas', 'kornia', 'onnxruntime', 'numba', 'sympy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PDF Master Pro V3.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['engine pdf.ico'],
)
