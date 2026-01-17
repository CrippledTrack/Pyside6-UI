"""
Standalone runner for the GUI submodule.

This allows running the GUI even when the parent project does not provide a
top-level `main.py` next to the `GUI/` folder.

Example:
    cd GUI
    python run.py --dev
"""

from __future__ import annotations

import os
import sys
import types


def _ensure_gui_virtual_package() -> None:
    """Ensure `import GUI...` works when this file is executed as a script.

    When executing `python GUI/run.py`, sys.path[0] becomes the GUI directory,
    so `import GUI` would normally look for `GUI/GUI`. We instead create a
    virtual package named `GUI` that points at this directory.
    """
    repo_root = os.path.dirname(os.path.abspath(__file__))  # .../GUI

    # Mark as standalone so path resolution uses GUI/ as base when appropriate.
    os.environ.setdefault("GUI_STANDALONE_MODE", "1")

    # If GUI is already loaded, don't stomp it.
    if "GUI" in sys.modules:
        return

    module = types.ModuleType("GUI")
    module.__path__ = [repo_root]
    sys.modules["GUI"] = module


if __name__ == "__main__":
    _ensure_gui_virtual_package()
    from GUI.app.app import run

    raise SystemExit(run(sys.argv))

