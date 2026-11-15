# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for XRD AutoFit Studio & DIC Utility standalone Windows distribution."""

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).resolve()

datas = [
    (str(project_root / "frontend" / "dist"), "frontend/dist"),
]

binaries = []
conda_bin = Path(r"C:\Users\sekig\anaconda3\Library\bin")
if conda_bin.exists():
    for dll_name in (
        "ffi.dll",
        "libmpdec-4.dll",
        "liblzma.dll",
        "LIBBZ2.dll",
        "libexpat.dll",
        "tcl86t.dll",
        "tk86t.dll",
        "sqlite3.dll",
        "libcrypto-3-x64.dll",
        "libssl-3-x64.dll",
        "zlib.dll",
    ):
        dll_path = conda_bin / dll_name
        if dll_path.exists():
            binaries.append((str(dll_path), "."))

hiddenimports = [
    "uvicorn",
    "fastapi",
    "fastapi.testclient",
    "starlette",
    "starlette.testclient",
    "pydantic",
    "httpx",
    "anyio",
    "scipy.special._ufuncs_cxx",
    "scipy.linalg.cython_blas",
    "scipy.linalg.cython_lapack",
    "scipy.integrate",
    "scipy.interpolate",
    "scipy.signal",
    "scipy.sparse.linalg",
    "pybaselines",
    "pybaselines.whittaker",
    "lmfit",
    "asteval",
    "uncertainties",
    "matplotlib",
    "matplotlib.pyplot",
    "matplotlib.backends.backend_agg",
    "PIL",
    "openpyxl",
    "pandas",
    "cv2",
    "webview",
    "tkinter",
    "tkinter.filedialog",
]
hiddenimports += collect_submodules("backend")
hiddenimports += collect_submodules("pybaselines")

a = Analysis(
    [str(project_root / "run_desktop.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="XRD_AutoFit_Studio",
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="XRD_AutoFit_Studio",
)
