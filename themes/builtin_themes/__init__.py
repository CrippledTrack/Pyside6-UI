"""
Built-in theme definitions for the application.

This package contains all built-in theme definitions that are available
by default in the application. Each theme is defined in its own module.
"""

from __future__ import annotations

from typing import Dict, Any

# Import theme modules
from . import (
    default,
    dark,
    light,
    legacy,
    purple_dark,
    blue,
    green,
    purple,
    orange,
    red,
    cyberpunk,
    minimal,
)

# Import base utilities for external use
from ._base import (
    BORDER_RADIUS_DEFAULT,
    BORDER_RADIUS_SHARP,
    generate_stylesheet,
)


# =============================================================================
# Theme getter functions (backward compatible API)
# =============================================================================

def get_default_theme() -> Dict[str, Any]:
    """Get default theme data."""
    return default.get_theme()


def get_dark_theme() -> Dict[str, Any]:
    """Get Dark theme data."""
    return dark.get_theme()


def get_light_theme() -> Dict[str, Any]:
    """Get Light theme data."""
    return light.get_theme()


def get_legacy_theme() -> Dict[str, Any]:
    """Get Legacy theme data."""
    return legacy.get_theme()


def get_purple_dark_theme() -> Dict[str, Any]:
    """Get Purple Dark theme data."""
    return purple_dark.get_theme()


def get_blue_theme() -> Dict[str, Any]:
    """Get Blue theme data."""
    return blue.get_theme()


def get_green_theme() -> Dict[str, Any]:
    """Get Green theme data."""
    return green.get_theme()


def get_purple_theme() -> Dict[str, Any]:
    """Get Purple theme data."""
    return purple.get_theme()


def get_orange_theme() -> Dict[str, Any]:
    """Get Orange theme data."""
    return orange.get_theme()


def get_red_theme() -> Dict[str, Any]:
    """Get Red theme data."""
    return red.get_theme()


def get_cyberpunk_theme() -> Dict[str, Any]:
    """Get Cyberpunk theme data."""
    return cyberpunk.get_theme()


def get_minimal_theme() -> Dict[str, Any]:
    """Get Minimal theme data."""
    return minimal.get_theme()


__all__ = [
    # Base utilities
    'BORDER_RADIUS_DEFAULT',
    'BORDER_RADIUS_SHARP',
    'generate_stylesheet',
    # Theme getters
    'get_default_theme',
    'get_dark_theme',
    'get_light_theme',
    'get_legacy_theme',
    'get_legacy_original_theme',
    'get_purple_dark_theme',
    'get_blue_theme',
    'get_green_theme',
    'get_purple_theme',
    'get_orange_theme',
    'get_red_theme',
    'get_cyberpunk_theme',
    'get_minimal_theme',
]

