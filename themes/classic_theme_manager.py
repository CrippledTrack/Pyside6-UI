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
        theme_data: Theme dictionary with 'palette' and optional 'legacy_stylesheet'
        
    Returns:
        Complete classic stylesheet string
    """
    palette = theme_data.get('palette', {})
    
    if not palette:
        return ""
    
    # Generate base stylesheet from palette
    highlight = palette.get('highlight', '#0078d4')
    
    base_stylesheet = _CLASSIC_TEMPLATE.format(
        window=palette.get('window', '#1e1e1e'),
        base=palette.get('base', '#2d2d2d'),
        border=palette.get('alternate_base', '#3c3c3c'),
        text=palette.get('text', '#ffffff'),
        highlight=highlight,
        highlight_text=palette.get('highlighted_text', '#ffffff'),
        highlight_hover=_adjust_color(highlight, 0.15),
        highlight_pressed=_adjust_color(highlight, -0.15),
    )
    
    # Append any theme-specific classic overrides
    overrides = theme_data.get('legacy_stylesheet', '')
    
    return base_stylesheet + overrides


__all__ = ['get_classic_stylesheet']
