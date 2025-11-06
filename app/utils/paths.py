from __future__ import annotations

import os
import sys
from pathlib import Path


def get_base_path() -> Path:
    """Get base path whether running from source or PyInstaller bundle."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running from PyInstaller bundle - use directory containing the executable
        return Path(sys.executable).parent
    else:
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
    # Both PyInstaller and source: look for ./plugins relative to base
    plugins_path = base / "plugins"
    return plugins_path


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
]


