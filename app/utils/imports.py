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

# Cache for the merged constants namespace.  The merge is deterministic for
# a given process, so we only need to compute it once.
_cached_constants: Any = None


def _is_constant(name: str, value: Any) -> bool:
    if not name or not name.isupper():
        return False
    if isinstance(value, ModuleType) or callable(value):
        return False
    return isinstance(value, (str, int, float, bool, tuple, list, dict, type(None)))


def _collect_constants(module: ModuleType) -> dict[str, Any]:
    return {
        name: value
        for name, value in vars(module).items()
        if _is_constant(name, value)
    }


def _ensure_parent_on_path() -> None:
    current_file = Path(__file__).resolve()
    parent_dir = current_file.parent.parent.parent.parent
    add_parent = os.environ.get("GUI_STANDALONE_MODE") != "1" or parent_has_gui_plugin_dirs(parent_dir)
    if add_parent and str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))


def merge_constants(*, apply_launch_overrides: bool = True) -> dict[str, Any]:
    """Merge GUI, platforms, and app_plugins constants.

    Priority (highest last): GUI defaults, ``platforms.constants``,
    ``app_plugins.constants``. ``GUI_API_VERSION`` and ``CURRENT_PLATFORM``
    are always restored from GUI internals. Launch env/argv overrides are
    optional so build-time collection can match runtime policy without
    picking up the builder's CLI flags.
    """
    _ensure_parent_on_path()
    from .. import constants as gui_constants
    merged = _collect_constants(gui_constants)

    try:
        from platforms import constants as platforms_constants  # type: ignore[import-not-found]
        merged.update(_collect_constants(platforms_constants))
    except ImportError:
        pass

    try:
        from app_plugins import constants as app_constants  # type: ignore[import-not-found]
        merged.update(_collect_constants(app_constants))
    except ImportError:
        pass

    if apply_launch_overrides:
        env_mode = os.environ.get("GUI_SINGLE_PLUGIN_MODE")
        env_name = os.environ.get("GUI_SINGLE_PLUGIN") or os.environ.get("GUI_SINGLE_PLUGIN_NAME")

        if env_name:
            if env_name.lower() in ("1", "true", "yes", "on"):
                merged["SINGLE_PLUGIN_MODE"] = True
            elif env_name.lower() in ("0", "false", "no", "off"):
                merged["SINGLE_PLUGIN_MODE"] = False
            else:
                merged["SINGLE_PLUGIN_MODE"] = True
                merged["SINGLE_PLUGIN_NAME"] = env_name

        if env_mode:
            merged["SINGLE_PLUGIN_MODE"] = env_mode.lower() in ("1", "true", "yes", "on")

        for arg in sys.argv:
            if arg.startswith("--single-plugin="):
                merged["SINGLE_PLUGIN_MODE"] = True
                merged["SINGLE_PLUGIN_NAME"] = arg.split("=", 1)[1].strip()
            elif arg == "--single-plugin":
                merged["SINGLE_PLUGIN_MODE"] = True

    merged["GUI_API_VERSION"] = gui_constants.GUI_API_VERSION
    merged["CURRENT_PLATFORM"] = gui_constants.CURRENT_PLATFORM
    return merged


def get_platforms_constants() -> Any:
    """Import and merge constants from GUI, platforms, and app_plugins.

    The result is cached after the first call for the lifetime of the process.
    """
    global _cached_constants
    if _cached_constants is not None:
        return _cached_constants
    _cached_constants = SimpleNamespace(**merge_constants(apply_launch_overrides=True))
    return _cached_constants


__all__ = ["get_platforms_constants", "merge_constants"]
