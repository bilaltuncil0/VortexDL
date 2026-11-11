# -*- mode: python ; coding: utf-8 -*-
"""Cross-platform PyInstaller entry point for VortexDL."""
from pathlib import Path
import sys

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
)

ROOT = Path(SPECPATH).resolve()

datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "locales"), "locales"),
]
root_icon = ROOT / "icon.png"
if root_icon.exists():
    datas.append((str(root_icon), "."))

binaries = []
hiddenimports = [
    # Legacy top-level modules are still used for settings and updater behavior.
    "storage",
    "updater",
    "sqlite3",
    "gettext",
    "locale",
    "yt_dlp.extractor._extractors",
    "yt_dlp.utils",
]
hiddenimports += collect_submodules("vortexdl")
datas += collect_data_files("vortexdl")

for package in ("yt_dlp", "customtkinter", "plyer", "pystray"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

# Plyer loads its macOS bridge dynamically and it is installed via the macOS extra.
if sys.platform == "darwin":
    pyobjus_datas, pyobjus_binaries, pyobjus_hiddenimports = collect_all("pyobjus")
    datas += pyobjus_datas
    binaries += pyobjus_binaries
    hiddenimports += pyobjus_hiddenimports

analysis = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
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
pyz = PYZ(analysis.pure)

if sys.platform == "win32":
    icon_path = ROOT / "assets" / "icon.ico"
else:
    icon_path = ROOT / "assets" / "icon.png"
icon = str(icon_path) if icon_path.exists() else None

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="VortexDL",
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
    icon=icon,
)
