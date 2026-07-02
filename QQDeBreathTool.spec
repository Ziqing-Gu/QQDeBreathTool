# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('breath_frame_model.joblib', '.'), ('debreath_icon.ico', '.')]
binaries = []
hiddenimports = [
    'debreath_tool_app',
    'scipy.ndimage',
    'scipy.signal',
    'sklearn.ensemble._hist_gradient_boosting.binning',
    'sklearn.ensemble._hist_gradient_boosting.common',
    'sklearn.ensemble._hist_gradient_boosting.gradient_boosting',
    'sklearn.ensemble._hist_gradient_boosting.grower',
    'sklearn.ensemble._hist_gradient_boosting.histogram',
    'sklearn.ensemble._hist_gradient_boosting.predictor',
    'sklearn.ensemble._hist_gradient_boosting.splitting',
    'sklearn.pipeline',
    'sklearn.preprocessing._data',
    'sklearn.utils._openmp_helpers',
]
for package in ('sounddevice', 'soundfile'):
    tmp_ret = collect_all(package)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]


a = Analysis(
    ['debreath_tool_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchaudio', 'torchvision', 'pandas', 'pyarrow', 'matplotlib', 'numba', 'llvmlite', 'h5py', 'PIL', 'IPython', 'tensorflow'],
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
