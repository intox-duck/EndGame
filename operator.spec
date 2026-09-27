# PyInstaller spec — build a single Operator.exe on Windows:
#   uv run pyinstaller operator.spec
# Produces dist/Operator.exe. Ship config.example.toml, .env.example and the
# playbooks/ folder alongside it (they are read from the working directory).

# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("google.genai")
    + collect_submodules("PySide6")
    + collect_submodules("keyring")
    + [
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        # keyring's Windows backend (Credential Manager):
        "keyring.backends.Windows",
    ]
)

# Ship the example configs and playbooks next to the exe so first run can seed
# config.toml / profile.toml. Personal profile.toml is NEVER bundled.
datas = [
    ("config.example.toml", "."),
    ("profile.example.toml", "."),
    ("playbooks", "playbooks"),
]

a = Analysis(
    ["src/operator_app/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
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
