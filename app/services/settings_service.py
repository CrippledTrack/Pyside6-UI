from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any

from ..utils.paths import get_base_path

logger = logging.getLogger(__name__)


@dataclass
class WindowGeometry:
    """Window geometry settings"""
    x: int = 100
    y: int = 100
    width: int = 800
    height: int = 600
    maximized: bool = False
    fullscreen: bool = False


@dataclass
class AppSettings:
    """Application settings with persistence"""
    theme: str = "ocean_blue"  # Default theme
    disabled_plugins: List[str] = None  # User-disabled plugins (separate from disabled_by_default)
    logging_enabled: bool = True
    log_to_file: bool = True
    window_geometry: WindowGeometry = None
    # UI/UX settings
    show_tooltips: bool = True
    # Keyboard shortcuts
    shortcuts_enabled: bool = True
    # Toast notifications
    toast_notifications_enabled: bool = True
    toast_duration: int = 3000
    # GUI version (for future migration detection)
    gui_version: str = ""
    
    def __post_init__(self):
        """Initialize default values for complex fields"""
        if self.disabled_plugins is None:
            self.disabled_plugins = []
        if self.window_geometry is None:
            self.window_geometry = WindowGeometry()


class SettingsService:
    """Service for managing application settings with JSON persistence"""
    
    def __init__(self):
        self._settings_file = get_base_path() / "settings.json"
        self._settings = AppSettings()
        self._load_settings()
    
    def _load_settings(self) -> None:
        """Load settings from JSON file"""
        if not self._settings_file.exists():
            logger.info("Settings file not found, using defaults")
            return
        
        try:
            with open(self._settings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load theme
            if 'theme' in data:
                self._settings.theme = data['theme']
            
            # Load disabled plugins (user-disabled, not including disabled_by_default)
            if 'disabled_plugins' in data and isinstance(data['disabled_plugins'], list):
                self._settings.disabled_plugins = data['disabled_plugins']
            
            # Load logging settings
            if 'logging_enabled' in data:
                self._settings.logging_enabled = bool(data['logging_enabled'])
            
            if 'log_to_file' in data:
                self._settings.log_to_file = bool(data['log_to_file'])
            
            # Load window geometry
            if 'window_geometry' in data and isinstance(data['window_geometry'], dict):
                geom = data['window_geometry']
                self._settings.window_geometry = WindowGeometry(
                    x=geom.get('x', 100),
                    y=geom.get('y', 100),
                    width=geom.get('width', 800),
                    height=geom.get('height', 600),
                    maximized=geom.get('maximized', False),
                    fullscreen=geom.get('fullscreen', False)
                )
            
            # Load UI/UX settings
            if 'show_tooltips' in data:
                self._settings.show_tooltips = bool(data['show_tooltips'])
            
            # Load keyboard shortcuts
            if 'shortcuts_enabled' in data:
                self._settings.shortcuts_enabled = bool(data['shortcuts_enabled'])
            
            # Load toast notifications
            if 'toast_notifications_enabled' in data:
                self._settings.toast_notifications_enabled = bool(data['toast_notifications_enabled'])
            if 'toast_duration' in data:
                self._settings.toast_duration = int(data['toast_duration'])
            
            # Load GUI version
            if 'gui_version' in data:
                self._settings.gui_version = str(data['gui_version'])
            
            logger.info(f"Settings loaded from {self._settings_file}")
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            # Keep default settings on error
    
    def _save_settings(self) -> None:
        """Save settings to JSON file"""
        try:
            # Convert settings to dict
            data = {
                'theme': self._settings.theme,
                'disabled_plugins': self._settings.disabled_plugins,
                'logging_enabled': self._settings.logging_enabled,
                'log_to_file': self._settings.log_to_file,
                'window_geometry': {
                    'x': self._settings.window_geometry.x,
                    'y': self._settings.window_geometry.y,
                    'width': self._settings.window_geometry.width,
                    'height': self._settings.window_geometry.height,
                    'maximized': self._settings.window_geometry.maximized,
                    'fullscreen': self._settings.window_geometry.fullscreen
                },
                'show_tooltips': self._settings.show_tooltips,
                'shortcuts_enabled': self._settings.shortcuts_enabled,
                'toast_notifications_enabled': self._settings.toast_notifications_enabled,
                'toast_duration': self._settings.toast_duration,
                'gui_version': self._settings.gui_version
            }
            
            # Write to file
            with open(self._settings_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Settings saved to {self._settings_file}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    def get_settings(self) -> AppSettings:
        """Get current settings"""
        return self._settings
    
    def save_theme_preference(self, theme_name: str) -> None:
        """Save theme preference"""
        self._settings.theme = theme_name
        self._save_settings()
        logger.info(f"Theme preference saved: {theme_name}")
    
    def get_theme_preference(self) -> str:
        """Get saved theme preference"""
        return self._settings.theme
    
    def save_disabled_plugins(self, plugin_names: List[str]) -> None:
        """Save user-disabled plugin names (excludes disabled_by_default)"""
        self._settings.disabled_plugins = plugin_names
        self._save_settings()
        logger.debug(f"Disabled plugins saved: {plugin_names}")
    
    def get_disabled_plugins(self) -> List[str]:
        """Get saved user-disabled plugin names"""
        return self._settings.disabled_plugins.copy()
    
    def save_window_geometry(self, x: int, y: int, width: int, height: int) -> None:
        """Save window geometry"""
        self._settings.window_geometry = WindowGeometry(x=x, y=y, width=width, height=height)
        self._save_settings()
        logger.debug(f"Window geometry saved: {x}, {y}, {width}x{height}")
    
    def get_window_geometry(self) -> WindowGeometry:
        """Get saved window geometry"""
        return self._settings.window_geometry
    
    def get_logging_enabled(self) -> bool:
        """Get logging enabled setting"""
        return self._settings.logging_enabled
    
    def get_log_to_file(self) -> bool:
        """Get log to file setting"""
        return self._settings.log_to_file
    
    # UI/UX settings methods
    def save_ui_preferences(self, show_tooltips: bool):
        """Save UI preferences"""
        self._settings.show_tooltips = show_tooltips
        self._save_settings()
        logger.debug(f"UI preferences saved: tooltips={show_tooltips}")
    
    def get_show_tooltips(self) -> bool:
        """Get show tooltips setting"""
        return self._settings.show_tooltips
    
    # Keyboard shortcuts methods
    def save_shortcuts_enabled(self, enabled: bool):
        """Save shortcuts enabled setting"""
        self._settings.shortcuts_enabled = enabled
        self._save_settings()
        logger.debug(f"Shortcuts enabled saved: {enabled}")
    
    def get_shortcuts_enabled(self) -> bool:
        """Get shortcuts enabled setting"""
        return self._settings.shortcuts_enabled
    
    # Toast notifications methods
    def save_toast_settings(self, enabled: bool, duration: int):
        """Save toast notification settings"""
        self._settings.toast_notifications_enabled = enabled
        self._settings.toast_duration = duration
        self._save_settings()
        logger.debug(f"Toast settings saved: enabled={enabled}, duration={duration}")
    
    def get_toast_notifications_enabled(self) -> bool:
        """Get toast notifications enabled setting"""
        return self._settings.toast_notifications_enabled
    
    def get_toast_duration(self) -> int:
        """Get toast duration setting"""
        return self._settings.toast_duration
    
    def save_gui_version(self, version: str):
        """Save GUI version to settings"""
        self._settings.gui_version = version
        self._save_settings()
        logger.debug(f"GUI version saved: {version}")
    
    def get_gui_version(self) -> str:
        """Get saved GUI version"""
        return self._settings.gui_version


def load_settings() -> SettingsService:
    """Load and return a settings service instance"""
    return SettingsService()


