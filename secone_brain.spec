# PyInstaller spec for the desktop app. Build (on Windows, with
# requirements-desktop.txt installed) via:
#
#   pyinstaller secone_brain.spec
#
# The result is a single dist/Secone Brain.exe - see README "Desktop app"
# for the full walkthrough, including first-run setup (.env, credentials.json)
# next to the exe.
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

# These libraries pick their implementation at runtime (plugins, lazy
# imports, etc.), so PyInstaller's static import scan misses pieces of them
# unless told to pull in every submodule explicitly.
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("anthropic")
    + collect_submodules("google_auth_oauthlib")
    + collect_submodules("googleapiclient")
)

a = Analysis(
    ["app_desktop.py"],
    pathex=[],
    binaries=[],
    # graph.html / voice.html etc. aren't Python - PyInstaller only bundles
    # code by default, so the static assets app/main.py serves need listing
    # here explicitly or the packaged exe would 404 on every page.
    datas=[("app/static", "app/static")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Secone Brain",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # No console window - this is a windowed desktop app, not a CLI tool.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
