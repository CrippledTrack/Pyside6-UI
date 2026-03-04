"""Import utilities for handling platform constants with priority-based merging.

This module provides functions to import and merge constants from multiple
sources with a defined priority order.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace, ModuleType
from typing import Any

from .paths import parent_has_gui_plugin_dirs


def get_platforms_constants() -> Any:
    """
    Import and merge constants from multiple sources with priority.
    
    Priority order (highest to lowest):
    1. app_plugins.constants (project-specific overrides)
    2. platforms.constants (shared/community additions)
    3. GUI/app/constants (framework defaults)
    
    Constants from higher priority sources override those from lower priority.
    
    Returns:
        SimpleNamespace: A module-like object with merged constants
    """
    # This file is at GUI/app/utils/imports.py
    # Parent project root is 4 levels up
    current_file = Path(__file__).resolve()
    parent_dir = current_file.parent.parent.parent.parent

    # Add parent to sys.path so we can merge constants from app_plugins/platforms.
    # When not standalone: always add. When standalone: add only if the parent
    # has our plugin trees (constants.py / core_plugins.py / linux|windows/), so we
    # don't pull in an unrelated app_plugins or platforms folder from another project.
    add_parent = os.environ.get("GUI_STANDALONE_MODE") != "1" or parent_has_gui_plugin_dirs(parent_dir)
    if add_parent and str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    
    def is_constant(name: str, value: Any) -> bool:
        if not name or not name.isupper():
            return False
        if isinstance(value, ModuleType) or callable(value):
            return False
        return isinstance(value, (str, int, float, bool, tuple, list, dict, type(None)))

    def collect(module: ModuleType) -> dict[str, Any]:
        return {
            name: value
            for name, value in vars(module).items()
            if is_constant(name, value)
        }

    # Start with GUI defaults (lowest priority)
    from .. import constants as gui_constants
    merged = collect(gui_constants)
    
    # Apply platforms constants (middle priority)
    try:
        from platforms import constants as platforms_constants
        merged.update(collect(platforms_constants))
    except ImportError:
        pass
    
    # Apply app_plugins constants (highest priority)
    try:
        from app_plugins import constants as app_constants
        merged.update(collect(app_constants))
    except ImportError:
        pass
    
    return SimpleNamespace(**merged)


__all__ = ['get_platforms_constants']
