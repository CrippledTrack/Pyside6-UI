"""
Classic stylesheet generator for old UI mode.

This module generates simple stylesheets matching the v2.4.0 pattern.
It extracts colors from modern theme palettes and applies them to a simple
CSS template - no complex conversion needed.

Used by ThemeManager when legacy/classic UI mode is enabled.
"""

from __future__ import annotations

import logging
from typing import Dict, Any

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
    background-color: {window};
}}
QTabWidget::pane {{
    border: {border_width} solid {border};
    background-color: {base};
    border-radius: {border_radius};
}}
QTabBar::tab {{
    background-color: {base};
    color: {text};
    border: {border_width} solid {border};
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: {border_radius};
    border-top-right-radius: {border_radius};
}}
QTabBar::tab:selected {{
    background-color: {tab_selected_bg};
    color: {tab_selected_text};
    border-bottom-color: {tab_selected_bg};
    font-weight: {tab_selected_font_weight};
}}
QTabBar::tab:hover {{
    background-color: {tab_hover_bg};
    color: {tab_hover_text};
}}
QPushButton {{
    background-color: {button_bg};
    color: {button_text};
    border: {button_border};
    padding: 8px 16px;
    border-radius: {button_border_radius};
}}
QPushButton:hover {{
    background-color: {button_hover};
}}
QPushButton:pressed {{
    background-color: {button_pressed};
}}
QLineEdit, QTextEdit, QComboBox {{
    border: {border_width} solid {input_border_color};
    border-radius: {border_radius};
    padding: 4px;
    background-color: {base};
    color: {text};
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {highlight};
}}
{label_quirk_block}
QMessageBox {{
    background-color: {base};
}}
QMessageBox QPushButton {{
    min-width: 80px;
}}
QScrollBar:vertical {{
    border: none;
    background-color: {base};
    width: {scrollbar_size};
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background-color: {border};
    min-height: 20px;
    border-radius: {scrollbar_handle_radius};
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
    height: {scrollbar_size};
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background-color: {border};
    min-width: 20px;
    border-radius: {scrollbar_handle_radius};
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {highlight};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
"""


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


def get_classic_stylesheet(theme_data: Dict[str, Any]) -> str:
    """Generate classic stylesheet from theme data.
    
    Takes a modern theme's data and generates a simple classic style stylesheet.
    Uses the palette colors + any theme-specific classic overrides.
    
    Args:
        theme_data: Theme dictionary with 'palette' and optional 'classic_*' override keys
                    (e.g. classic_border_radius, classic_button_bg, winforms_label_quirk).
        
    Returns:
        Complete classic stylesheet string
    """
    palette = theme_data.get('palette', {})
    
    if not palette:
        return ""
    
    # Generate base stylesheet from palette
    highlight = palette.get('highlight', '#0078d4')

    # Safely pull structural token overrides from theme_data (v5.1.0)
    border_width             = theme_data.get('classic_border_width', '1px')
    border_radius            = theme_data.get('classic_border_radius', '4px')
    scrollbar_size           = theme_data.get('classic_scrollbar_size', '10px')
    scrollbar_handle_radius  = theme_data.get('classic_scrollbar_handle_radius', '5px')

    # Tab appearance
    tab_selected_bg = theme_data.get(
        'classic_tab_selected_bg',
        palette.get('alternate_base', '#3c3c3c')
    )
    tab_selected_text = theme_data.get(
        'classic_tab_selected_text',
        palette.get('text', '#ffffff')
    )
    tab_font_weight = theme_data.get('classic_tab_font_weight', 'normal')
    tab_hover_bg = theme_data.get(
        'classic_tab_hover_bg',
        palette.get('alternate_base', '#3c3c3c')
    )
    tab_hover_text = theme_data.get(
        'classic_tab_hover_text',
        palette.get('text', '#ffffff')
    )

    # Button overrides — defaults match the original highlight-coloured button behaviour
    button_bg            = theme_data.get('classic_button_bg', highlight)
    button_text          = theme_data.get('classic_button_text', palette.get('highlighted_text', '#ffffff'))
    button_hover         = theme_data.get('classic_button_hover', _adjust_color(highlight, 0.15))
    button_pressed       = theme_data.get('classic_button_pressed', _adjust_color(highlight, -0.15))
    button_border        = theme_data.get('classic_button_border', 'none')
    button_border_radius = theme_data.get('classic_button_border_radius', border_radius)

    # Input border colour — allows themes like Cyberpunk to use neon border_color
    input_border_color = theme_data.get(
        'classic_input_border_color',
        palette.get('alternate_base', '#3c3c3c')
    )

    # WinForms label quirk — inject bordered QLabel block for classic mode when enabled
    _text = palette.get('text', '#ffffff')
    if theme_data.get('winforms_label_quirk', False):
        label_quirk_block = (
            f"QLabel {{ color: {_text}; border: 1px solid #d9d9d9; padding: 4px 8px; "
            f"background-color: #ffffff; border-radius: 2px; }}\n"
            f"QGroupBox > QLabel, QSplitter > QLabel {{ border: none; "
            f"background-color: transparent; padding: 0; }}"
        )
    else:
        label_quirk_block = f"QLabel {{ color: {_text}; }}"

    base_stylesheet = _CLASSIC_TEMPLATE.format(
        window=palette.get('window', '#1e1e1e'),
        base=palette.get('base', '#2d2d2d'),
        border=palette.get('alternate_base', '#3c3c3c'),
        text=palette.get('text', '#ffffff'),
        highlight=highlight,
        highlight_text=palette.get('highlighted_text', '#ffffff'),
        highlight_hover=_adjust_color(highlight, 0.15),
        highlight_pressed=_adjust_color(highlight, -0.15),
        border_width=border_width,
        border_radius=border_radius,
        scrollbar_size=scrollbar_size,
        scrollbar_handle_radius=scrollbar_handle_radius,
        tab_selected_bg=tab_selected_bg,
        tab_selected_text=tab_selected_text,
        tab_selected_font_weight=tab_font_weight,
        tab_hover_bg=tab_hover_bg,
        tab_hover_text=tab_hover_text,
        button_bg=button_bg,
        button_text=button_text,
        button_hover=button_hover,
        button_pressed=button_pressed,
        button_border=button_border,
        button_border_radius=button_border_radius,
        input_border_color=input_border_color,
        label_quirk_block=label_quirk_block,
    )

    return base_stylesheet


__all__ = ['get_classic_stylesheet']
