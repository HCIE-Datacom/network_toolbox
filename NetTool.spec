# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('data', 'data'), ('templates', 'templates'), ('image_icon.png', '.')]
binaries = []
hiddenimports = ['queue', 'pyftpdlib', 'paramiko', 'ping3', 'PySide6']
tmp_ret = collect_all('modules')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['network_toolbox.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='NetTool',
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
    icon=['NetTool.app/Contents/Resources/AppIcon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NetTool',
)
app = BUNDLE(
    coll,
    name='NetTool.app',
    icon='NetTool.app/Contents/Resources/AppIcon.icns',
    bundle_identifier='com.tangwenbo.networktoolbox',
    version='V100R008C00SPC600',
    info_plist={
        'CFBundleDisplayName': 'NetTool',
        'CFBundleShortVersionString': 'V100R008C00SPC600',
        'CFBundleVersion': 'V100R008C00SPC600',
        'NetToolVersion': 'V100R008C00SPC600',
        'NSHighResolutionCapable': True,
    },
)
