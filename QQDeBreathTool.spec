# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['debreath_tool_app.py'],
    pathex=[],
    binaries=[],
    datas=[('breath_frame_model.joblib', '.'), ('debreath_icon.ico', '.')],
    hiddenimports=[
        'debreath_tool_app',
        'numpy',
        'scipy',
        'miniaudio',
        'soundfile',
        'sklearn',
        'joblib',
        'PIL',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='QQDeBreathTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['debreath_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='QQDeBreathTool',
)
app = BUNDLE(
    coll,
    name='QQDeBreathTool.app',
    icon='debreath_icon.ico',
    bundle_identifier=None,
)
