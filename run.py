"""
Standalone runner for the GUI submodule (script or PyInstaller binary).

Puts the parent directory on sys.path so the module can be imported
resolves to the real GUI package. Use this for both interactive runs and as
the PyInstaller entry point.

Example:
    cd GUI
    python run.py --dev
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


if __name__ == "__main__":
    os.environ.setdefault("GUI_STANDALONE_MODE", "1")

    gui_dir = Path(__file__).resolve().parent
    if getattr(sys, "frozen", False):
        root = getattr(sys, "_MEIPASS", None)
        path_entry = str(Path(root) if isinstance(root, str) else gui_dir.parent)
    else:
        path_entry = str(gui_dir.parent)

    if path_entry not in sys.path:
        sys.path.insert(0, path_entry)

    if getattr(sys, "frozen", False):
        # Static import allows PyInstaller to trace and bundle the app correctly
        from GUI.app.app import run
    else:
        package_name = gui_dir.name
        module = __import__(f"{package_name}.app.app", fromlist=["run"])
        run = module.run

    raise SystemExit(run(sys.argv))
