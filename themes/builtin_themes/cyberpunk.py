"""Cyberpunk theme - neon colors with sharp edges."""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet, BORDER_RADIUS_SHARP


def get_theme() -> Dict[str, Any]:
    """Get Cyberpunk theme data."""
    return {
        "name": "Cyberpunk",
        "description": "Cyberpunk theme with neon colors",
        "stylesheet": generate_stylesheet(
            window_bg="#0a0a0a",
            base_bg="#1a1a1a",
            alt_bg="#222222",
            text_color="#00ff41",
            text_secondary="#00cc33",
            accent_color="#ff006e",
            accent_hover="#ff1a7a",
            accent_pressed="#cc0057",
            border_color="#00ff41",
            border_hover="#00cc33",
            button_text="#ffffff",
            is_dark=True,
            border_radius=BORDER_RADIUS_SHARP,  # Sharp edges for cyberpunk aesthetic
        ) + """
            /* Cyberpunk-specific overrides for sharp edges and neon glow */
            QTabWidget::pane {
                border-width: 2px;
            }
            QTabBar::tab {
                border-width: 2px;
            }
            QTabBar::tab:selected {
                background-color: #00ff41;
                color: #0a0a0a;
            }
            QTabBar::tab:hover:!selected {
                background-color: #00cc33;
                color: #0a0a0a;
            }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
                border-width: 2px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border-color: #ff006e;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                border-radius: 0px;
            }
        """,
        "legacy_stylesheet": _CLASSIC_STYLESHEET,
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


# =============================================================================
# Classic Stylesheet Overrides
# =============================================================================

_CLASSIC_STYLESHEET = """
/* Cyberpunk overrides - sharp corners, 2px borders, inverted selected tab */
QTabWidget::pane {
    border: 2px solid #00ff41;
    border-radius: 0px;
}
QTabBar::tab {
    border: 2px solid #00ff41;
    border-top-left-radius: 0px;
    border-top-right-radius: 0px;
}
QTabBar::tab:selected {
    background-color: #00ff41;
    color: #0a0a0a;
}
QTabBar::tab:hover {
    background-color: #00cc33;
    color: #0a0a0a;
}
QPushButton {
    border: 2px solid #ff006e;
    border-radius: 0px;
}
QLineEdit, QTextEdit, QComboBox {
    border: 2px solid #00ff41;
    border-radius: 0px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    border-radius: 0px;
}
"""
