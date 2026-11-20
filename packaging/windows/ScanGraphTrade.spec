# -*- mode: python ; coding: utf-8 -*-
# Construction :  pyinstaller packaging/windows/ScanGraphTrade.spec --noconfirm
# Variable d'environnement TESSERACT_DIR : dossier Tesseract-OCR à embarquer (facultatif).
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parents[1]
SRC = ROOT / "src"

datas = [(str(SRC / "scan_graph_trade" / "web" / "index.html"), "scan_graph_trade/web")]

tess = os.environ.get("TESSERACT_DIR")
if tess and Path(tess).is_dir():
    tess = Path(tess)
    # moteur + DLL + données de langue (on ignore les outils d'entraînement)
    for f in tess.glob("*.dll"):
        datas.append((str(f), "tesseract"))
    datas.append((str(tess / "tesseract.exe"), "tesseract"))
    datas.append((str(tess / "tessdata"), "tesseract/tessdata"))

a = Analysis(
    [str(ROOT / "packaging" / "windows" / "launcher.py")],
    pathex=[str(SRC)],
    datas=datas,
    hiddenimports=collect_submodules("scan_graph_trade"),
    excludes=["fastapi", "uvicorn", "starlette", "pydantic", "pytest", "IPython", "matplotlib",
              "pandas", "scipy", "PIL.ImageQt", "PyQt5", "PyQt6", "PySide2", "PySide6", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ScanGraphTrade",
    icon=str(ROOT / "packaging" / "windows" / "icon.ico"),
    console=False,
    upx=False,
    runtime_tmpdir=None,
)
