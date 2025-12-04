"""
Legacy theme manager adapter for old UI mode.

This module provides an adapter that loads modern themes from the main
theme system and converts them into a simpler legacy format suitable
for the old UI. It eliminates the need for separate legacy theme definitions
by automatically adapting all modern themes to work with legacy styling.

The adapter converts complex modern stylesheets (generated with advanced
styling features) into simpler, more straightforward stylesheets that
work well with legacy UI components.
"""

from __future__ import annotations

import json
import logging
import platform
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

# Import modern themes from the main builtin_themes package
# All themes will be converted from modern format to legacy format
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


def _extract_color_from_stylesheet(stylesheet: str, selector: str, property: str) -> Optional[str]:
    """Extract a color value from a stylesheet by selector and property.
    
    Handles both explicit properties (border-color: #color) and shorthand (border: 1px solid #color).
    Also handles combined selectors (QLineEdit, QTextEdit, ...).
    """
    try:
        lines = stylesheet.split('\n')
        in_selector = False
        for i, line in enumerate(lines):
            # Check if this line contains the selector (handles combined selectors)
            line_lower = line.lower()
            if selector.lower() in line_lower and '{' in line:
                in_selector = True
            elif in_selector:
                # Check for explicit property like "border-color: #color"
                if property in line and ':' in line:
                    # Extract hex color
                    match = re.search(r'#[0-9a-fA-F]{6}', line)
                    if match:
                        return match.group(0)
                # Also check for "border:" shorthand property which includes color
                # Format: "border: 1px solid #color" or "border: 2px solid #color"
                if property == 'border-color' and 'border:' in line:
                    # Extract color from "border: 1px solid #color" format
                    # This regex looks for hex color after "solid" keyword
                    match = re.search(r'solid\s+(#[0-9a-fA-F]{6})', line, re.IGNORECASE)
                    if match:
                        return match.group(1)
                    # Fallback: extract any hex color in the line
                    match = re.search(r'#[0-9a-fA-F]{6}', line)
                    if match:
                        return match.group(0)
                if '}' in line:
                    in_selector = False
    except Exception:
        pass
    return None


def _extract_property_value_from_stylesheet(stylesheet: str, selector: str, property: str) -> Optional[str]:
    """Extract a property value from a stylesheet by selector and property.
    
    This can extract any property value (border-radius, border-width, etc.)
    not just colors.
    """
    try:
        lines = stylesheet.split('\n')
        in_selector = False
        for i, line in enumerate(lines):
            if selector in line and '{' in line:
                in_selector = True
            elif in_selector:
                if property in line and ':' in line:
                    # Extract value after the colon
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        value = parts[1].split(';')[0].strip()
                        if value:
                            return value
                if '}' in line:
                    in_selector = False
    except Exception:
        pass
    return None


def _extract_common_border_radius(stylesheet: str) -> str:
    """Extract the most common border-radius value from the stylesheet.
    
    Returns a default value if not found or if themes use sharp corners.
    """
    # Try to find border-radius values
    radius_pattern = r'border-radius:\s*(\d+px|0px)'
    matches = re.findall(radius_pattern, stylesheet, re.IGNORECASE)
    
    if matches:
        # Count occurrences of each value
        counts = Counter(matches)
        most_common = counts.most_common(1)[0]
        
        # If 0px is common (sharp corners), prefer it
        if '0px' in [r for r, _ in counts.most_common(3)]:
            return '0px'
        # Otherwise use the most common value
        return most_common[0]
    
    # Check for BORDER_RADIUS_SHARP pattern (0px)
    if 'border-radius: 0px' in stylesheet.lower() or 'border-radius:0px' in stylesheet.lower():
        return '0px'
    
    # Default to 4px for rounded corners
    return '4px'


def _extract_border_width(stylesheet: str) -> str:
    """Extract the common border-width value from the stylesheet."""
    # Look for border-width patterns
    width_pattern = r'border-width:\s*(\d+px)'
    matches = re.findall(width_pattern, stylesheet, re.IGNORECASE)
    
    if matches:
        counts = Counter(matches)
        most_common = counts.most_common(1)[0][0]
        return most_common
    
    # Check for explicit 2px borders (like cyberpunk)
    if 'border-width: 2px' in stylesheet or 'border-width:2px' in stylesheet:
        return '2px'
    
    # Default to 1px
    return '1px'


def _convert_modern_to_legacy_theme(modern_theme: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a modern theme to legacy format with simplified stylesheet.
    
    This adapter function takes a modern theme (with complex generated stylesheet)
    and converts it to a simpler legacy-style theme suitable for the old UI.
    It uses the legacy builtin_themes.py file as a reference for color mappings.
    
    Args:
        modern_theme: Modern theme dictionary with stylesheet and palette
        
    Returns:
        Legacy-format theme dictionary with simplified stylesheet
    """
    palette = modern_theme.get('palette', {})
    stylesheet = modern_theme.get('stylesheet', '')
    
    # Extract colors from palette - these match legacy theme structure exactly
    window_bg = palette.get('window', '#1e1e1e')
    window_text = palette.get('window_text', '#ffffff')
    base_bg = palette.get('base', '#2d2d2d')
    alt_bg = palette.get('alternate_base', '#3c3c3c')
    text_color = palette.get('text', '#ffffff')
    highlight = palette.get('highlight', '#0078d4')
    highlighted_text = palette.get('highlighted_text', '#ffffff')
    
    # Determine if it's a dark theme
    is_dark = _is_dark_color(window_bg)
    
    # Try to extract button hover/pressed from stylesheet, or derive them
    button_hover = _extract_color_from_stylesheet(stylesheet, 'QPushButton:hover', 'background-color')
    button_pressed = _extract_color_from_stylesheet(stylesheet, 'QPushButton:pressed', 'background-color')
    
    # Derive hover/pressed if not found
    if not button_hover:
        button_hover = _lighten_color(highlight, 0.15) if is_dark else _darken_color(highlight, 0.1)
    if not button_pressed:
        button_pressed = _darken_color(highlight, 0.15) if is_dark else _darken_color(highlight, 0.2)
    
    # For buttons, use highlight color directly (legacy pattern)
    # Button text should be white for dark themes, or window_bg for light
    button_text = 'white' if is_dark else window_bg
    # Check if button_text in palette suggests different (like green theme uses dark text)
    palette_button_text = palette.get('button_text', '')
    if palette_button_text and palette_button_text != window_text:
        # If button_text differs significantly, use it
        if _is_dark_color(palette_button_text) != is_dark:
            button_text = palette_button_text
    
    # Extract theme-specific styling characteristics from original stylesheet
    border_radius = _extract_common_border_radius(stylesheet)
    border_width = _extract_border_width(stylesheet)
    
    # Try to extract border color from common selectors, fallback to alt_bg
    # Try multiple selectors to find the border color (cyberpunk uses green borders)
    border_color = _extract_color_from_stylesheet(stylesheet, 'QLineEdit', 'border-color')
    if not border_color:
        border_color = _extract_color_from_stylesheet(stylesheet, 'QTextEdit', 'border-color')
    if not border_color:
        border_color = _extract_color_from_stylesheet(stylesheet, 'QPlainTextEdit', 'border-color')
    if not border_color:
        border_color = _extract_color_from_stylesheet(stylesheet, 'QTabWidget::pane', 'border-color')
    if not border_color:
        # Fallback to alternate_base for legacy themes (matches legacy pattern)
        border_color = alt_bg
    
    # Light theme specific adjustments (matching legacy light theme)
    if not is_dark:
        tab_bg = '#e0e0e0'
        label_color = '#333333'
        scrollbar_bg = '#f0f0f0'
        scrollbar_handle = '#c0c0c0'
        scrollbar_handle_hover = '#a0a0a0'
    else:
        tab_bg = base_bg  # For dark themes, tabs use base
        label_color = text_color
        scrollbar_bg = base_bg
        scrollbar_handle = alt_bg
        scrollbar_handle_hover = highlight
    
    # Generate simplified legacy-style stylesheet matching legacy builtin_themes.py pattern exactly
    stylesheet = f"""
        QMainWindow {{
            background-color: {window_bg};
        }}
        QWidget {{
            background-color: {window_bg};
            color: {window_text};
        }}
        #loadingWidget {{
            background-color: {base_bg};
        }}
        QTabWidget::pane {{
            border: {border_width} solid {border_color};
            background-color: {base_bg};
            border-radius: {border_radius};
        }}
        QTabBar::tab {{
            background-color: {tab_bg};
            color: {text_color};
            border: {border_width} solid {border_color};
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: {border_radius};
            border-top-right-radius: {border_radius};
        }}
        QTabBar::tab:selected {{
            background-color: {alt_bg if is_dark else base_bg};
            border-bottom-color: {alt_bg if is_dark else base_bg};
        }}
        QTabBar::tab:hover {{
            background-color: {alt_bg if is_dark else '#f5f5f5'};
        }}
        QPushButton {{
            background-color: {highlight};
            color: {button_text};
            border: none;
            padding: 8px 16px;
            border-radius: {border_radius};
        }}
        QPushButton:hover {{
            background-color: {button_hover};
        }}
        QPushButton:pressed {{
            background-color: {button_pressed};
        }}
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
            border: {border_width} solid {border_color};
            border-radius: {border_radius};
            padding: 4px;
            background-color: {base_bg};
            color: {text_color};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
            border-color: {highlight};
        }}
        QLabel {{
            color: {label_color};
        }}
        QMessageBox {{
            background-color: {base_bg};
        }}
        QMessageBox QPushButton {{
            min-width: 80px;
        }}
        QScrollBar:vertical {{
            border: none;
            background-color: {scrollbar_bg};
            width: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {scrollbar_handle};
            min-height: 20px;
            border-radius: {border_radius};
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {scrollbar_handle_hover};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            border: none;
            background-color: {scrollbar_bg};
            height: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {scrollbar_handle};
            min-width: 20px;
            border-radius: {border_radius};
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {scrollbar_handle_hover};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
    """
    
    return {
        "name": modern_theme.get("name", "Unknown"),
        "description": modern_theme.get("description", ""),
        "stylesheet": stylesheet.strip(),
        "palette": palette.copy()  # Keep the same palette
    }


def _is_dark_color(color: str) -> bool:
    """Determine if a color is dark."""
    try:
        if color.startswith('#'):
            color = color[1:]
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            # Calculate perceived brightness
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            return brightness < 128
    except (ValueError, IndexError):
        pass
    return True  # Default to dark


def _lighten_color(color: str, factor: float) -> str:
    """Lighten a hex color by a factor (0.0-1.0)."""
    try:
        if color.startswith('#'):
            color = color[1:]
            r = min(255, int(int(color[0:2], 16) + (255 - int(color[0:2], 16)) * factor))
            g = min(255, int(int(color[2:4], 16) + (255 - int(color[2:4], 16)) * factor))
            b = min(255, int(int(color[4:6], 16) + (255 - int(color[4:6], 16)) * factor))
            return f"#{r:02x}{g:02x}{b:02x}"
    except (ValueError, IndexError):
        pass
    return color


def _darken_color(color: str, factor: float) -> str:
    """Darken a hex color by a factor (0.0-1.0)."""
    try:
        if color.startswith('#'):
            color = color[1:]
            r = max(0, int(int(color[0:2], 16) * (1 - factor)))
            g = max(0, int(int(color[2:4], 16) * (1 - factor)))
            b = max(0, int(int(color[4:6], 16) * (1 - factor)))
            return f"#{r:02x}{g:02x}{b:02x}"
    except (ValueError, IndexError):
        pass
    return color


class LegacyThemeManager:
    """Legacy theme manager for old UI mode.
    
    This class acts as an adapter that loads modern themes from the main
    theme system and converts them into a simpler legacy format suitable
    for the old UI. It provides backward compatibility by automatically
    adapting modern themes to work with legacy styling requirements.
    
    The adapter converts complex modern stylesheets (generated with advanced
    styling features) into simpler, more straightforward stylesheets that
    work well with the legacy UI components.
    """
    
    def __init__(self, themes_dir: str = "themes", settings_service: Optional["SettingsService"] = None) -> None:
        self.themes_dir = Path(themes_dir)
        self.themes: Dict[str, Any] = {}
        self.builtin_theme_names: set = set()  # Track built-in theme names
        # Built-in aliases that should not be shown in UI theme pickers
        self._hidden_theme_names: set = {"ocean_blue"}
        self.settings_service = settings_service
        self.current_theme = ""  # Initialize current theme
        self.load_builtin_themes()
        self.load_custom_themes()
    
    def load_builtin_themes(self) -> None:
        """Load built-in themes from modern theme system and convert to legacy format.
        
        All themes are loaded from the modern theme system and converted
        through the adapter. No legacy theme definitions are needed.
        """
        # Load all modern themes - the adapter converts them to legacy format
        modern_themes = {
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
        
        # Convert all modern themes to legacy format
        # The adapter converts complex modern stylesheets to simpler legacy-style ones
        builtin_themes = {}
        for theme_name, modern_theme in modern_themes.items():
            stylesheet = modern_theme.get('stylesheet', '')
            
            # Check if this is the "default" theme (empty stylesheet, system styling)
            if theme_name == "default" and (not stylesheet or stylesheet.strip() == ''):
                # Default theme uses system styling, keep as-is (no conversion needed)
                builtin_themes[theme_name] = modern_theme
            elif theme_name == "legacy":
                # Legacy theme already has custom overrides designed for legacy UI
                # Keep it as-is to preserve all the custom styling
                builtin_themes[theme_name] = modern_theme
                logger.debug(f"Keeping legacy theme '{theme_name}' as-is (preserves custom overrides)")
            else:
                # Convert modern theme to legacy format
                builtin_themes[theme_name] = _convert_modern_to_legacy_theme(modern_theme)
                logger.debug(f"Converted modern theme '{theme_name}' to legacy format")
        
        self.builtin_theme_names = set(builtin_themes.keys())
        self.themes.update(builtin_themes)
    
    def is_builtin_theme(self, theme_name: str) -> bool:
        """Check if a theme is a built-in theme"""
        return theme_name in self.builtin_theme_names
    
    def load_custom_themes(self) -> None:
        """Load custom themes from the themes directory.
        
        Custom themes can be in either modern or legacy format. Modern themes
        will be automatically converted to legacy format for compatibility.
        """
        if not self.themes_dir.exists():
            return
        
        for theme_file in self.themes_dir.glob("*.json"):
            try:
                with open(theme_file, 'r', encoding='utf-8') as f:
                    theme_data = json.load(f)
                    theme_name = theme_file.stem
                    
                    # Check if theme needs conversion (modern format)
                    # Modern themes typically have longer, more complex stylesheets
                    stylesheet = theme_data.get('stylesheet', '')
                    # Simple heuristic: if stylesheet is very long and has modern patterns,
                    # it's likely a modern theme that needs conversion
                    if len(stylesheet) > 2000 or ('/*' in stylesheet and 'rgba(' in stylesheet):
                        # Likely a modern theme, convert it
                        theme_data = _convert_modern_to_legacy_theme(theme_data)
                        logger.debug(f"Converted custom modern theme '{theme_name}' to legacy format")
                    
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
            
            # Check if this is the "default" theme (empty stylesheet, system styling)
            stylesheet = theme_data.get('stylesheet', '')
            palette = theme_data.get('palette', {})
            
            # Apply theme (empty stylesheet/palette will reset to system defaults)
            self._apply_stylesheet(stylesheet)
            self._apply_palette(palette)
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
    
    def apply_modern_theme(self, theme_name: str, modern_theme_data: Dict[str, Any]) -> bool:
        """Apply a modern theme by converting it to legacy format and applying it.
        
        This method is used when the main ThemeManager is the source of truth
        for theme data. It accepts modern theme data, converts it, and applies it.
        
        Args:
            theme_name: Name of the theme being applied
            modern_theme_data: Modern theme dictionary with stylesheet and palette
            
        Returns:
            True if theme was applied successfully, False otherwise
        """
        try:
            # Check if this is the "default" theme (empty stylesheet, system styling)
            stylesheet = modern_theme_data.get('stylesheet', '')
            palette = modern_theme_data.get('palette', {})
            
            if theme_name == "default" and (not stylesheet or stylesheet.strip() == ''):
                # Default theme uses system styling - don't convert, apply directly
                self._apply_stylesheet('')  # Clear any existing stylesheet
                self._apply_palette({})  # Reset to system palette
                self.current_theme = theme_name
                logger.info(f"Applied default theme (system styling) in legacy mode")
            elif theme_name == "legacy":
                # Legacy theme already has custom overrides designed for legacy UI
                # Apply it directly without conversion to preserve all custom styling
                self._apply_stylesheet(stylesheet)
                self._apply_palette(palette)
                self.current_theme = theme_name
                logger.info(f"Applied legacy theme as-is (preserves custom overrides)")
            else:
                # Convert modern theme to legacy format
                legacy_theme = _convert_modern_to_legacy_theme(modern_theme_data)
                
                # Apply the converted legacy theme
                self._apply_stylesheet(legacy_theme.get('stylesheet', ''))
                self._apply_palette(legacy_theme.get('palette', {}))
                self.current_theme = theme_name
                logger.info(f"Applied theme '{theme_name}' in legacy mode (converted from modern)")
            
            # Save theme preference if settings service is available
            if self.settings_service:
                try:
                    self.settings_service.save_theme_preference(theme_name)
                except Exception as e:
                    logger.warning(f"Failed to save theme preference: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to apply modern theme {theme_name}: {e}")
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
            # Reset to system default palette
            app.setPalette(app.style().standardPalette())
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


__all__ = ['LegacyThemeManager']
