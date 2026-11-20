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
# Qt imports the Windows ICU API. A third-party ICU on PATH can shadow it
# with a different ABI when collected into PyInstaller's runtime directory.
a.binaries = [
    entry for entry in a.binaries
    if entry[0].lower() != 'icuuc.dll'
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PDF Master Pro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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

bundle = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='PDF Master Pro',
)
