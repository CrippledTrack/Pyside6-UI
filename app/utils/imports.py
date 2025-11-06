from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def get_platforms_constants() -> Any:
    """
    Import and return the app_plugins.constants module with fallback handling.
    
    This function handles the common import pattern:
    1. Try direct import from app_plugins.constants (new name)
    2. Try adding parent directory to sys.path and import from app_plugins.constants
    3. LEGACY: Fallback to platforms.constants (deprecated, 3.0.0 compatibility)
    4. Fallback to app.constants
    
    Returns:
        Module: The constants module (from app_plugins, platforms legacy, or app fallback)
    """
    # First attempt: direct import from new name
    try:
        from app_plugins import constants
        return constants
    except ImportError:
        pass
    
    # Second attempt: add parent directory to path and try new name
    try:
        # This file is at GUI/app/utils/imports.py
        # Parent project root is 4 levels up
        current_file = Path(__file__).resolve()
        parent_dir = current_file.parent.parent.parent.parent
        
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
        
        from app_plugins import constants
        return constants
    except ImportError:
        pass
    
    # LEGACY: Support for old 'platforms/' folder name (deprecated, 3.0.0 compatibility)
    try:
        from platforms import constants
        return constants
    except ImportError:
        pass
    
    # LEGACY: Support for old 'platforms/' folder name with path manipulation (deprecated, 3.0.0 compatibility)
    try:
        current_file = Path(__file__).resolve()
        parent_dir = current_file.parent.parent.parent.parent
        
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
        
        from platforms import constants
        return constants
    except ImportError:
        pass
    
    # Fallback: use app.constants
    try:
        from app import constants
        return constants
    except ImportError:
        # Relative import fallback
        from .. import constants
        return constants


__all__ = ['get_platforms_constants']
