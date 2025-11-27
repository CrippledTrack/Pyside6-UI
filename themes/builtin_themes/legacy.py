"""Legacy theme - classic Windows 11-inspired styling.

This theme mimics the original look of older scripts with simpler,
flatter styling and minimal visual enhancements.
"""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet


def get_theme() -> Dict[str, Any]:
    """Get Legacy theme data."""
    return {
        "name": "Legacy",
        "description": "Legacy theme based on classic PowerShell script styling with Windows 11-inspired design",
        "stylesheet": generate_stylesheet(
            window_bg="#f3f3f3",
            base_bg="#ffffff",
            alt_bg="#f8f8f8",
            text_color="#000000",
            text_secondary="#666666",
            accent_color="#0078d4",
            accent_hover="#106ebe",
            accent_pressed="#005a9e",
            border_color="#d0d0d0",
            border_hover="#a0a0a0",
            button_bg="#ffffff",
            button_text="#000000",
            button_hover="#f0f0f0",
            button_pressed="#e0e0e0",
            is_dark=False,
        ) + """
            /* ===========================================
               Legacy Overrides - Classic/Simple Styling
               =========================================== */
            
            /* Simpler buttons with borders */
            QPushButton {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                padding: 6px 12px;
                font-weight: normal;
                text-transform: none;
            }
            QPushButton:hover {
                border-color: #0078d4;
            }
            QPushButton:disabled {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
            
            /* Simpler tab styling */
            QTabWidget::pane {
                border-radius: 0px;
            }
            QTabBar::tab {
                border-radius: 0px;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                padding: 6px 12px;
                text-transform: none;
                font-weight: normal;
            }
            QTabBar::tab:selected {
                border-top: 1px solid #d0d0d0; /* Remove the accent color top border */
                border-bottom: 1px solid #ffffff; /* Blend with pane */
            }
            
            /* Basic input fields */
            QLineEdit, QTextEdit, QPlainTextEdit {
                border-radius: 2px;
                padding: 4px 6px;
            }
            QSpinBox, QDoubleSpinBox {
                border-radius: 2px;
                padding: 2px 4px;
            }
            QComboBox {
                border-radius: 2px;
                padding: 4px 6px;
            }
            
            /* Simple group boxes */
            QGroupBox {
                border-radius: 3px;
                margin-top: 8px;
                padding-top: 8px;
            }
            
            /* Basic scrollbars */
            QScrollBar:vertical {
                width: 12px;
            }
            QScrollBar::handle:vertical {
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar:horizontal {
                height: 12px;
            }
            QScrollBar::handle:horizontal {
                border-radius: 6px;
                min-width: 20px;
            }
            
            /* Simple list/tree styling */
            QListWidget, QListView, QTreeWidget, QTreeView, QTableWidget, QTableView {
                border-radius: 2px;
            }
            QListWidget::item, QListView::item {
                padding: 2px;
            }
            
            /* Basic checkboxes */
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 2px;
            }
            
            /* Basic radio buttons */
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
            }
            
            /* Simple progress bar */
            QProgressBar {
                border-radius: 2px;
            }
            QProgressBar::chunk {
                border-radius: 1px;
            }
            
            /* Basic tooltips */
            QToolTip {
                padding: 2px 4px;
            }
            
            /* Simple menus */
            QMenu {
                padding: 2px;
            }
            QMenu::item {
                padding: 4px 16px 4px 8px;
            }
            QMenuBar {
                border-bottom: 1px solid #d0d0d0;
            }
            QMenuBar::item {
                padding: 4px 8px;
            }
            
            /* No card styling - keep frames simple */
            QFrame#card, QFrame[card="true"], QFrame#cardElevated {
                border: none;
                background-color: transparent;
            }
            
            /* Classic header styling */
            QHeaderView::section {
                text-transform: none;
                font-weight: normal;
                padding: 4px;
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
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
