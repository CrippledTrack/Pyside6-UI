"""Classic vs modern Qt UI mode helpers.

Classic UI remains fully supported. Prefer these helpers over scattering
``is_legacy_ui()`` / classic stylesheet imports at call sites.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .theme_manager import ThemeManager


def is_classic_ui(theme_manager: Optional["ThemeManager"]) -> bool:
    """Return True when the theme manager is in classic (legacy) UI mode."""
    if theme_manager is None:
        return False
    return bool(theme_manager.is_legacy_ui())


def classic_stylesheet_for(
    theme_manager: Optional["ThemeManager"],
    theme_data: Optional[Mapping[str, Any]] = None,
) -> str:
    """Build the classic stylesheet for ``theme_data`` or the current theme."""
    from .classic_theme_manager import get_classic_stylesheet

    data: Mapping[str, Any]
    if theme_data is not None:
        data = theme_data
    elif theme_manager is not None:
        data = theme_manager.get_theme_data()
    else:
        data = {}
    return get_classic_stylesheet(data)


__all__ = [
    "is_classic_ui",
    "classic_stylesheet_for",
]
