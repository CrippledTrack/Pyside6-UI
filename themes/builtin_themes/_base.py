"""
Base theme utilities and shared stylesheet generator.

This module provides the core functionality for generating theme stylesheets
with consistent styling patterns across all built-in themes.
"""

from __future__ import annotations

from typing import Dict, Any


# =============================================================================
# Shared Style Constants
# =============================================================================
# These values are used across all themes for consistency.
# Only override in specific theme files when absolutely necessary.

BORDER_RADIUS_DEFAULT = "4px"  # Standard rounded corners
BORDER_RADIUS_SHARP = "0px"    # For cyberpunk/angular themes


def generate_stylesheet(
    # Main colors
    window_bg: str,
    base_bg: str,
    alt_bg: str,
    text_color: str,
    text_secondary: str,
    # Accent colors
    accent_color: str,
    accent_hover: str,
    accent_pressed: str,
    # Border colors
    border_color: str,
    border_hover: str,
    # Button specific (can differ from accent)
    button_bg: str = None,
    button_text: str = None,
    button_hover: str = None,
    button_pressed: str = None,
    # Style variants
    is_dark: bool = True,
    border_radius: str = BORDER_RADIUS_DEFAULT,
) -> str:
    """Generate an enhanced stylesheet with consistent styling patterns.
    
    This helper function creates polished stylesheets with:
    - Smooth hover transitions (via color gradations)
    - Card-like containers with subtle borders
    - Better focus states
    - Refined scrollbar styling
    - Enhanced list/tree widget items
    
    Args:
        window_bg: Main window background color
        base_bg: Base background for content areas
        alt_bg: Alternative/secondary background color
        text_color: Primary text color
        text_secondary: Secondary/muted text color
        accent_color: Primary accent color for highlights
        accent_hover: Accent color on hover
        accent_pressed: Accent color when pressed
        border_color: Default border color
        border_hover: Border color on hover
        button_bg: Button background (defaults to accent_color)
        button_text: Button text color
        button_hover: Button hover color
        button_pressed: Button pressed color
        is_dark: Whether this is a dark theme
        border_radius: Default border radius for elements
    
    Returns:
        Complete Qt stylesheet string
    """
    # Default button colors to accent if not specified
    button_bg = button_bg or accent_color
    button_text = button_text or ("#ffffff" if is_dark else window_bg)
    button_hover = button_hover or accent_hover
    button_pressed = button_pressed or accent_pressed
    
    # Calculate overlay colors based on theme
    if is_dark:
        hover_overlay = "rgba(255, 255, 255, 0.05)"
        disabled_bg = "rgba(255, 255, 255, 0.08)"
    else:
        hover_overlay = "rgba(0, 0, 0, 0.03)"
        disabled_bg = "rgba(0, 0, 0, 0.05)"
    
    # Card container background (slightly different from base for depth)
    card_bg = alt_bg if is_dark else base_bg
    
    return f"""
        /* ===== Base Widgets ===== */
        QMainWindow {{
            background-color: {window_bg};
        }}
        QWidget {{
            background-color: {window_bg};
            color: {text_color};
        }}
        
        /* ===== Loading Widget ===== */
        #loadingWidget {{
            background-color: {base_bg};
            border-radius: {border_radius};
        }}
        
        /* ===== Tab Widget ===== */
        QTabWidget::pane {{
            border: 1px solid {border_color};
            background-color: {base_bg};
            border-radius: {border_radius};
        }}
        QTabBar::tab {{
            background-color: {alt_bg};
            color: {text_secondary};
            border: 1px solid {border_color};
            border-bottom: none;
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        QTabBar::tab:selected {{
            background-color: {base_bg};
            color: {text_color};
            border-bottom-color: {base_bg};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {card_bg};
        }}
        
        /* ===== Buttons ===== */
        QPushButton {{
            background-color: {button_bg};
            color: {button_text};
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        }}
        QPushButton:hover {{
            background-color: {button_hover};
        }}
        QPushButton:pressed {{
            background-color: {button_pressed};
        }}
        QPushButton:disabled {{
            background-color: {disabled_bg};
            color: {text_secondary};
            border: 1px solid {border_color};
        }}
        
        /* ===== Input Fields ===== */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            border: 1px solid {border_color};
            border-radius: 4px;
            padding: 6px 8px;
            background-color: {base_bg};
            color: {text_color};
            selection-background-color: {accent_color};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {accent_color};
        }}
        QLineEdit:disabled, QTextEdit:disabled {{
            background-color: {alt_bg};
            color: {text_secondary};
        }}
        
        /* ===== SpinBox ===== */
        QSpinBox, QDoubleSpinBox {{
            border: 1px solid {border_color};
            border-radius: 4px;
            padding: 4px 8px;
            background-color: {base_bg};
            color: {text_color};
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {accent_color};
        }}
        QSpinBox::up-button, QSpinBox::down-button,
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
            subcontrol-origin: border;
            background-color: {alt_bg};
            border: none;
            width: 16px;
        }}
        QSpinBox::up-button {{
            subcontrol-position: top right;
            border-top-right-radius: 3px;
        }}
        QSpinBox::down-button {{
            subcontrol-position: bottom right;
            border-bottom-right-radius: 3px;
        }}
        QDoubleSpinBox::up-button {{
            subcontrol-position: top right;
            border-top-right-radius: 3px;
        }}
        QDoubleSpinBox::down-button {{
            subcontrol-position: bottom right;
            border-bottom-right-radius: 3px;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover,
        QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {border_hover};
        }}
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
            image: none;
            border-left: 3px solid transparent;
            border-right: 3px solid transparent;
            border-bottom: 3px solid {text_color};
            width: 0;
            height: 0;
        }}
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
            image: none;
            border-left: 3px solid transparent;
            border-right: 3px solid transparent;
            border-top: 3px solid {text_color};
            width: 0;
            height: 0;
        }}
        
        /* ===== ComboBox ===== */
        QComboBox {{
            border: 1px solid {border_color};
            border-radius: 4px;
            padding: 6px 8px;
            background-color: {base_bg};
            color: {text_color};
        }}
        QComboBox:focus {{
            border-color: {accent_color};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: 1px solid {border_color};
            background-color: {alt_bg};
        }}
        QComboBox::drop-down:hover {{
            background-color: {border_hover};
        }}
        QComboBox QAbstractItemView {{
            background-color: {base_bg};
            border: 1px solid {border_color};
            selection-background-color: {accent_color};
        }}
        
        /* ===== Labels ===== */
        QLabel {{
            color: {text_color};
            background-color: transparent;
        }}
        
        /* ===== Group Box ===== */
        QGroupBox {{
            border: 1px solid {border_color};
            border-radius: 4px;
            margin: 4px;
            margin-top: 12px;
            padding-top: 12px;
            background-color: {alt_bg};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 6px;
            background-color: {window_bg};
            color: {text_color};
        }}
        
        /* ===== Card Containers (only for explicitly marked frames) ===== */
        QFrame#card, QFrame[card="true"] {{
            background-color: {card_bg};
            border: 1px solid {border_color};
            border-radius: {border_radius};
        }}
        QFrame#cardElevated {{
            background-color: {base_bg};
            border: 1px solid {border_color};
            border-radius: {border_radius};
        }}
        
        /* ===== Scrollbars ===== */
        QScrollBar:vertical {{
            border: none;
            background-color: {base_bg};
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {border_color};
            min-height: 20px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {border_hover};
        }}
        QScrollBar::handle:vertical:pressed {{
            background-color: {accent_color};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QScrollBar:horizontal {{
            border: none;
            background-color: transparent;
            height: 12px;
            margin: 2px 4px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {border_color};
            min-width: 30px;
            border-radius: 5px;
            margin: 2px 0;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {border_hover};
        }}
        QScrollBar::handle:horizontal:pressed {{
            background-color: {accent_color};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}
        
        /* ===== Lists and Trees ===== */
        QListWidget, QListView, QTreeWidget, QTreeView, QTableWidget, QTableView {{
            background-color: {base_bg};
            border: 1px solid {border_color};
            border-radius: 4px;
        }}
        QListWidget::item, QListView::item {{
            padding: 4px;
        }}
        QListWidget::item:selected, QListView::item:selected,
        QTreeWidget::item:selected, QTreeView::item:selected {{
            background-color: {accent_color};
            color: {button_text};
        }}
        QListWidget::item:hover:!selected, QListView::item:hover:!selected {{
            background-color: {hover_overlay};
        }}
        QHeaderView::section {{
            background-color: {alt_bg};
            color: {text_color};
            padding: 6px 8px;
            border: none;
            border-right: 1px solid {border_color};
            border-bottom: 1px solid {border_color};
        }}
        
        /* ===== Checkboxes ===== */
        QCheckBox {{
            color: {text_color};
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {border_color};
            border-radius: 3px;
            background-color: {base_bg};
        }}
        QCheckBox::indicator:hover {{
            border-color: {accent_color};
        }}
        QCheckBox::indicator:checked {{
            background-color: {accent_color};
            border-color: {accent_color};
        }}
        QCheckBox:disabled {{
            color: {text_secondary};
        }}
        
        /* ===== Radio Buttons ===== */
        QRadioButton {{
            color: {text_color};
            spacing: 6px;
        }}
        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {border_color};
            border-radius: 8px;
            background-color: {base_bg};
        }}
        QRadioButton::indicator:hover {{
            border-color: {accent_color};
        }}
        QRadioButton::indicator:checked {{
            background-color: {accent_color};
            border-color: {accent_color};
        }}
        
        /* ===== Progress Bar ===== */
        QProgressBar {{
            border: 1px solid {border_color};
            border-radius: 4px;
            background-color: {alt_bg};
            text-align: center;
            color: {text_color};
        }}
        QProgressBar::chunk {{
            background-color: {accent_color};
            border-radius: 3px;
        }}
        
        /* ===== Sliders ===== */
        QSlider::groove:horizontal {{
            border: none;
            height: 4px;
            background-color: {alt_bg};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background-color: {accent_color};
            border: none;
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
        QSlider::handle:horizontal:hover {{
            background-color: {accent_hover};
        }}
        
        /* ===== Tool Tips ===== */
        QToolTip {{
            background-color: {base_bg};
            color: {text_color};
            border: 1px solid {border_color};
            padding: 4px 8px;
        }}
        
        /* ===== Menus ===== */
        QMenu {{
            background-color: {base_bg};
            border: 1px solid {border_color};
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 20px 6px 12px;
        }}
        QMenu::item:selected {{
            background-color: {accent_color};
            color: {button_text};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {border_color};
            margin: 4px 8px;
        }}
        QMenuBar {{
            background-color: {window_bg};
            border-bottom: 1px solid {border_color};
        }}
        QMenuBar::item {{
            padding: 4px 10px;
        }}
        QMenuBar::item:selected {{
            background-color: {hover_overlay};
        }}
        QMenuBar::item:pressed {{
            background-color: {accent_color};
            color: {button_text};
        }}
        
        /* ===== Status Bar ===== */
        QStatusBar {{
            background-color: {window_bg};
            border-top: 1px solid {border_color};
            padding: 4px;
            color: {text_secondary};
        }}
        QStatusBar::item {{
            border: none;
        }}
        
        /* ===== Message Box ===== */
        QMessageBox {{
            background-color: {base_bg};
        }}
        QMessageBox QLabel {{
            color: {text_color};
        }}
        QMessageBox QPushButton {{
            min-width: 80px;
            min-height: 28px;
        }}
        
        /* ===== Dialog ===== */
        QDialog {{
            background-color: {window_bg};
        }}
        
        /* ===== Splitter ===== */
        QSplitter::handle {{
            background-color: {border_color};
        }}
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        QSplitter::handle:vertical {{
            height: 2px;
        }}
        QSplitter::handle:hover {{
            background-color: {accent_color};
        }}
    """


__all__ = [
    'BORDER_RADIUS_DEFAULT',
    'BORDER_RADIUS_SHARP',
    'generate_stylesheet',
]

