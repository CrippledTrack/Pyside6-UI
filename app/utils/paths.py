"""Path utilities for determining application directories.

This module provides functions to locate various application directories
whether running from source or as a PyInstaller bundle.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def parent_has_gui_plugin_dirs(parent_dir: Path) -> bool:
    """Return True if parent_dir contains app_plugins or platforms that look like this GUI's plugin trees.

    Used in standalone mode to decide whether to add the parent to sys.path for
    constants and plugin loading. We require at least one expected file or
    directory (constants.py, core_plugins.py, or linux/ / windows/) so that an
    unrelated folder named app_plugins or platforms (e.g. from another project)
    is not used, which could cause wrong constants, wrong plugins, or import errors.
    """
    for name in ("app_plugins", "platforms"):
        d = parent_dir / name
        if not d.is_dir():
            continue
        if (d / "constants.py").exists() or (d / "core_plugins.py").exists():
            return True
        if (d / "linux").is_dir() or (d / "windows").is_dir():
            return True
    return False


def get_base_path() -> Path:
    """Get base path whether running from source or PyInstaller bundle."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running from PyInstaller bundle - use directory containing the executable
        return Path(sys.executable).parent
    else:
        # Standalone mode: the base path is the GUI repository root (the `GUI/` folder).
        # This is used when the GUI is run via `GUI/run.py` (or otherwise embedded).
        if os.environ.get("GUI_STANDALONE_MODE") == "1":
            # This file is at GUI/app/utils/paths.py -> GUI/app/utils -> GUI/app -> GUI
            return Path(__file__).resolve().parent.parent.parent

        # Running from source - find the parent project using app.py as anchor
        # This file is at GUI/app/utils/paths.py
        current = Path(__file__).resolve()
        
        # Navigate: GUI/app/utils/paths.py -> GUI/app/utils -> GUI/app
        app_dir = current.parent.parent
        
        # Verify we found the right location by checking for app.py
        if (app_dir / "app.py").exists():
            # app_dir is GUI/app/, go up to GUI/, then to parent project
            gui_root = app_dir.parent  # GUI/
            parent_project = gui_root.parent  # Parent project root
            return parent_project
        
        # Fallback to current working directory
        return Path.cwd()


def get_plugins_dir() -> Path:
    """Get the external plugins directory path."""
    base = get_base_path()
    # Frozen (binary): always use ./plugins next to the executable for 4.x compatibility.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return base / "plugins"
    # Standalone from source (run.py from GUI/): use user_plugins to avoid confusion with GUI/plugins.
    if os.environ.get("GUI_STANDALONE_MODE") == "1":
        return base / "user_plugins"
    # Non-standalone (main.py or -m GUI): look for ./plugins relative to project root.
    return base / "plugins"


def app_root() -> Path:
    """Legacy function for backward compatibility."""
    return get_base_path()


def logs_dir() -> Path:
    """Get the logs directory path."""
    return app_root() / "logs"


__all__ = [
    'get_base_path',
    'get_plugins_dir',
    'app_root',
    'logs_dir',
    'parent_has_gui_plugin_dirs',
]


