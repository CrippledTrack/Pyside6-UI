"""Minimal theme - clean and simple design."""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet


def get_theme() -> Dict[str, Any]:
    """Get Minimal theme data."""
    return {
        "name": "Minimal",
        "description": "Minimal theme with clean design",
        "stylesheet": generate_stylesheet(
            window_bg="#ffffff",
            base_bg="#fafafa",
            alt_bg="#f5f5f5",
            text_color="#333333",
            text_secondary="#888888",
            accent_color="#007bff",
            accent_hover="#0056b3",
            accent_pressed="#004494",
            border_color="#e0e0e0",
            border_hover="#c0c0c0",
            button_bg="#f8f9fa",
            button_text="#333333",
            button_hover="#e9ecef",
            button_pressed="#dee2e6",
            is_dark=False,
        ) + """
            /* Minimal-specific clean styling - bordered buttons, borderless groups */
            QPushButton {
                border: 1px solid #dee2e6;
            }
            QPushButton:hover {
                border-color: #adb5bd;
            }
            QGroupBox {
                border-width: 0px;
                background-color: transparent;
            }
            QGroupBox::title {
                background-color: transparent;
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

