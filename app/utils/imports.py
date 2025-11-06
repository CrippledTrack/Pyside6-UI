from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def get_platforms_constants() -> Any:
    """
    Import and return the platforms.constants module with fallback handling.
    
    This function handles the common import pattern:
    1. Try direct import from platforms.constants
    2. Try adding parent directory to sys.path and import
    3. Fallback to app.constants
    
    Returns:
        Module: The constants module (from platforms or app fallback)
    """
    # First attempt: direct import
    try:
        from platforms import constants
        return constants
    except ImportError:
        pass
    
    # Second attempt: add parent directory to path
    try:
        # This file is at GUI/app/utils/imports.py
        # Parent project root is 4 levels up
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
