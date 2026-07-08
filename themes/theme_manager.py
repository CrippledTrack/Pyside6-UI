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
from types import MappingProxyType
from typing import Callable, Dict, List, Optional, Any, TYPE_CHECKING
from ..app.qt_bindings import QApplication, QPalette, QColor, Qt

# Try to get NEW_UI_ENABLED_BY_DEFAULT from platform constants first, fallback to GUI constants
try:
    from ..app.utils.imports import get_platforms_constants
    platform_constants = get_platforms_constants()
    NEW_UI_ENABLED_BY_DEFAULT = getattr(platform_constants, 'NEW_UI_ENABLED_BY_DEFAULT', None)
    if NEW_UI_ENABLED_BY_DEFAULT is None:
        from ..app.constants import NEW_UI_ENABLED_BY_DEFAULT
except (ImportError, AttributeError):
    try:
        from ..app.constants import NEW_UI_ENABLED_BY_DEFAULT
    except ImportError:
        # Fallback if constants not available
        NEW_UI_ENABLED_BY_DEFAULT = True

# PERF: Builtin theme getter functions are imported lazily via their module path
# to avoid generating all 13 stylesheet strings at import time.
# See _BUILTIN_THEME_FACTORIES below.

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


def create_palette_from_data(palette_data: Dict[str, Any]) -> QPalette:
    """Create and return a QPalette object from palette data dictionary."""
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
            
    return palette


# Mapping of builtin theme name -> factory function import path.
# Each factory is only called the first time its theme is accessed.
_BUILTIN_THEME_FACTORIES: Dict[str, str] = {
    "default":     "get_default_theme",
    "dark":        "get_dark_theme",
    "light":       "get_light_theme",
    "blue":        "get_blue_theme",
    "green":       "get_green_theme",
    "purple":      "get_purple_theme",
    "purple_dark": "get_purple_dark_theme",
    "orange":      "get_orange_theme",
    "red":         "get_red_theme",
    "cyberpunk":   "get_cyberpunk_theme",
    "minimal":     "get_minimal_theme",
    "oled":        "get_oled_theme",
    "legacy":      "get_legacy_theme",
}


class ThemeManager:
    """Manages application themes including loading, saving, and applying themes"""
    
    def __init__(self, themes_dir: str = "themes", settings_service: Optional["SettingsService"] = None) -> None:
        self.themes_dir = Path(themes_dir)
        self._themes: Dict[str, Any] = {}
        self.builtin_theme_names: set = set()  # Track built-in theme names
        self.settings_service = settings_service
        self.current_theme = ""  # Initialize current theme
        self._last_stylesheet = ""  # Track last applied stylesheet for refreshes
        # Capture initial system palette before any theme is applied
        self._initial_palette = QApplication.style().standardPalette()
        
        # PERF: Lazy theme factories — theme data is only generated when first accessed.
        # Maps theme name -> callable that returns the theme data dict.
        self._theme_factories: Dict[str, Callable[[], Dict[str, Any]]] = {}
        # Cache of sorted theme name list, invalidated on add/remove.
        self._sorted_names_cache: Optional[List[str]] = None
        
        # Check if we should use legacy theme manager
        self._use_legacy = False
        if self.settings_service:
            try:
                self._use_legacy = not self.settings_service.get_new_ui_enabled()
            except Exception:
                # If method doesn't exist, default to new UI
                self._use_legacy = False
        
        # Always load themes in main manager (single source of truth)
        self.load_builtin_themes()
        self.load_custom_themes()
    
    def load_builtin_themes(self) -> None:
        """Register built-in themes as lazy factories.
        
        Theme data is not generated until the theme is first accessed
        (applied or previewed), saving ~200KB+ of stylesheet strings
        for themes that are never used.
        """
        from . import builtin_themes as _bt_mod
        for name, func_name in _BUILTIN_THEME_FACTORIES.items():
            factory = getattr(_bt_mod, func_name)
            self._theme_factories[name] = factory
        self.builtin_theme_names = set(_BUILTIN_THEME_FACTORIES.keys())
        self._sorted_names_cache = None  # Invalidate name cache
    
    def is_builtin_theme(self, theme_name: str) -> bool:
        """Check if a theme is a built-in theme.
        
        Since there's only one set of themes, we check the main manager's
        built-in theme names.
        """
        # Ensure themes are loaded
        if not self.builtin_theme_names:
            self.load_builtin_themes()
        return theme_name in self.builtin_theme_names
    
    def load_custom_themes(self) -> None:
        """Load custom themes from the themes directory.
        """
        if not self.themes_dir.exists():
            return
        
        for theme_file in self.themes_dir.glob("*.json"):
            try:
                with open(theme_file, 'r', encoding='utf-8') as f:
                    theme_data = json.load(f)
                    theme_name = theme_file.stem
                    self._themes[theme_name] = theme_data
                    logger.info(f"Loaded custom theme: {theme_name}")
            except Exception as e:
                logger.error(f"Failed to load theme {theme_file.name}: {e}")
        self._sorted_names_cache = None  # Invalidate name cache
    
    def _resolve_theme(self, theme_name: str) -> Optional[Dict[str, Any]]:
        """Resolve a theme by name, materializing from a lazy factory if needed.
        
        Returns the theme data dict, or None if the theme does not exist.
        """
        if theme_name in self._themes:
            return self._themes[theme_name]
        if theme_name in self._theme_factories:
            self._themes[theme_name] = self._theme_factories.pop(theme_name)()
            return self._themes[theme_name]
        return None

    def _has_theme(self, theme_name: str) -> bool:
        """Check if a theme is registered (materialized or pending lazy factory)."""
        return theme_name in self._themes or theme_name in self._theme_factories

    @property
    def themes(self) -> MappingProxyType:
        """Get a read-only view of all themes.
        
        PERF: Returns a MappingProxyType instead of a full copy.
        Lazy-factory themes are materialized on access to ensure the
        view is complete for callers that iterate all themes (e.g. theme dialog).
        """
        # Ensure themes are loaded
        if not self._themes and not self._theme_factories:
            self.load_builtin_themes()
            self.load_custom_themes()
        # Materialize any remaining lazy factories so the view is complete
        if self._theme_factories:
            for name in list(self._theme_factories):
                self._themes[name] = self._theme_factories.pop(name)()
        return MappingProxyType(self._themes)
    
    @themes.setter
    def themes(self, value: Dict[str, Any]) -> None:
        """Set themes dictionary"""
        self._themes = value
        self._theme_factories.clear()
        self._sorted_names_cache = None
    
    def save_custom_theme(self, theme_name: str, theme_data: Dict[str, Any]) -> bool:
        """Save a custom theme to file.
        """
        self.themes_dir.mkdir(parents=True, exist_ok=True)
        
        theme_path = self.themes_dir / f"{theme_name}.json"
        try:
            import os
            import tempfile
            temp_fd, temp_path = tempfile.mkstemp(dir=str(self.themes_dir), prefix=f".theme_{theme_name}_")
            try:
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    json.dump(theme_data, f, indent=2, ensure_ascii=False)
                os.replace(temp_path, theme_path)
            except Exception as e:
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass
                raise e
            self._themes[theme_name] = theme_data
            self._sorted_names_cache = None  # Invalidate name cache
            logger.info(f"Saved custom theme: {theme_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save theme {theme_name}: {e}")
            return False
    
    def get_theme_names(self) -> List[str]:
        """Get list of available theme names.
        
        Returns themes from the main manager since there's only one set of themes
        (modern themes that get adapted for legacy UI).
        PERF: Result is cached and invalidated when themes are added/removed.
        """
        # Ensure themes are loaded
        if not self._themes and not self._theme_factories:
            self.load_builtin_themes()
            self.load_custom_themes()
        
        if self._sorted_names_cache is None:
            # Include both materialized and pending lazy themes
            all_names = set(self._themes.keys()) | set(self._theme_factories.keys())
            self._sorted_names_cache = sorted(all_names)
        return list(self._sorted_names_cache)
    
    def get_current_theme(self) -> str:
        """Get current theme name"""
        return getattr(self, 'current_theme', '')

    def get_theme_data(self, theme_name: Optional[str] = None) -> Dict[str, Any]:
        """Get the data dict for a theme.

        Args:
            theme_name: Theme to look up.  ``None`` (default) uses the current theme.

        Returns:
            Theme data dictionary (direct reference, not a copy), or ``{}``
            if the theme is not found.
        """
        if theme_name is None:
            theme_name = self.get_current_theme()
        return self._resolve_theme(theme_name) or {}

    def is_legacy_ui(self) -> bool:
        """Whether the UI is running in legacy (classic) mode."""
        return self._use_legacy
    
    def apply_theme(self, theme_name: str, new_ui_enabled: Optional[bool] = None) -> bool:
        """Apply a theme to the application
        
        Args:
            theme_name: Name of the theme to apply
            new_ui_enabled: If False, uses classic stylesheet generator.
                          If None, checks settings_service for the flag.
        """
        # Check settings service for flag if not explicitly provided
        if new_ui_enabled is None and self.settings_service:
            try:
                new_ui_enabled = self.settings_service.get_new_ui_enabled()
            except Exception:
                # If method doesn't exist or fails, use constant default
                new_ui_enabled = NEW_UI_ENABLED_BY_DEFAULT
        elif new_ui_enabled is None:
            new_ui_enabled = NEW_UI_ENABLED_BY_DEFAULT
        
        # Use classic stylesheet if old UI is enabled
        if not new_ui_enabled:
            self._use_legacy = True
            
            # Ensure themes are loaded
            if not self._themes and not self._theme_factories:
                self.load_builtin_themes()
                self.load_custom_themes()
            
            # Check if theme exists
            if not self._has_theme(theme_name):
                logger.error(f"Theme '{theme_name}' not found")
                return False
            
            try:
                theme_data = self._resolve_theme(theme_name)
                
                # Default theme = system styling
                if theme_name == "default" and not theme_data.get('stylesheet', '').strip():
                    self._apply_stylesheet('')
                    self._apply_palette({})
                else:
                    # Generate classic stylesheet from theme data
                    from .classic_theme_manager import get_classic_stylesheet
                    classic_stylesheet = get_classic_stylesheet(theme_data)
                    self._apply_stylesheet(classic_stylesheet)
                    self._apply_palette(theme_data.get('palette', {}))
                
                self.current_theme = theme_name
                logger.info(f"Applied theme: {theme_name} (classic_ui=True)")
                
                # Save theme preference
                if self.settings_service:
                    try:
                        self.settings_service.save_theme_preference(theme_name)
                    except Exception as e:
                        logger.warning(f"Failed to save theme preference: {e}")
                
                return True
            except Exception as e:
                logger.error(f"Failed to apply theme {theme_name}: {e}")
                return False
        
        # Use new theme manager
        # If we were using legacy, we need to switch back to new
        if self._use_legacy:
            # Make sure new themes are loaded
            if not self._themes and not self._theme_factories:
                self.load_builtin_themes()
                self.load_custom_themes()
            logger.info("Switched to new theme manager")
        
        self._use_legacy = False
        
        # Ensure themes are loaded
        if not self._themes and not self._theme_factories:
            self.load_builtin_themes()
            self.load_custom_themes()
        
        # Check if theme exists
        if not self._has_theme(theme_name):
            logger.error(f"Theme '{theme_name}' not found")
            return False
        
        try:
            theme_data = self._resolve_theme(theme_name)
            stylesheet = theme_data.get('stylesheet', '')
            
            self._apply_stylesheet(stylesheet)
            self._apply_palette(theme_data.get('palette', {}))
            self.current_theme = theme_name
            logger.info(f"Applied theme: {theme_name} (new_ui={new_ui_enabled})")
            
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
        # Ensure themes are loaded
        if not self._themes and not self._theme_factories:
            self.load_builtin_themes()
            self.load_custom_themes()
        
        # Use saved theme preference if available
        if saved_theme and self._has_theme(saved_theme):
            theme_name = saved_theme
            logger.info(f"Applying saved theme preference: {theme_name}")
        else:
            # Check for DEFAULT_THEME constant override
            try:
                from ..app.utils.imports import get_platforms_constants
                platform_constants = get_platforms_constants()
                default_theme = getattr(platform_constants, 'DEFAULT_THEME', '')
            except Exception:
                default_theme = ''
            
            if default_theme and self._has_theme(default_theme):
                theme_name = default_theme
                logger.info(f"Applying constant default theme override: {theme_name}")
            else:
                # Auto-detect based on system preference
                is_dark = self.detect_system_dark_mode()
                theme_name = "dark" if is_dark else "light"
                logger.info(f"Applying auto-detected theme: {theme_name}")
        
        # apply_theme will automatically check settings_service for new_ui_enabled
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
        app = QApplication.instance()
        normalized = stylesheet if stylesheet else ""
        was_empty = not self._last_stylesheet
        app.setStyleSheet(normalized)
        if not normalized and not was_empty:
            self._refresh_menus_after_stylesheet_clear(app)
        self._last_stylesheet = normalized

    def _refresh_menus_after_stylesheet_clear(self, app: QApplication) -> None:
        """Force menu bars to re-polish after clearing stylesheet."""
        try:
            from ..app.qt_bindings import QMenuBar
        except Exception:
            return
        
        for widget in app.allWidgets():
            if isinstance(widget, QMenuBar):
                try:
                    style = widget.style()
                    style.unpolish(widget)
                    style.polish(widget)
                    widget.updateGeometry()
                    widget.update()
                except Exception:
                    continue
    
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
        
        palette = create_palette_from_data(palette_data)
        app.setPalette(palette)

    @staticmethod
    def parse_hex_color(hex_color: str) -> tuple[int, int, int]:
        """Parse hex color string to RGB tuple.
        
        Args:
            hex_color: Color in hex format (e.g., '#0078d4' or '0078d4')
            
        Returns:
            RGB tuple of integers (r, g, b)
        """
        if not hex_color:
            return (0, 120, 212)
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join(c + c for c in hex_color)
        if len(hex_color) == 6:
            try:
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            except ValueError:
                pass
        return (0, 120, 212)  # Default blue fallback

    @staticmethod
    def adjust_color(hex_color: str, factor: float) -> str:
        """Adjust a hex color brightness.
        
        Args:
            hex_color: Color in hex format (e.g., '#0078d4')
            factor: Brightness adjustment. > 1 lightens, < 1 darkens
            
        Returns:
            Adjusted color in hex format
        """
        hex_color_clean = hex_color.lstrip('#')
        if len(hex_color_clean) == 3:
            hex_color_clean = ''.join(c + c for c in hex_color_clean)
        if len(hex_color_clean) == 6:
            try:
                r, g, b = tuple(int(hex_color_clean[i:i+2], 16) for i in (0, 2, 4))
                if factor > 1:
                    r = min(255, int(r + (255 - r) * (factor - 1)))
                    g = min(255, int(g + (255 - g) * (factor - 1)))
                    b = min(255, int(b + (255 - b) * (factor - 1)))
                else:
                    r = int(r * factor)
                    g = int(g * factor)
                    b = int(b * factor)
                return f"#{r:02x}{g:02x}{b:02x}"
            except ValueError:
                pass
        return hex_color

    @staticmethod
    def adjust_notification_color(hex_color: str, notification_type: Any) -> str:
        """Parse hex color and adjust hue based on notification type.
        
        Args:
            hex_color: Base highlight color in hex format
            notification_type: The notification type to adjust for (string or NotificationType enum)
            
        Returns:
            Adjusted color in hex format
        """
        # Resolve enum to its string value if needed
        type_str = notification_type
        if hasattr(notification_type, 'value'):
            type_str = notification_type.value
        if isinstance(type_str, str):
            type_str = type_str.lower()
        else:
            type_str = str(type_str).lower()
            
        r, g, b = ThemeManager.parse_hex_color(hex_color)
        
        # Adjust hue based on type
        if type_str == "success":
            r, g, b = max(0, r - 30), min(255, g + 40), max(0, b - 30)
        elif type_str == "warning":
            r, g, b = min(255, r + 80), min(255, g + 30), max(0, b - 80)
        elif type_str == "error":
            r, g, b = min(255, r + 100), max(0, g - 60), max(0, b - 60)
        elif type_str == "loading":
            r, g, b = min(255, r + 20), max(0, g - 40), min(255, b + 40)
        # info/other keeps original highlight color
        
        return f"#{r:02x}{g:02x}{b:02x}"


__all__ = ['ThemeManager']

