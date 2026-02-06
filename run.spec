# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs

project_dir = Path(os.getcwd()).resolve()

datas = []

# Collect files in a directory and preserve subfolders under dest_prefix.
def add_tree(src_dir, dest_prefix):
    src_path = Path(src_dir)
    if not src_path.exists():
        return []
    collected = []
    for path in src_path.rglob("*"):
        if path.is_file():
            rel = path.relative_to(src_path)
            dest = Path(dest_prefix) / rel.parent
            collected.append((str(path), str(dest)))
    return collected

# Core configs / data files
for filename in [
    "config.json",
    "config.example.json",
    "name.txt",
    "personality_recycle.db",
]:
    src = project_dir / filename
    if src.exists():
        datas.append((str(src), "."))

# Static frontend assets
frontend_dir = project_dir / "frontend"
if frontend_dir.exists():
    datas += add_tree(frontend_dir, "frontend")

# Runtime folders (sessions, monitor, logs, etc.)
for folder in [
    "configs",
    "profile_photos",
    "sessions",
    "monitor",
    "temp_media",
    "logs",
]:
    src = project_dir / folder
    if src.exists():
        datas += add_tree(src, folder)

hiddenimports = []
# Telethon uses dynamic imports in some environments
hiddenimports += collect_submodules("telethon")
# Flask/Jinja often use dynamic imports
hiddenimports += collect_submodules("flask")
hiddenimports += collect_submodules("flask_cors")
hiddenimports += collect_submodules("jinja2")
hiddenimports += collect_submodules("werkzeug")
hiddenimports += collect_submodules("itsdangerous")
hiddenimports += collect_submodules("click")
hiddenimports += collect_submodules("blinker")
# PySocks is imported as "socks" by some clients
hiddenimports += ["socks"]

# Optional crypto acceleration for telethon (if installed)
binaries = []
try:
    binaries += collect_dynamic_libs("cryptg")
except Exception:
    pass

a = Analysis(
    [str(project_dir / "run.py")],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="run",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="炒群脚本1.0",
)
