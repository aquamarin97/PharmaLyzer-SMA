# PharmaLyzerSMA.spec
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

crypto_datas, crypto_binaries, crypto_hiddenimports = collect_all('cryptography')
sklearn_datas, sklearn_binaries, sklearn_hiddenimports = collect_all('sklearn')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        *crypto_binaries,
        *sklearn_binaries,
    ],
    datas=[
        ('app/i18n/translations', 'app/i18n/translations'),
        ('assets/appicon.png', 'assets'),
        ('assets/appicon.ico', 'assets'),
        ('assets/pharmalinelogo.svg', 'assets'),
        *crypto_datas,
        *sklearn_datas,
    ],
    hiddenimports=[
        'PyQt5.sip',
        'PyQt5.QtSvg',
        'cryptography',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.asymmetric',
        'cryptography.hazmat.primitives.asymmetric.padding',
        'cryptography.hazmat.primitives.hashes',
        'cryptography.hazmat.backends',
        'cryptography.hazmat.backends.openssl',
        'cryptography.hazmat.backends.openssl.backend',
        'sklearn',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors.typedefs',
        'sklearn.neighbors.quad_tree',
        'sklearn.tree._utils',
        *crypto_hiddenimports,
        *sklearn_hiddenimports,
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='PharmaLyzerSMA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,   # ← UPX kapalı (flash önleme)
    console=False,
    icon='assets/appicon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,   # ← UPX kapalı
    name='PharmaLyzerSMA',
)