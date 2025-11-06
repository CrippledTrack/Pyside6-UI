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

if TYPE_CHECKING:
    from ..app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class ThemeManager:
    """Manages application themes including loading, saving, and applying themes"""
    
    def __init__(self, themes_dir: str = "themes", settings_service: Optional["SettingsService"] = None) -> None:
        self.themes_dir = Path(themes_dir)
        self.themes: Dict[str, Any] = {}
        self.settings_service = settings_service
        self.load_builtin_themes()
        self.load_custom_themes()
    
    def load_builtin_themes(self) -> None:
        """Load built-in themes"""
        self.themes.update({
            "dark": self._get_dark_theme(),
            "light": self._get_light_theme(),
            "blue": self._get_blue_theme(),
            "green": self._get_green_theme(),
            "purple": self._get_purple_theme(),
            "orange": self._get_orange_theme(),
            "red": self._get_red_theme(),
            "cyberpunk": self._get_cyberpunk_theme(),
            "minimal": self._get_minimal_theme(),
            "legacy": self._get_legacy_theme(),
            "ocean_blue": self._get_ocean_blue_theme()
        })
    
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
        return list(self.themes.keys())
    
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
            theme_name = "ocean_blue" if is_dark else "light"
            logger.info(f"Applying auto-detected theme: {theme_name}")
        
        self.apply_theme(theme_name)
        return theme_name
    
    def set_settings_service(self, settings_service: Optional["SettingsService"]) -> None:
        """Set the settings service for theme persistence"""
        self.settings_service = settings_service
    
    def _apply_stylesheet(self, stylesheet: str):
        """Apply stylesheet to the application"""
        if stylesheet:
            QApplication.instance().setStyleSheet(stylesheet)
    
    def _apply_palette(self, palette_data: Dict[str, Any]):
        """Apply color palette to the application"""
        if not palette_data:
            return
        
        app = QApplication.instance()
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
    
    def _get_default_theme(self) -> Dict[str, Any]:
        """Get default theme data"""
        return {
            "name": "Default",
            "description": "Default system theme",
            "stylesheet": "",
            "palette": {            }
        }
    
    def _get_legacy_theme(self) -> Dict[str, Any]:
        """Get legacy theme data based on classic PowerShell script styling"""
        return {
            "name": "Legacy",
            "description": "Legacy theme based on classic PowerShell script styling with Windows 11-inspired design",
            "stylesheet": """
                QMainWindow {
                    background-color: #f3f3f3;
                    font-family: "Segoe UI";
                }
                QWidget {
                    background-color: #f3f3f3;
                    color: #000000;
                    font-family: "Segoe UI";
                }
                #loadingWidget {
                    background-color: #ffffff;
                }
                QTabWidget::pane {
                    border: 1px solid #d0d0d0;
                    background-color: #ffffff;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background-color: #f0f0f0;
                    color: #000000;
                    border: 1px solid #d0d0d0;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    font-family: "Segoe UI";
                    font-size: 9pt;
                }
                QTabBar::tab:selected {
                    background-color: #ffffff;
                    border-bottom-color: #ffffff;
                    font-weight: bold;
                }
                QTabBar::tab:hover {
                    background-color: #e8e8e8;
                }
                QPushButton {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #d0d0d0;
                    padding: 6px 12px;
                    border-radius: 3px;
                    font-family: "Segoe UI";
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #f8f8f8;
                    border-color: #a0a0a0;
                }
                QPushButton:pressed {
                    background-color: #e0e0e0;
                    border-color: #808080;
                }
                QLineEdit, QTextEdit, QComboBox {
                    border: 1px solid #d0d0d0;
                    border-radius: 3px;
                    padding: 4px;
                    background-color: #ffffff;
                    color: #000000;
                    font-family: "Segoe UI";
                    font-size: 9pt;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                    border-color: #0078d4;
                    outline: none;
                }
                QLabel {
                    color: #000000;
                    font-family: "Segoe UI";
                    font-size: 9pt;
                }
                QMessageBox {
                    background-color: #ffffff;
                    font-family: "Segoe UI";
                }
                QMessageBox QPushButton {
                    min-width: 80px;
                    background-color: #ffffff;
                    border: 1px solid #d0d0d0;
                }
                QScrollBar:vertical {
                    border: none;
                    background-color: #f0f0f0;
                    width: 12px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background-color: #c0c0c0;
                    min-height: 20px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #a0a0a0;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar:horizontal {
                    border: none;
                    background-color: #f0f0f0;
                    height: 12px;
                    margin: 0px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #c0c0c0;
                    min-width: 20px;
                    border-radius: 6px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #a0a0a0;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                }
                QCheckBox {
                    color: #000000;
                    font-family: "Segoe UI";
                    font-size: 9pt;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border: 1px solid #d0d0d0;
                    background-color: #ffffff;
                    border-radius: 2px;
                }
                QCheckBox::indicator:checked {
                    background-color: #0078d4;
                    border-color: #0078d4;
                }
                QCheckBox::indicator:hover {
                    border-color: #a0a0a0;
                }
                QListWidget, QTreeWidget {
                    background-color: #ffffff;
                    border: 1px solid #d0d0d0;
                    border-radius: 3px;
                    font-family: "Segoe UI";
                    font-size: 9pt;
                }
                QListWidget::item, QTreeWidget::item {
                    padding: 4px;
                }
                QListWidget::item:selected, QTreeWidget::item:selected {
                    background-color: #0078d4;
                    color: #ffffff;
                }
                QListWidget::item:hover, QTreeWidget::item:hover {
                    background-color: #f0f0f0;
                }
                QGroupBox {
                    font-family: "Segoe UI";
                    font-size: 9pt;
                    font-weight: bold;
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    margin-top: 8px;
                    padding-top: 8px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 8px;
                    padding: 0 4px 0 4px;
                    color: #000000;
                }
                QProgressBar {
                    border: 1px solid #d0d0d0;
                    border-radius: 3px;
                    background-color: #f0f0f0;
                    text-align: center;
                    font-family: "Segoe UI";
                    font-size: 9pt;
                }
                QProgressBar::chunk {
                    background-color: #0078d4;
                    border-radius: 2px;
                }
                QTextEdit {
                    background-color: #ffffff;
                    border: 1px solid #d0d0d0;
                    border-radius: 3px;
                    padding: 4px;
                    font-family: "Segoe UI";
                    font-size: 9pt;
                }
                QTextEdit:focus {
                    border-color: #0078d4;
                }
                QListView {
                    background-color: #ffffff;
                    border: 1px solid #d0d0d0;
                    border-radius: 3px;
                    font-family: "Segoe UI";
                    font-size: 9pt;
                }
                QListView::item {
                    padding: 4px;
                }
                QListView::item:selected {
                    background-color: #0078d4;
                    color: #ffffff;
                }
                QListView::item:hover {
                    background-color: #f0f0f0;
                }
                QFrame {
                    background-color: #ffffff;
                    border: 1px solid #d0d0d0;
                    border-radius: 3px;
                }
                QToolTip {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #d0d0d0;
                    border-radius: 3px;
                    padding: 4px;
                    font-family: "Segoe UI";
                    font-size: 8pt;
                }
            """,
            "palette": {
                "window": "#f3f3f3",
                "window_text": "#000000",
                "base": "#ffffff",
                "alternate_base": "#f8f8f8",
                "tool_tip_base": "#ffffff",
                "tool_tip_text": "#000000",
                "text": "#000000",
                "button": "#ffffff",
                "button_text": "#000000",
                "bright_text": "#0078d4",
                "link": "#0078d4",
                "highlight": "#0078d4",
                "highlighted_text": "#ffffff"
            }
        }
    
    def _get_dark_theme(self) -> Dict[str, Any]:
        """Get dark theme data"""
        return {
            "name": "Dark",
            "description": "Dark theme with purple accents",
            "stylesheet": """
                QMainWindow {
                    background-color: #1e1e1e;
                }
                QWidget {
                    background-color: #1e1e1e;
                    color: #ffffff;
                }
                #loadingWidget {
                    background-color: #2d2d2d;
                }
                QTabWidget::pane {
                    border: 1px solid #3c3c3c;
                    background-color: #2d2d2d;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #3c3c3c;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: #3c3c3c;
                    border-bottom-color: #3c3c3c;
                }
                QTabBar::tab:hover {
                    background-color: #3c3c3c;
                }
                QPushButton {
                    background-color: #6c3483;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #884ea0;
                }
                QPushButton:pressed {
                    background-color: #512e5f;
                }
                QLineEdit, QTextEdit, QComboBox {
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    padding: 4px;
                    background-color: #2d2d2d;
                    color: #ffffff;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                    border-color: #6c3483;
                }
                QLabel {
                    color: #ffffff;
                }
                QMessageBox {
                    background-color: #2d2d2d;
                }
                QMessageBox QPushButton {
                    min-width: 80px;
                }
                QScrollBar:vertical {
                    border: none;
                    background-color: #2d2d2d;
                    width: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background-color: #3c3c3c;
                    min-height: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #4c4c4c;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar:horizontal {
                    border: none;
                    background-color: #2d2d2d;
                    height: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #3c3c3c;
                    min-width: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #4c4c4c;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                }
            """,
            "palette": {
                "window": "#1e1e1e",
                "window_text": "#ffffff",
                "base": "#2d2d2d",
                "alternate_base": "#353535",
                "tool_tip_base": "#ffffff",
                "tool_tip_text": "#000000",
                "text": "#ffffff",
                "button": "#2d2d2d",
                "button_text": "#ffffff",
                "bright_text": "#ff0000",
                "link": "#6c3483",
                "highlight": "#6c3483",
                "highlighted_text": "#ffffff"
            }
        }
    
    def _get_light_theme(self) -> Dict[str, Any]:
        """Get light theme data"""
        return {
            "name": "Light",
            "description": "Light theme with blue accents",
            "stylesheet": """
                QMainWindow {
                    background-color: #f0f0f0;
                }
                QWidget {
                    background-color: #f0f0f0;
                    color: #000000;
                }
                #loadingWidget {
                    background-color: #ffffff;
                }
                QTabWidget::pane {
                    border: 1px solid #cccccc;
                    background-color: #ffffff;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background-color: #e0e0e0;
                    color: #000000;
                    border: 1px solid #cccccc;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: #ffffff;
                    border-bottom-color: #ffffff;
                }
                QTabBar::tab:hover {
                    background-color: #f5f5f5;
                }
                QPushButton {
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #106ebe;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
                QLineEdit, QTextEdit, QComboBox {
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px;
                    background-color: white;
                    color: #000000;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                    border-color: #0078d4;
                }
                QLabel {
                    color: #333333;
                }
                QMessageBox {
                    background-color: white;
                }
                QMessageBox QPushButton {
                    min-width: 80px;
                }
                QScrollBar:vertical {
                    border: none;
                    background-color: #f0f0f0;
                    width: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background-color: #c0c0c0;
                    min-height: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #a0a0a0;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar:horizontal {
                    border: none;
                    background-color: #f0f0f0;
                    height: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #c0c0c0;
                    min-width: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #a0a0a0;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                }
            """,
            "palette": {
                "window": "#f0f0f0",
                "window_text": "#000000",
                "base": "#ffffff",
                "alternate_base": "#e9e9e9",
                "tool_tip_base": "#ffffff",
                "tool_tip_text": "#000000",
                "text": "#000000",
                "button": "#f0f0f0",
                "button_text": "#000000",
                "bright_text": "#ff0000",
                "link": "#0078d4",
                "highlight": "#0078d4",
                "highlighted_text": "#ffffff"
            }
        }
    
    def _get_blue_theme(self) -> Dict[str, Any]:
        """Get blue theme data"""
        return {
            "name": "Blue",
            "description": "Blue theme with modern styling",
            "stylesheet": """
                QMainWindow {
                    background-color: #1a1a2e;
                }
                QWidget {
                    background-color: #1a1a2e;
                    color: #ffffff;
                }
                #loadingWidget {
                    background-color: #16213e;
                }
                QTabWidget::pane {
                    border: 1px solid #0f3460;
                    background-color: #16213e;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background-color: #16213e;
                    color: #ffffff;
                    border: 1px solid #0f3460;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: #0f3460;
                    border-bottom-color: #0f3460;
                }
                QTabBar::tab:hover {
                    background-color: #0f3460;
                }
                QPushButton {
                    background-color: #e94560;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #f06292;
                }
                QPushButton:pressed {
                    background-color: #c2185b;
                }
                QLineEdit, QTextEdit, QComboBox {
                    border: 1px solid #0f3460;
                    border-radius: 4px;
                    padding: 4px;
                    background-color: #16213e;
                    color: #ffffff;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                    border-color: #e94560;
                }
                QLabel {
                    color: #ffffff;
                }
                QMessageBox {
                    background-color: #16213e;
                }
                QMessageBox QPushButton {
                    min-width: 80px;
                }
                QScrollBar:vertical {
                    border: none;
                    background-color: #16213e;
                    width: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background-color: #0f3460;
                    min-height: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #e94560;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar:horizontal {
                    border: none;
                    background-color: #16213e;
                    height: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #0f3460;
                    min-width: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #e94560;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                }
            """,
            "palette": {
                "window": "#1a1a2e",
                "window_text": "#ffffff",
                "base": "#16213e",
                "alternate_base": "#0f3460",
                "tool_tip_base": "#ffffff",
                "tool_tip_text": "#000000",
                "text": "#ffffff",
                "button": "#16213e",
                "button_text": "#ffffff",
                "bright_text": "#e94560",
                "link": "#e94560",
                "highlight": "#e94560",
                "highlighted_text": "#ffffff"
            }
        }
    
    def _get_green_theme(self) -> Dict[str, Any]:
        """Get green theme data"""
        return {
            "name": "Green",
            "description": "Green theme with nature-inspired colors",
            "stylesheet": """
                QMainWindow {
                    background-color: #1b4332;
                }
                QWidget {
                    background-color: #1b4332;
                    color: #ffffff;
                }
                #loadingWidget {
                    background-color: #2d6a4f;
                }
                QTabWidget::pane {
                    border: 1px solid #40916c;
                    background-color: #2d6a4f;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background-color: #2d6a4f;
                    color: #ffffff;
                    border: 1px solid #40916c;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: #40916c;
                    border-bottom-color: #40916c;
                }
                QTabBar::tab:hover {
                    background-color: #40916c;
                }
                QPushButton {
                    background-color: #95d5b2;
                    color: #1b4332;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #b7e4c7;
                }
                QPushButton:pressed {
                    background-color: #74c69d;
                }
                QLineEdit, QTextEdit, QComboBox {
                    border: 1px solid #40916c;
                    border-radius: 4px;
                    padding: 4px;
                    background-color: #2d6a4f;
                    color: #ffffff;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                    border-color: #95d5b2;
                }
                QLabel {
                    color: #ffffff;
                }
                QMessageBox {
                    background-color: #2d6a4f;
                }
                QMessageBox QPushButton {
                    min-width: 80px;
                }
                QScrollBar:vertical {
                    border: none;
                    background-color: #2d6a4f;
                    width: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background-color: #40916c;
                    min-height: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #95d5b2;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar:horizontal {
                    border: none;
                    background-color: #2d6a4f;
                    height: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #40916c;
                    min-width: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #95d5b2;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                }
            """,
            "palette": {
                "window": "#1b4332",
                "window_text": "#ffffff",
                "base": "#2d6a4f",
                "alternate_base": "#40916c",
                "tool_tip_base": "#ffffff",
                "tool_tip_text": "#000000",
                "text": "#ffffff",
                "button": "#2d6a4f",
                "button_text": "#ffffff",
                "bright_text": "#95d5b2",
                "link": "#95d5b2",
                "highlight": "#95d5b2",
                "highlighted_text": "#1b4332"
            }
        }
    
    def _get_purple_theme(self) -> Dict[str, Any]:
        """Get purple theme data"""
        return {
            "name": "Purple",
            "description": "Purple theme with elegant styling",
            "stylesheet": """
                QMainWindow {
                    background-color: #2d1b69;
                }
                QWidget {
                    background-color: #2d1b69;
                    color: #ffffff;
                }
                #loadingWidget {
                    background-color: #3c096c;
                }
                QTabWidget::pane {
                    border: 1px solid #5a189a;
                    background-color: #3c096c;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background-color: #3c096c;
                    color: #ffffff;
                    border: 1px solid #5a189a;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: #5a189a;
                    border-bottom-color: #5a189a;
                }
                QTabBar::tab:hover {
                    background-color: #5a189a;
                }
                QPushButton {
                    background-color: #c77dff;
                    color: #2d1b69;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #e0aaff;
                }
                QPushButton:pressed {
                    background-color: #9d4edd;
                }
                QLineEdit, QTextEdit, QComboBox {
                    border: 1px solid #5a189a;
                    border-radius: 4px;
                    padding: 4px;
                    background-color: #3c096c;
                    color: #ffffff;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                    border-color: #c77dff;
                }
                QLabel {
                    color: #ffffff;
                }
                QMessageBox {
                    background-color: #3c096c;
                }
                QMessageBox QPushButton {
                    min-width: 80px;
                }
                QScrollBar:vertical {
                    border: none;
                    background-color: #3c096c;
                    width: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background-color: #5a189a;
                    min-height: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #c77dff;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar:horizontal {
                    border: none;
                    background-color: #3c096c;
                    height: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #5a189a;
                    min-width: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #c77dff;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                }
            """,
            "palette": {
                "window": "#2d1b69",
                "window_text": "#ffffff",
                "base": "#3c096c",
                "alternate_base": "#5a189a",
                "tool_tip_base": "#ffffff",
                "tool_tip_text": "#000000",
                "text": "#ffffff",
                "button": "#3c096c",
                "button_text": "#ffffff",
                "bright_text": "#c77dff",
                "link": "#c77dff",
                "highlight": "#c77dff",
                "highlighted_text": "#2d1b69"
            }
        }
    
    def _get_orange_theme(self) -> Dict[str, Any]:
        """Get orange theme data"""
        return {
            "name": "Orange",
            "description": "Orange theme with warm colors",
            "stylesheet": """
                QMainWindow {
                    background-color: #783937;
                }
                QWidget {
                    background-color: #783937;
                    color: #ffffff;
                }
                #loadingWidget {
                    background-color: #9c6644;
                }
                QTabWidget::pane {
                    border: 1px solid #b08968;
                    background-color: #9c6644;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background-color: #9c6644;
                    color: #ffffff;
                    border: 1px solid #b08968;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: #b08968;
                    border-bottom-color: #b08968;
                }
                QTabBar::tab:hover {
                    background-color: #b08968;
                }
                QPushButton {
                    background-color: #ddb892;
                    color: #783937;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #e6ccb2;
                }
                QPushButton:pressed {
                    background-color: #c4a484;
                }
                QLineEdit, QTextEdit, QComboBox {
                    border: 1px solid #b08968;
                    border-radius: 4px;
                    padding: 4px;
                    background-color: #9c6644;
                    color: #ffffff;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                    border-color: #ddb892;
                }
                QLabel {
                    color: #ffffff;
                }
                QMessageBox {
                    background-color: #9c6644;
                }
                QMessageBox QPushButton {
                    min-width: 80px;
                }
                QScrollBar:vertical {
                    border: none;
                    background-color: #9c6644;
                    width: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background-color: #b08968;
                    min-height: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #ddb892;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar:horizontal {
                    border: none;
                    background-color: #9c6644;
                    height: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #b08968;
                    min-width: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #ddb892;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                }
            """,
            "palette": {
                "window": "#783937",
                "window_text": "#ffffff",
                "base": "#9c6644",
                "alternate_base": "#b08968",
                "tool_tip_base": "#ffffff",
                "tool_tip_text": "#000000",
                "text": "#ffffff",
                "button": "#9c6644",
                "button_text": "#ffffff",
                "bright_text": "#ddb892",
                "link": "#ddb892",
                "highlight": "#ddb892",
                "highlighted_text": "#783937"
            }
        }
    
    def _get_red_theme(self) -> Dict[str, Any]:
        """Get red theme data"""
        return {
            "name": "Red",
            "description": "Red theme with bold styling",
            "stylesheet": """
                QMainWindow {
                    background-color: #660708;
                }
                QWidget {
                    background-color: #660708;
                    color: #ffffff;
                }
                #loadingWidget {
                    background-color: #a4161a;
                }
                QTabWidget::pane {
                    border: 1px solid #ba181b;
                    background-color: #a4161a;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background-color: #a4161a;
                    color: #ffffff;
                    border: 1px solid #ba181b;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: #ba181b;
                    border-bottom-color: #ba181b;
                }
                QTabBar::tab:hover {
                    background-color: #ba181b;
                }
                QPushButton {
                    background-color: #dc2f02;
                    color: #ffffff;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #e85d04;
                }
                QPushButton:pressed {
                    background-color: #b91c1c;
                }
                QLineEdit, QTextEdit, QComboBox {
                    border: 1px solid #ba181b;
                    border-radius: 4px;
                    padding: 4px;
                    background-color: #a4161a;
                    color: #ffffff;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                    border-color: #dc2f02;
                }
                QLabel {
                    color: #ffffff;
                }
                QMessageBox {
                    background-color: #a4161a;
                }
                QMessageBox QPushButton {
                    min-width: 80px;
                }
                QScrollBar:vertical {
                    border: none;
                    background-color: #a4161a;
                    width: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background-color: #ba181b;
                    min-height: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #dc2f02;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar:horizontal {
                    border: none;
                    background-color: #a4161a;
                    height: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #ba181b;
                    min-width: 20px;
                    border-radius: 5px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #dc2f02;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                }
            """,
            "palette": {
                "window": "#660708",
                "window_text": "#ffffff",
                "base": "#a4161a",
                "alternate_base": "#ba181b",
                "tool_tip_base": "#ffffff",
                "tool_tip_text": "#000000",
                "text": "#ffffff",
                "button": "#a4161a",
                "button_text": "#ffffff",
                "bright_text": "#dc2f02",
                "link": "#dc2f02",
                "highlight": "#dc2f02",
                "highlighted_text": "#ffffff"
            }
        }
    
    def _get_cyberpunk_theme(self) -> Dict[str, Any]:
        """Get cyberpunk theme data"""
        return {
            "name": "Cyberpunk",
            "description": "Cyberpunk theme with neon colors",
            "stylesheet": """
                QMainWindow {
                    background-color: #0a0a0a;
                }
                QWidget {
                    background-color: #0a0a0a;
                    color: #00ff41;
                }
                #loadingWidget {
                    background-color: #1a1a1a;
                }
                QTabWidget::pane {
                    border: 2px solid #00ff41;
                    background-color: #1a1a1a;
                    border-radius: 0px;
                }
                QTabBar::tab {
                    background-color: #1a1a1a;
                    color: #00ff41;
                    border: 2px solid #00ff41;
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 0px;
                    border-top-right-radius: 0px;
                }
                QTabBar::tab:selected {
                    background-color: #00ff41;
                    color: #0a0a0a;
                    border-bottom-color: #00ff41;
                }
                QTabBar::tab:hover {
                    background-color: #00cc33;
                    color: #0a0a0a;
                }
                QPushButton {
                    background-color: #ff006e;
                    color: #ffffff;
                    border: 2px solid #ff006e;
                    padding: 8px 16px;
                    border-radius: 0px;
                }
                QPushButton:hover {
                    background-color: #ff1a7a;
                    border-color: #ff1a7a;
                }
                QPushButton:pressed {
                    background-color: #cc0057;
                    border-color: #cc0057;
                }
                QLineEdit, QTextEdit, QComboBox {
                    border: 2px solid #00ff41;
                    border-radius: 0px;
                    padding: 4px;
                    background-color: #1a1a1a;
                    color: #00ff41;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                    border-color: #ff006e;
                }
                QLabel {
                    color: #00ff41;
                }
                QMessageBox {
                    background-color: #1a1a1a;
                }
                QMessageBox QPushButton {
                    min-width: 80px;
                }
                QScrollBar:vertical {
                    border: none;
                    background-color: #1a1a1a;
                    width: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background-color: #00ff41;
                    min-height: 20px;
                    border-radius: 0px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #ff006e;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar:horizontal {
                    border: none;
                    background-color: #1a1a1a;
                    height: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #00ff41;
                    min-width: 20px;
                    border-radius: 0px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #ff006e;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                }
            """,
            "palette": {
                "window": "#0a0a0a",
                "window_text": "#00ff41",
                "base": "#1a1a1a",
                "alternate_base": "#2a2a2a",
                "tool_tip_base": "#1a1a1a",
                "tool_tip_text": "#00ff41",
                "text": "#00ff41",
                "button": "#1a1a1a",
                "button_text": "#00ff41",
                "bright_text": "#ff006e",
                "link": "#ff006e",
                "highlight": "#ff006e",
                "highlighted_text": "#ffffff"
            }
        }
    
    def _get_minimal_theme(self) -> Dict[str, Any]:
        """Get minimal theme data"""
        return {
            "name": "Minimal",
            "description": "Minimal theme with clean design",
            "stylesheet": """
                QMainWindow {
                    background-color: #ffffff;
                }
                QWidget {
                    background-color: #ffffff;
                    color: #333333;
                }
                #loadingWidget {
                    background-color: #fafafa;
                }
                QTabWidget::pane {
                    border: 1px solid #e0e0e0;
                    background-color: #fafafa;
                    border-radius: 2px;
                }
                QTabBar::tab {
                    background-color: #f5f5f5;
                    color: #666666;
                    border: 1px solid #e0e0e0;
                    padding: 8px 16px;
                    margin-right: 1px;
                    border-top-left-radius: 2px;
                    border-top-right-radius: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #ffffff;
                    color: #333333;
                    border-bottom-color: #ffffff;
                }
                QTabBar::tab:hover {
                    background-color: #f0f0f0;
                }
                QPushButton {
                    background-color: #f8f9fa;
                    color: #333333;
                    border: 1px solid #dee2e6;
                    padding: 8px 16px;
                    border-radius: 2px;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                    border-color: #adb5bd;
                }
                QPushButton:pressed {
                    background-color: #dee2e6;
                }
                QLineEdit, QTextEdit, QComboBox {
                    border: 1px solid #dee2e6;
                    border-radius: 2px;
                    padding: 4px;
                    background-color: #ffffff;
                    color: #333333;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                    border-color: #007bff;
                }
                QLabel {
                    color: #333333;
                }
                QMessageBox {
                    background-color: #ffffff;
                }
                QMessageBox QPushButton {
                    min-width: 80px;
                }
                QScrollBar:vertical {
                    border: none;
                    background-color: #f8f9fa;
                    width: 8px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background-color: #dee2e6;
                    min-height: 20px;
                    border-radius: 4px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #adb5bd;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar:horizontal {
                    border: none;
                    background-color: #f8f9fa;
                    height: 8px;
                    margin: 0px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #dee2e6;
                    min-width: 20px;
                    border-radius: 4px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #adb5bd;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                }
            """,
            "palette": {
                "window": "#ffffff",
                "window_text": "#333333",
                "base": "#fafafa",
                "alternate_base": "#f5f5f5",
                "tool_tip_base": "#ffffff",
                "tool_tip_text": "#333333",
                "text": "#333333",
                "button": "#f8f9fa",
                "button_text": "#333333",
                "bright_text": "#dc3545",
                "link": "#007bff",
                "highlight": "#007bff",
                "highlighted_text": "#ffffff"
            }
        }

    def _get_ocean_blue_theme(self) -> Dict[str, Any]:
        """Get Ocean Blue theme data (integrated from sample_custom_theme.json)"""
        return {
            "name": "Ocean Blue",
            "description": "A calming ocean-inspired theme with blue and teal colors",
            "stylesheet": "QMainWindow {\n    background-color: #0f1419;\n}\nQWidget {\n    background-color: #0f1419;\n    color: #e6f3ff;\n}\n#loadingWidget {\n    background-color: #1a2332;\n}\nQTabWidget::pane {\n    border: 1px solid #2d3748;\n    background-color: #1a2332;\n    border-radius: 4px;\n}\nQTabBar::tab {\n    background-color: #1a2332;\n    color: #e6f3ff;\n    border: 1px solid #2d3748;\n    padding: 8px 16px;\n    margin-right: 2px;\n    border-top-left-radius: 4px;\n    border-top-right-radius: 4px;\n}\nQTabBar::tab:selected {\n    background-color: #2d3748;\n    border-bottom-color: #2d3748;\n}\nQTabBar::tab:hover {\n    background-color: #2d3748;\n}\nQPushButton {\n    background-color: #3182ce;\n    color: white;\n    border: none;\n    padding: 8px 16px;\n    border-radius: 4px;\n}\nQPushButton:hover {\n    background-color: #4299e1;\n}\nQPushButton:pressed {\n    background-color: #2b6cb0;\n}\nQLineEdit, QTextEdit, QComboBox {\n    border: 1px solid #2d3748;\n    border-radius: 4px;\n    padding: 4px;\n    background-color: #1a2332;\n    color: #e6f3ff;\n}\nQLineEdit:focus, QTextEdit:focus, QComboBox:focus {\n    border-color: #3182ce;\n}\nQLabel {\n    color: #e6f3ff;\n}\nQMessageBox {\n    background-color: #1a2332;\n}\nQMessageBox QPushButton {\n    min-width: 80px;\n}\nQScrollBar:vertical {\n    border: none;\n    background-color: #1a2332;\n    width: 10px;\n    margin: 0px;\n}\nQScrollBar::handle:vertical {\n    background-color: #2d3748;\n    min-height: 20px;\n    border-radius: 5px;\n}\nQScrollBar::handle:vertical:hover {\n    background-color: #3182ce;\n}\nQScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {\n    height: 0px;\n}\nQScrollBar:horizontal {\n    border: none;\n    background-color: #1a2332;\n    height: 10px;\n    margin: 0px;\n}\nQScrollBar::handle:horizontal {\n    background-color: #2d3748;\n    min-width: 20px;\n    border-radius: 5px;\n}\nQScrollBar::handle:horizontal:hover {\n    background-color: #3182ce;\n}\nQScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {\n    width: 0px;\n}",
            "palette": {
                "window": "#0f1419",
                "window_text": "#e6f3ff",
                "base": "#1a2332",
                "alternate_base": "#2d3748",
                "tool_tip_base": "#ffffff",
                "tool_tip_text": "#000000",
                "text": "#e6f3ff",
                "button": "#1a2332",
                "button_text": "#e6f3ff",
                "bright_text": "#3182ce",
                "link": "#3182ce",
                "highlight": "#3182ce",
                "highlighted_text": "#ffffff"
            }
        }