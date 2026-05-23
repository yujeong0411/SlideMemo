# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

litellm_datas, litellm_binaries, litellm_hiddenimports = collect_all('litellm')
tiktoken_datas, tiktoken_binaries, tiktoken_hiddenimports = collect_all('tiktoken')
tiktoken_ext_datas, tiktoken_ext_binaries, tiktoken_ext_hiddenimports = collect_all('tiktoken_ext')

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=litellm_binaries + tiktoken_binaries + tiktoken_ext_binaries,
    datas=[('logo.ico', '.'), ('logo.png', '.'), ('assets', 'assets')] + litellm_datas + tiktoken_datas + tiktoken_ext_datas,
    hiddenimports=['keyring.backends', 'keyring.backends.Windows', 'tiktoken_ext', 'tiktoken_ext.openai_public'] + litellm_hiddenimports + tiktoken_hiddenimports + tiktoken_ext_hiddenimports,
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
    name='SlideMemo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SlideMemo',
)
