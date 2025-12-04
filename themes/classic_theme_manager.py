"""
Classic theme manager for old UI mode.

This module uses simple stylesheet templates matching the v2.4.0 pattern.
It extracts colors from modern theme palettes and applies them to a simple
CSS template - no complex conversion needed.

The ClassicThemeManager receives themes from the main ThemeManager rather
than loading them independently, keeping a single source of truth.
"""

from __future__ import annotations

import json
import logging
import platform
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from ..app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


# =============================================================================
# Classic Stylesheet Template
# =============================================================================
# Simple template matching classic pattern - just plug in colors

_CLASSIC_TEMPLATE = """
QMainWindow {{
    background-color: {window};
}}
QWidget {{
    background-color: {window};
    color: {text};
}}
#loadingWidget {{
    background-color: {base};
}}
QTabWidget::pane {{
    border: 1px solid {border};
    background-color: {base};
    border-radius: 4px;
}}
QTabBar::tab {{
    background-color: {base};
    color: {text};
    border: 1px solid {border};
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background-color: {border};
    border-bottom-color: {border};
}}
QTabBar::tab:hover {{
    background-color: {border};
}}
QPushButton {{
    background-color: {highlight};
    color: {highlight_text};
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
}}
QPushButton:hover {{
    background-color: {highlight_hover};
}}
QPushButton:pressed {{
    background-color: {highlight_pressed};
}}
QLineEdit, QTextEdit, QComboBox {{
    border: 1px solid {border};
    border-radius: 4px;
    padding: 4px;
    background-color: {base};
    color: {text};
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {highlight};
}}
QLabel {{
    color: {text};
}}
QMessageBox {{
    background-color: {base};
}}
QMessageBox QPushButton {{
    min-width: 80px;
}}
QScrollBar:vertical {{
    border: none;
    background-color: {base};
    width: 10px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background-color: {border};
    min-height: 20px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {highlight};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    border: none;
    background-color: {base};
    height: 10px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background-color: {border};
    min-width: 20px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {highlight};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
"""


def _get_classic_stylesheet(palette: Dict[str, Any]) -> str:
    """Generate classic stylesheet from palette colors using simple template."""
    if not palette:
        return ""
    
    # Map palette to template variables
    highlight = palette.get('highlight', '#0078d4')
    
    return _CLASSIC_TEMPLATE.format(
        window=palette.get('window', '#1e1e1e'),
        base=palette.get('base', '#2d2d2d'),
        border=palette.get('alternate_base', '#3c3c3c'),
        text=palette.get('text', '#ffffff'),
        highlight=highlight,
        highlight_text=palette.get('highlighted_text', '#ffffff'),
        highlight_hover=_adjust_color(highlight, 0.15),
        highlight_pressed=_adjust_color(highlight, -0.15),
    )


def _adjust_color(color: str, factor: float) -> str:
    """Lighten (positive) or darken (negative) a color."""
    try:
        if color.startswith('#'):
            c = color[1:]
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            if factor > 0:  # lighten
                r = min(255, int(r + (255 - r) * factor))
                g = min(255, int(g + (255 - g) * factor))
                b = min(255, int(b + (255 - b) * factor))
            else:  # darken
                factor = abs(factor)
                r = max(0, int(r * (1 - factor)))
                g = max(0, int(g * (1 - factor)))
                b = max(0, int(b * (1 - factor)))
            return f"#{r:02x}{g:02x}{b:02x}"
    except (ValueError, IndexError):
        pass
    return color


class ClassicThemeManager:
    """Classic theme manager
    
    This manager receives themes from the main ThemeManager and applies
    them with classic-style stylesheets generated from palettes.
    """
    
    def __init__(self, themes_dir: str = "themes", settings_service: Optional["SettingsService"] = None) -> None:
        self.themes_dir = Path(themes_dir)
        self.themes: Dict[str, Any] = {}
        self.builtin_theme_names: set = set()
        self._hidden_theme_names: set = {"ocean_blue"}
        self.settings_service = settings_service
        self.current_theme = ""
        # Don't load themes here - wait for load_themes() to be called
        self.load_custom_themes()
    
    def load_themes(self, themes_dict: Dict[str, Any]) -> None:
        """Load themes from provided dictionary (called by main ThemeManager).
        
        Args:
            themes_dict: Dictionary of theme_name -> theme_data
        """
        for theme_name, theme_data in themes_dict.items():
            stylesheet = theme_data.get('stylesheet', '')
            palette = theme_data.get('palette', {})
            
            # Default theme = system styling
            if theme_name == "default" and not stylesheet.strip():
                self.themes[theme_name] = theme_data
            # All other themes: generate from palette + append any classic overrides
            else:
                base_ss = _get_classic_stylesheet(palette)
                overrides = theme_data.get('legacy_stylesheet', '')
                self.themes[theme_name] = {
                    "name": theme_data.get("name", theme_name),
                    "description": theme_data.get("description", ""),
                    "stylesheet": base_ss + overrides,
                    "palette": palette
                }
        
        self.builtin_theme_names = set(self.themes.keys())
        logger.debug(f"Loaded {len(self.themes)} themes into classic manager")
    
    def is_builtin_theme(self, theme_name: str) -> bool:
        return theme_name in self.builtin_theme_names
    
    def load_custom_themes(self) -> None:
        """Load custom themes from themes directory."""
        if not self.themes_dir.exists():
            return
        
        for theme_file in self.themes_dir.glob("*.json"):
            try:
                with open(theme_file, 'r', encoding='utf-8') as f:
                    theme_data = json.load(f)
                    theme_name = theme_file.stem
                    palette = theme_data.get('palette', {})
                    
                    # Generate base + append any classic overrides
                    if palette:
                        base_ss = _get_classic_stylesheet(palette)
                        overrides = theme_data.get('legacy_stylesheet', '')
                        theme_data['stylesheet'] = base_ss + overrides
                    
                    self.themes[theme_name] = theme_data
                    logger.info(f"Loaded custom theme: {theme_name}")
            except Exception as e:
                logger.error(f"Failed to load theme {theme_file.name}: {e}")
    
    def save_custom_theme(self, theme_name: str, theme_data: Dict[str, Any]) -> bool:
        """Save a custom theme to file."""
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
        return [name for name in self.themes.keys() if name not in self._hidden_theme_names]
    
    def get_current_theme(self) -> str:
        return self.current_theme
    
    def apply_theme(self, theme_name: str) -> bool:
        """Apply a theme to the application."""
        if theme_name not in self.themes:
            logger.error(f"Theme '{theme_name}' not found")
            return False
        
        try:
            theme_data = self.themes[theme_name]
            self._apply_stylesheet(theme_data.get('stylesheet', ''))
            self._apply_palette(theme_data.get('palette', {}))
            self.current_theme = theme_name
            logger.info(f"Applied theme: {theme_name}")
            
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
        """Apply a modern theme using classic stylesheet."""
        try:
            stylesheet = modern_theme_data.get('stylesheet', '')
            palette = modern_theme_data.get('palette', {})
            
            # Default = system styling
            if theme_name == "default" and not stylesheet.strip():
                self._apply_stylesheet('')
                self._apply_palette({})
            # All other themes: generate from palette + append any classic overrides
            else:
                base_ss = _get_classic_stylesheet(palette)
                overrides = modern_theme_data.get('legacy_stylesheet', '')
                self._apply_stylesheet(base_ss + overrides)
                self._apply_palette(palette)
            
            self.current_theme = theme_name
            logger.info(f"Applied theme: {theme_name}")
            
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
        """Detect system dark mode preference."""
        try:
            return QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            try:
                return platform.system().lower() == "linux"
            except Exception:
                return False

    def apply_auto_theme(self, saved_theme: Optional[str] = None) -> str:
        """Apply saved theme or auto-detect dark/light."""
        if saved_theme and saved_theme in self.themes:
            theme_name = saved_theme
        else:
            theme_name = "dark" if self.detect_system_dark_mode() else "light"
        
        self.apply_theme(theme_name)
        return theme_name
    
    def set_settings_service(self, settings_service: Optional["SettingsService"]) -> None:
        self.settings_service = settings_service
    
    def _apply_stylesheet(self, stylesheet: str):
        """Apply stylesheet to application."""
        QApplication.instance().setStyleSheet(stylesheet if stylesheet else "")
    
    def _apply_palette(self, palette_data: Dict[str, Any]):
        """Apply palette to application."""
        app = QApplication.instance()
        
        if not palette_data:
            app.setPalette(app.style().standardPalette())
            return
        
        palette = QPalette()
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
                    color = QColor(color_value)
                elif isinstance(color_value, list) and len(color_value) >= 3:
                    color = QColor(*color_value[:4]) if len(color_value) >= 4 else QColor(*color_value[:3])
                else:
                    continue
                palette.setColor(color_roles[role_name], color)
        
        app.setPalette(palette)


__all__ = ['ClassicThemeManager']
