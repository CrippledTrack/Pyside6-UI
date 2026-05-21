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
            flat_containers=True,       # Drops modern card rendering wrappers
            winforms_label_quirk=True,  # Applies bordered style onto scoped field labels
            tab_selected_indicator="#adadad",  # Gray top-border on selected tab (classic Windows)
        ) + """
            /* ===========================================
               Legacy Overrides - Classic/Simple Styling
               =========================================== */
            
            /* Simpler buttons with borders - Windows Classic Style */
            QPushButton {
                background-color: #e1e1e1; /* Gradient-ish gray */
                border: 1px solid #adadad;
                border-radius: 2px;
                padding: 4px 12px;
                color: #000000;
                font-weight: normal;
                text-transform: none;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #e5f1fb;
                border-color: #0078d7;
            }
            QPushButton:pressed {
                background-color: #cce4f7;
                border-color: #005499;
            }
            QPushButton:disabled {
                background-color: #f4f4f4;
                border-color: #d9d9d9;
                color: #838383;
            }
            
            /* Classic tab styling */
            QTabWidget::pane {
                border: 1px solid #d9d9d9;
                background-color: #ffffff;
                border-radius: 0px;
                top: -1px;
            }
            QTabWidget::tab-bar {
                left: 5px; /* Slight offset */
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                border: 1px solid #d9d9d9;
                border-bottom: 1px solid #d9d9d9;
                border-top-left-radius: 2px;
                border-top-right-radius: 2px;
                padding: 4px 12px;
                margin-right: -1px;
                color: #000000;
                text-transform: none;
                font-weight: normal;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                border-bottom: 1px solid #ffffff; /* Blend with pane */
                border-top: 2px solid #adadad; /* Gray highlight line */
            }
            QTabBar::tab:hover:!selected {
                background-color: #fdfdfd;
            }
            
            /* Basic input fields - Classic Windows */
            QLineEdit, QTextEdit, QPlainTextEdit {
                border: 1px solid #7a7a7a; /* Darker border */
                border-radius: 0px;
                padding: 3px 5px;
                background-color: #ffffff;
                color: #000000;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #0078d7;
            }
            QSpinBox, QDoubleSpinBox {
                border: 1px solid #7a7a7a;
                border-radius: 0px;
                padding: 2px 4px;
                background-color: #ffffff;
            }
            QComboBox {
                border: 1px solid #7a7a7a;
                border-radius: 0px;
                padding: 3px 5px;
                background-color: #ffffff;
            }
            
            /* Standard Group Boxes - Resetting Base Theme */
            QGroupBox {
                border: 1px solid #d0d0d0;
                border-radius: 2px;
                margin-top: 1.5em; /* Standard space for title */
                padding-top: 20px; 
                padding-bottom: 10px;
                padding-left: 5px;
                padding-right: 5px;
                background-color: transparent; /* Let window bg show */
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                padding: 0 3px;
                background-color: transparent; /* or #f3f3f3 to mask border */
                color: #000000;
                font-weight: bold;
            }
            
            /* Basic scrollbars - Classic Square */
            QScrollBar:vertical {
                width: 16px; /* Standard Windows width */
                background-color: #f0f0f0;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #cdcdcd;
                border-radius: 0px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a6a6a6;
            }
            QScrollBar::add-line:vertical {
                border: none;
                background: #f0f0f0;
                height: 16px;
                subcontrol-position: bottom;
                subcontrol-origin: margin;
            }
            QScrollBar::sub-line:vertical {
                border: none;
                background: #f0f0f0;
                height: 16px;
                subcontrol-position: top;
                subcontrol-origin: margin;
            }
            QScrollBar:horizontal {
                height: 16px;
                background-color: #f0f0f0;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: #cdcdcd;
                border-radius: 0px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #a6a6a6;
            }
            
            /* Simple list/tree styling */
            QListWidget, QListView, QTreeWidget, QTreeView, QTableWidget, QTableView {
                border: 1px solid #7a7a7a;
                border-radius: 0px;
            }
            QListWidget::item, QListView::item {
                padding: 2px;
            }
            
            /* Basic checkboxes - Classic Sharp */
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
                border: 1px solid #333333;
                border-radius: 0px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                /* Fallback to a blue fill to indicate checked state clearly in legacy theme */
                background-color: #0078d7;
                border: 1px solid #333333;
                image: none;
            }
            QCheckBox::indicator:disabled {
                border-color: #888888;
                background-color: #f0f0f0;
            }
            QCheckBox::indicator:checked:disabled {
                background-color: #888888;
            }
            
            /* Basic radio buttons */
            QRadioButton::indicator {
                width: 12px;
                height: 12px;
                border: 1px solid #333333;
                border-radius: 6px; /* Circular but simple */
                background-color: #ffffff;
            }
            QRadioButton::indicator:checked {
                background-color: #000000; /* Simple dot */
                border: 3px solid #ffffff; /* Ring effect */
                outline: 1px solid #333333;
            }
            
            /* Simple progress bar */
            QProgressBar {
                border: 1px solid #7a7a7a;
                border-radius: 0px;
                background-color: #ffffff;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
                border-radius: 0px;
            }
            
            /* Basic tooltips */
            QToolTip {
                padding: 2px 4px;
            }
            
            /* Simple menus - Classic Style */
            QMenu {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                padding: 2px 0px;
                border-radius: 0px;
            }
            QMenu::item {
                padding: 5px 30px 5px 30px;
                border-radius: 0px;
                margin: 0px;
                color: #000000;
            }
            QMenu::item:selected {
                background-color: #e5f3ff;
                color: #000000;
                border: 1px solid #cce8ff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #e0e0e0;
                margin: 4px 10px;
            }

            /* Classic Menu Bar */
            QMenuBar {
                background-color: #f0f0f0;
                border-bottom: 1px solid #d0d0d0;
            }
            QMenuBar::item {
                padding: 6px 10px;
                background-color: transparent;
                border-radius: 0px;
                margin: 0px;
                color: #000000;
            }
            QMenuBar::item:selected {
                background-color: #e5f3ff;
                border: 1px solid #cce8ff;
            }
            QMenuBar::item:pressed {
                background-color: #cce8ff;
                border: 1px solid #99d1ff;
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
        # Classic mode structural tokens (v5.1.0)
        "classic_border_radius": "4px",
        "classic_scrollbar_size": "12px",
        "classic_tab_font_weight": "bold",
        # Classic tab selection — white active tab blending with pane (R3)
        "classic_tab_selected_bg": "#ffffff",
        "classic_tab_selected_text": "#000000",
        # Classic tab hover — subtle gray (G8)
        "classic_tab_hover_bg": "#e8e8e8",
        # Enable WinForms label quirk in classic mode (R4)
        "winforms_label_quirk": True,
        # Classic button overrides — white Windows-style buttons (R5)
        "classic_button_bg": "#ffffff",
        "classic_button_text": "#000000",
        "classic_button_hover": "#f8f8f8",
        "classic_button_pressed": "#e0e0e0",
        "classic_button_border": "1px solid #d0d0d0",
        "classic_button_border_radius": "3px",
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


