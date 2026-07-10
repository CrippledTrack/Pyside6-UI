"""Default theme - uses system styling."""

from __future__ import annotations

from typing import Dict, Any


def get_theme() -> Dict[str, Any]:
    """Get default theme data."""
    return {
        "name": "Default",
        "description": "Default system theme",
        "stylesheet": "",
        "palette": {}
    }

