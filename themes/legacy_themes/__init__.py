"""Legacy themes package for old UI mode.

This package provides the old theme management system that was used
before the UI overhaul. It's used when new_ui_enabled is False.
"""

from .theme_manager import LegacyThemeManager

__all__ = ['LegacyThemeManager']

