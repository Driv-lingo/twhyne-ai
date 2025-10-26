# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/leverncurrie/Downloads/SNF_AI_Demo/clean-windsurf/snf_ai_windows_main.py'],
    pathex=[],
    binaries=[],
    datas=[('backend', 'backend'), ('models/.gitkeep', 'models'), ('uploads/.gitkeep', 'uploads')],
    hiddenimports=['flask', 'flask_cors', 'PIL', 'numpy', 'requests'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'pandas'],
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
    name='SNF-AI-Windsurf',
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
