# PyInstaller recipe for the compact, standalone Status Changer executable.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_dir = Path(SPECPATH).resolve()
test_packages = ("pywinauto.tests", "comtypes.test")


def include_runtime_module(name):
    return not any(name == package or name.startswith(package + ".")
                   for package in test_packages)


hiddenimports = ["camfrog_auto"]
hiddenimports += collect_submodules("pywinauto", filter=include_runtime_module)
hiddenimports += collect_submodules("comtypes", filter=include_runtime_module)

icon_path = project_dir / "app.ico"

a = Analysis(
    [str(project_dir / "camfrog_status_gui.py")],
    pathex=[str(project_dir)],
    binaries=[],
    datas=[],
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
    a.binaries,
    a.datas,
    [],
    name="zcfato",
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
    icon=[str(icon_path)] if icon_path.is_file() else None,
)
