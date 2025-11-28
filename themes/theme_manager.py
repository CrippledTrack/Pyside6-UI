"""
Theme management system for the application.

This module handles loading, applying, and managing themes including
built-in themes and custom theme files. It provides automatic theme
detection based on system preferences.
"""

from __future__ import annotations

import os
import json
import logging
import platform
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

from .builtin_themes import (
    get_default_theme,
    get_legacy_theme,
    get_dark_theme,
    get_light_theme,
    get_blue_theme,
    get_green_theme,
    get_purple_theme,
    get_orange_theme,
    get_red_theme,
    get_cyberpunk_theme,
    get_minimal_theme,
    get_purple_dark_theme,
)

if TYPE_CHECKING:
    from ..app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


def _parse_version_tuple(v: str) -> Optional[tuple]:
    """Parse a semantic version string like '3.1.2' -> (3, 1, 2). Returns None on failure."""
    try:
        parts = v.strip().split(".")
        if len(parts) < 2:
            return None
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        return (major, minor, patch)
    except Exception:
        return None


def _is_version_lte(version_str: str, major: int, minor: int) -> bool:
    """Return True if version_str <= major.minor.x (any patch)."""
    t = _parse_version_tuple(version_str)
    if t is None:
        return False
    v_major, v_minor, _ = t
    if v_major < major:
        return True
    if v_major > major:
        return False
    return v_minor <= minor


class ThemeManager:
    """Manages application themes including loading, saving, and applying themes"""
    
    def __init__(self, themes_dir: str = "themes", settings_service: Optional["SettingsService"] = None) -> None:
        self.themes_dir = Path(themes_dir)
        self.themes: Dict[str, Any] = {}
        self.builtin_theme_names: set = set()  # Track built-in theme names
        # Built-in aliases that should not be shown in UI theme pickers
        self._hidden_theme_names: set = {"ocean_blue"}
        self.settings_service = settings_service
        # Capture initial system palette before any theme is applied
        self._initial_palette = QApplication.style().standardPalette()
        self.load_builtin_themes()
        self.load_custom_themes()
    
    def load_builtin_themes(self) -> None:
        """Load built-in themes"""
        builtin_themes = {
            "default": get_default_theme(),
            "dark": get_dark_theme(), 
            "light": get_light_theme(),
            "blue": get_blue_theme(),
            "green": get_green_theme(),
            "purple": get_purple_theme(),
            "purple_dark": get_purple_dark_theme(),
            "orange": get_orange_theme(),
            "red": get_red_theme(),
            "cyberpunk": get_cyberpunk_theme(),
            "minimal": get_minimal_theme(),
            "legacy": get_legacy_theme(),
        }
        self.builtin_theme_names = set(builtin_themes.keys())
        self.themes.update(builtin_themes)
    
    def is_builtin_theme(self, theme_name: str) -> bool:
        """Check if a theme is a built-in theme"""
        return theme_name in self.builtin_theme_names
    
    def load_custom_themes(self) -> None:
        """Load custom themes from the themes directory"""
        if not self.themes_dir.exists():
            return
        
        for theme_file in self.themes_dir.glob("*.json"):
            try:
                with open(theme_file, 'r', encoding='utf-8') as f:
                    theme_data = json.load(f)
                    theme_name = theme_file.stem
                    self.themes[theme_name] = theme_data
                    logger.info(f"Loaded custom theme: {theme_name}")
            except Exception as e:
                logger.error(f"Failed to load theme {theme_file.name}: {e}")
    
    def save_custom_theme(self, theme_name: str, theme_data: Dict[str, Any]) -> bool:
        """Save a custom theme to file"""
        self.themes_dir.mkdir(parents=True, exist_ok=True)
        
        theme_path = self.themes_dir / f"{theme_name}.json"
        try:
            with open(theme_path, 'w', encoding='utf-8') as f:
                json.dump(theme_data, f, indent=2, ensure_ascii=False)
            self.themes[theme_name] = theme_data
            logger.info(f"Saved custom theme: {theme_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save theme {theme_name}: {e}")
            return False
    
    def get_theme_names(self) -> List[str]:
        """Get list of available theme names"""
        # Hide compatibility aliases from UI
        return [name for name in self.themes.keys() if name not in self._hidden_theme_names]
    
    def get_current_theme(self) -> str:
        """Get current theme name"""
        return self.current_theme
    
    def apply_theme(self, theme_name: str) -> bool:
        """Apply a theme to the application"""
        if theme_name not in self.themes:
            logger.error(f"Theme '{theme_name}' not found")
            return False
        
        try:
            theme_data = self.themes[theme_name]
            self._apply_stylesheet(theme_data.get('stylesheet', ''))
            self._apply_palette(theme_data.get('palette', {}))
            self.current_theme = theme_name
            logger.info(f"Applied theme: {theme_name}")
            
            # Save theme preference if settings service is available
            if self.settings_service:
                try:
                    self.settings_service.save_theme_preference(theme_name)
                except Exception as e:
                    logger.warning(f"Failed to save theme preference: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to apply theme {theme_name}: {e}")
            return False

    def detect_system_dark_mode(self) -> bool:
        """Detect whether the system prefers dark mode.

        Falls back to previous app behavior: if detection fails, default to
        dark on Linux and light elsewhere.
        """
        try:
            return QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            try:
                current_platform = platform.system().lower()
            except Exception:
                current_platform = ""
            return current_platform == "linux"

    def apply_auto_theme(self, saved_theme: Optional[str] = None) -> str:
        """Detect and apply the appropriate theme ('dark' or 'light').
        
        Args:
            saved_theme: If provided, use this theme instead of auto-detection

        Returns the applied theme name.
        """
        # Use saved theme preference if available
        if saved_theme and saved_theme in self.themes:
            theme_name = saved_theme
            logger.info(f"Applying saved theme preference: {theme_name}")
        else:
            # Auto-detect based on system preference
            is_dark = self.detect_system_dark_mode()
            theme_name = "dark" if is_dark else "light"
            logger.info(f"Applying auto-detected theme: {theme_name}")
        
        self.apply_theme(theme_name)
        return theme_name
    
    def set_settings_service(self, settings_service: Optional["SettingsService"]) -> None:
        """Set the settings service for theme persistence"""
        self.settings_service = settings_service
    
    def _apply_stylesheet(self, stylesheet: str):
        """Apply stylesheet to the application.
        
        If stylesheet is empty, clears any existing stylesheet to reset to system defaults.
        """
        # Always set the stylesheet (empty string clears previous styles)
        QApplication.instance().setStyleSheet(stylesheet if stylesheet else "")
    
    def _apply_palette(self, palette_data: Dict[str, Any]):
        """Apply color palette to the application.
        
        If palette_data is empty, resets to the default system palette.
        """
        app = QApplication.instance()
        
        if not palette_data:
            # Reset to initial system palette if captured, otherwise standard palette
            palette = getattr(self, '_initial_palette', app.style().standardPalette())
            app.setPalette(palette)
            return
        
        palette = QPalette()
        
        # Map color roles to their string representations
        color_roles = {
            'window': QPalette.ColorRole.Window,
            'window_text': QPalette.ColorRole.WindowText,
            'base': QPalette.ColorRole.Base,
            'alternate_base': QPalette.ColorRole.AlternateBase,
            'tool_tip_base': QPalette.ColorRole.ToolTipBase,
            'tool_tip_text': QPalette.ColorRole.ToolTipText,
            'text': QPalette.ColorRole.Text,
            'button': QPalette.ColorRole.Button,
            'button_text': QPalette.ColorRole.ButtonText,
            'bright_text': QPalette.ColorRole.BrightText,
            'link': QPalette.ColorRole.Link,
            'highlight': QPalette.ColorRole.Highlight,
            'highlighted_text': QPalette.ColorRole.HighlightedText
        }
        
        for role_name, color_value in palette_data.items():
            if role_name in color_roles:
                if isinstance(color_value, str):
                    # Handle hex color strings
                    color = QColor(color_value)
                elif isinstance(color_value, list) and len(color_value) >= 3:
                    # Handle RGB/RGBA lists
                    if len(color_value) == 3:
                        color = QColor(color_value[0], color_value[1], color_value[2])
                    else:
                        color = QColor(color_value[0], color_value[1], color_value[2], color_value[3])
                else:
                    continue
                
                palette.setColor(color_roles[role_name], color)
        
        app.setPalette(palette)


__all__ = ['ThemeManager']
