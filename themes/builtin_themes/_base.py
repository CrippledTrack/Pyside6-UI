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

BORDER_RADIUS_DEFAULT = "6px"  # Slightly rounded for modern/material feel
BORDER_RADIUS_SHARP = "0px"    # For cyberpunk/angular themes
BORDER_RADIUS_PILL = "16px"    # For pill-shaped elements

# Material Design spacing and sizing
SPACING_SMALL = "4px"
SPACING_MEDIUM = "8px"
SPACING_LARGE = "16px"


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
        hover_overlay = "rgba(255, 255, 255, 0.08)"
        pressed_overlay = "rgba(255, 255, 255, 0.12)"
        disabled_bg = "rgba(255, 255, 255, 0.08)"
        shadow_color = "rgba(0, 0, 0, 0.4)"
    else:
        hover_overlay = "rgba(0, 0, 0, 0.05)"
        pressed_overlay = "rgba(0, 0, 0, 0.08)"
        disabled_bg = "rgba(0, 0, 0, 0.05)"
        shadow_color = "rgba(0, 0, 0, 0.15)"
    
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
            selection-background-color: {accent_color};
            selection-color: {button_text};
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
            border-top-left-radius: 0;
            top: -1px; /* Align with tab bar */
        }}
        QTabWidget::tab-bar {{
            alignment: left;
            left: 0;
        }}
        QTabBar {{
            background-color: transparent;
            border: none;
        }}
        QTabBar::tab {{
            background-color: {alt_bg};
            color: {text_secondary};
            border: 1px solid {border_color};
            border-bottom: 1px solid {border_color};
            padding: 8px 12px; /* Reduced from 16px to fit more tabs */
            margin-right: 2px;
            border-top-left-radius: {border_radius};
            border-top-right-radius: {border_radius};
            min-width: 60px; /* Reduced from 80px */
            font-weight: 500;
        }}
        QTabBar::tab:selected {{
            background-color: {base_bg};
            color: {text_color};
            border-bottom-color: {base_bg};
            border-top: 2px solid {accent_color};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {hover_overlay};
            color: {text_color};
            border-color: {border_hover};
        }}
        QTabBar::tab:disabled {{
            color: {disabled_bg};
            background-color: transparent;
        }}
        
        /* ===== Buttons ===== */
        QPushButton {{
            background-color: {button_bg};
            color: {button_text};
            border: none;
            padding: 6px 12px; /* Reduced from 8px 16px */
            border-radius: {border_radius};
            font-weight: 600;
            min-height: 0px; /* Explicitly reset to prevent legacy leak */
        }}
        QPushButton:hover {{
            background-color: {button_hover};
            border: 1px solid {accent_color}; /* Subtle highlight */
        }}
        QPushButton:pressed {{
            background-color: {button_pressed};
        }}
        QPushButton:disabled {{
            background-color: {disabled_bg};
            color: {text_secondary};
            border: 1px solid {border_color};
        }}
        /* Flat/Text Button style variants if needed via property */
        QPushButton[flat="true"] {{
            background-color: transparent;
            color: {accent_color};
            border: none;
        }}
        QPushButton[flat="true"]:hover {{
            background-color: {hover_overlay};
        }}
        
        /* ===== Input Fields ===== */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            border: 1px solid {border_color};
            border-radius: {border_radius};
            padding: 6px 8px; /* Reduced from 8px 12px */
            background-color: {base_bg};
            color: {text_color};
            selection-background-color: {accent_color};
            selection-color: {button_text};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border: 2px solid {accent_color};
            padding: 5px 7px; /* Compensate for thicker border */
            background-color: {base_bg};
        }}
        QLineEdit:hover:!focus, QTextEdit:hover:!focus {{
            border-color: {border_hover};
        }}
        QLineEdit:disabled, QTextEdit:disabled {{
            background-color: {alt_bg};
            color: {text_secondary};
            border-color: {border_color};
        }}
        
        /* ===== SpinBox ===== */
        QSpinBox, QDoubleSpinBox {{
            border: 1px solid {border_color};
            border-radius: {border_radius};
            padding: 6px 12px;
            background-color: {base_bg};
            color: {text_color};
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 2px solid {accent_color};
            padding: 5px 11px;
        }}
        QSpinBox:hover:!focus, QDoubleSpinBox:hover:!focus {{
            border-color: {border_hover};
        }}
        QSpinBox::up-button, QSpinBox::down-button,
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
            subcontrol-origin: border;
            background-color: transparent;
            border: none;
            width: 20px;
            margin: 1px;
            border-radius: 2px;
        }}
        QSpinBox::up-button, QDoubleSpinBox::up-button {{
            subcontrol-position: top right;
        }}
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            subcontrol-position: bottom right;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover,
        QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {hover_overlay};
        }}
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 4px solid {text_secondary};
            width: 0;
            height: 0;
        }}
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 4px solid {text_secondary};
            width: 0;
            height: 0;
        }}
        QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {{
            border-bottom-color: {accent_color};
        }}
        QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {{
            border-top-color: {accent_color};
        }}
        
        /* ===== ComboBox ===== */
        QComboBox {{
            border: 1px solid {border_color};
            border-radius: {border_radius};
            padding: 6px 12px;
            background-color: {base_bg};
            color: {text_color};
        }}
        QComboBox:focus {{
            border: 2px solid {accent_color};
            padding: 5px 11px;
        }}
        QComboBox:hover:!focus {{
            border-color: {border_hover};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 24px;
            border-left: none;
            background-color: transparent;
            margin-right: 4px;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {text_secondary};
            width: 0;
            height: 0;
            margin-top: 2px;
        }}
        QComboBox::down-arrow:on {{
            border-top: 5px solid {accent_color};
        }}
        QComboBox QAbstractItemView {{
            background-color: {base_bg};
            border: 1px solid {border_color};
            border-radius: 4px;
            selection-background-color: {accent_color};
            selection-color: {button_text};
            padding: 4px;
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 8px;
            border-radius: 2px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {hover_overlay};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {accent_color};
        }}
        
        /* ===== Labels ===== */
        QLabel {{
            color: {text_color};
            background-color: transparent;
            border: none;
            padding: 0;
            border-radius: 0;
        }}
        
        /* ===== Group Box ===== */
        QGroupBox {{
            border: 1px solid {border_color};
            border-radius: {border_radius};
            margin-top: 20px;
            padding-top: 10px;
            background-color: {alt_bg};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 4px;
            background-color: transparent;
            color: {accent_color};
            font-weight: bold;
        }}
        
        /* ===== Card Containers ===== */
        QFrame#card, QFrame[card="true"] {{
            background-color: {card_bg};
            border: 1px solid {border_color};
            border-radius: {border_radius};
            margin: 4px;
        }}
        QFrame#cardElevated {{
            background-color: {base_bg};
            border: 1px solid {border_color};
            border-radius: {border_radius};
            /* Attempt simple shadow simulation via border-bottom/right */
            border-bottom: 2px solid {border_color};
            border-right: 2px solid {border_color};
        }}
        
        /* ===== Scrollbars ===== */
        QScrollBar:vertical {{
            border: none;
            background-color: transparent;
            width: 12px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background-color: {border_color};
            min-height: 20px;
            border-radius: 6px;
            margin: 2px;
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
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {border_color};
            min-width: 30px;
            border-radius: 6px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {border_hover};
        }}
        QScrollBar::handle:horizontal:pressed {{
            background-color: {accent_color};
        }}
        
        /* ===== Lists and Trees ===== */
        QListWidget, QListView, QTreeWidget, QTreeView, QTableWidget, QTableView {{
            background-color: {base_bg};
            border: 1px solid {border_color};
            border-radius: {border_radius};
            outline: none;
        }}
        QListWidget::item, QListView::item, QTreeWidget::item, QTreeView::item {{
            padding: 4px; /* Reduced padding to save space */
            border-radius: 4px;
            margin: 1px 4px;
        }}
        QListWidget::item:selected, QListView::item:selected,
        QTreeWidget::item:selected, QTreeView::item:selected {{
            background-color: {accent_color};
            color: {button_text};
        }}
        QListWidget::item:hover:!selected, QListView::item:hover:!selected,
        QTreeWidget::item:hover:!selected, QTreeView::item:hover:!selected {{
            background-color: {hover_overlay};
        }}
        QHeaderView::section {{
            background-color: {base_bg};
            color: {text_secondary};
            padding: 4px 6px; /* Reduced padding */
            border: none;
            border-bottom: 2px solid {border_color};
            font-weight: bold;
        }}
        QTableCornerButton::section {{
            background-color: {base_bg};
            border: none;
            border-bottom: 2px solid {border_color};
        }}
        
        /* ===== Checkboxes ===== */
        QCheckBox {{
            color: {text_color};
            spacing: 8px;
            padding: 4px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {border_color};
            border-radius: 3px;
            background-color: {base_bg};
        }}
        QCheckBox::indicator:hover {{
            border-color: {accent_color};
            background-color: {hover_overlay};
        }}
        QCheckBox::indicator:checked {{
            background-color: {accent_color};
            border-color: {accent_color};
            image: url(checkbox_check.png); /* Fallback or remove if no image, usually just color is enough for flat */
        }}
        QCheckBox:disabled {{
            color: {text_secondary};
        }}
        
        /* ===== Radio Buttons ===== */
        QRadioButton {{
            color: {text_color};
            spacing: 8px;
            padding: 4px;
        }}
        QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {border_color};
            border-radius: 10px;
            background-color: {base_bg};
        }}
        QRadioButton::indicator:hover {{
            border-color: {accent_color};
            background-color: {hover_overlay};
        }}
        QRadioButton::indicator:checked {{
            background-color: {base_bg};
            border: 5px solid {accent_color}; /* Dot effect */
        }}
        
        /* ===== Progress Bar ===== */
        QProgressBar {{
            border: none;
            border-radius: 4px;
            background-color: {alt_bg};
            text-align: center;
            color: {text_color};
            min-height: 8px;
            max-height: 12px;
        }}
        QProgressBar::chunk {{
            background-color: {accent_color};
            border-radius: 4px;
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
            border: 2px solid {base_bg}; /* Material ring effect */
            width: 16px;
            height: 16px;
            margin: -6px 0;
            border-radius: 9px;
        }}
        QSlider::handle:horizontal:hover {{
            background-color: {accent_hover};
            margin: -7px 0; /* Grow effect */
            width: 18px;
            height: 18px;
            border-radius: 10px;
        }}
        
        /* ===== Tool Tips ===== */
        QToolTip {{
            background-color: {text_color}; /* Inverted */
            color: {base_bg};
            border: none;
            border-radius: 4px;
            padding: 6px 10px;
            opacity: 230;
        }}
        
        /* ===== Menus ===== */
        QMenu {{
            background-color: {base_bg};
            border: 1px solid {border_color};
            border-radius: {border_radius};
            padding: 4px 0;
            /* No native shadow in style sheet, relying on window manager or border */
        }}
        QMenu::item {{
            padding: 8px 32px 8px 16px; /* Extra right pad for shortcut */
            margin: 2px 4px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {hover_overlay};
            color: {text_color};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {border_color};
            margin: 4px 16px;
        }}
        QMenuBar {{
            background-color: {window_bg};
            border-bottom: 1px solid {border_color};
        }}
        QMenuBar::item {{
            padding: 8px 12px;
            background-color: transparent;
            border-radius: 4px;
            margin: 2px;
        }}
        QMenuBar::item:selected {{
            background-color: {hover_overlay};
        }}
        QMenuBar::item:pressed {{
            background-color: {pressed_overlay};
            color: {text_color};
        }}
        
        /* ===== Status Bar ===== */
        QStatusBar {{
            background-color: {window_bg};
            border-top: 1px solid {border_color};
            padding: 4px 8px;
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
            min-height: 32px;
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
    'BORDER_RADIUS_PILL',
    'generate_stylesheet',
]
