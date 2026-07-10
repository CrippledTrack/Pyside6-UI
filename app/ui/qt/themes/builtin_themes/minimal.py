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
            window_bg="#f5f5f5",
            base_bg="#ffffff",
            alt_bg="#fafafa",
            text_color="#333333",
            text_secondary="#666666",
            accent_color="#007bff",
            accent_hover="#0056b3",
            accent_pressed="#004494",
            border_color="#d6d6d6",
            border_hover="#b0b0b0",
            button_bg="#ffffff",
            button_text="#333333",
            button_hover="#f8f9fa",
            button_pressed="#dee2e6",
            is_dark=False,
        ) + """
            /* Minimal-specific clean styling - bordered buttons, borderless groups */
            QPushButton {
                border: 1px solid #d6d6d6;
                border-radius: 4px;
                padding: 4px 8px; /* Reduced padding for tighter minimal look */
                min-height: 20px; /* Ensure minimum height */
            }
            QPushButton:hover {
                border-color: #adb5bd;
                background-color: #f0f0f0;
            }
            QGroupBox {
                border: 1px solid #e0e0e0; /* Add subtle border for structure */
                border-radius: 6px;
                margin-top: 24px;
                padding-top: 24px;
                padding-bottom: 12px;
                padding-left: 12px;
                padding-right: 12px;
                background-color: #ffffff; /* White background card effect */
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 4px;
                background-color: transparent;
                color: #333333;
                font-weight: bold;
            }
        """,
        # Classic mode structural tokens (v5.1.0)
        "classic_border_radius": "2px",
        "classic_scrollbar_size": "8px",
        "classic_scrollbar_handle_radius": "4px",
        # Classic button overrides — light gray minimal-style buttons
        "classic_button_bg": "#f8f9fa",
        "classic_button_text": "#333333",
        "classic_button_hover": "#e9ecef",
        "classic_button_pressed": "#dee2e6",
        "classic_button_border": "1px solid #dee2e6",
        "classic_button_border_radius": "2px",
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

