"""
Built-in theme definitions for the application.

Theme modules are imported on first use so startup only pays for the
theme that is actually applied (plus shared ``_base`` when needed).
"""

from __future__ import annotations

import importlib
from typing import Any, Dict

# Base utilities — lightweight; theme modules depend on these when loaded.
from ._base import (
    BORDER_RADIUS_DEFAULT,
    BORDER_RADIUS_SHARP,
    generate_stylesheet,
)

_PACKAGE = __name__


def _load_theme(module_name: str) -> Dict[str, Any]:
    """Import a single theme module and return its theme data."""
    module = importlib.import_module(f".{module_name}", _PACKAGE)
    return module.get_theme()


def get_default_theme() -> Dict[str, Any]:
    """Get default theme data."""
    return _load_theme("default")


def get_dark_theme() -> Dict[str, Any]:
    """Get Dark theme data."""
    return _load_theme("dark")


def get_light_theme() -> Dict[str, Any]:
    """Get Light theme data."""
    return _load_theme("light")


def get_legacy_theme() -> Dict[str, Any]:
    """Get Legacy theme data."""
    return _load_theme("legacy")


def get_purple_dark_theme() -> Dict[str, Any]:
    """Get Purple Dark theme data."""
    return _load_theme("purple_dark")


def get_blue_theme() -> Dict[str, Any]:
    """Get Blue theme data."""
    return _load_theme("blue")


def get_green_theme() -> Dict[str, Any]:
    """Get Green theme data."""
    return _load_theme("green")


def get_purple_theme() -> Dict[str, Any]:
    """Get Purple theme data."""
    return _load_theme("purple")


def get_orange_theme() -> Dict[str, Any]:
    """Get Orange theme data."""
    return _load_theme("orange")


def get_red_theme() -> Dict[str, Any]:
    """Get Red theme data."""
    return _load_theme("red")


def get_cyberpunk_theme() -> Dict[str, Any]:
    """Get Cyberpunk theme data."""
    return _load_theme("cyberpunk")


def get_minimal_theme() -> Dict[str, Any]:
    """Get Minimal theme data."""
    return _load_theme("minimal")


def get_oled_theme() -> Dict[str, Any]:
    """Get OLED Dark theme data."""
    return _load_theme("oled")


__all__ = [
    'BORDER_RADIUS_DEFAULT',
    'BORDER_RADIUS_SHARP',
    'generate_stylesheet',
    'get_default_theme',
    'get_dark_theme',
    'get_light_theme',
    'get_legacy_theme',
    'get_purple_dark_theme',
    'get_blue_theme',
    'get_green_theme',
    'get_purple_theme',
    'get_orange_theme',
    'get_red_theme',
    'get_cyberpunk_theme',
    'get_minimal_theme',
    'get_oled_theme',
]
