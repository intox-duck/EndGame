# PyInstaller spec — build a single Operator.exe on Windows:
#   uv run pyinstaller operator.spec
# Produces dist/Operator.exe. Ship config.example.toml, .env.example and the
# playbooks/ folder alongside it (they are read from the working directory).

# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("google.genai")
    + collect_submodules("PySide6")
    + ["pynput.keyboard._win32", "pynput.mouse._win32"]
)

a = Analysis(
    ["src/operator_app/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
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
    name="Operator",
    debug=False,
    strip=False,
    upx=True,
    console=False,          # windowed app; set True to see stdout for debugging
)
