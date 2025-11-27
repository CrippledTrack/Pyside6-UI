"""Light theme - clean light theme with blue accents."""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet


def get_theme() -> Dict[str, Any]:
    """Get Light theme data."""
    return {
        "name": "Light",
        "description": "Light theme with blue accents",
        "stylesheet": generate_stylesheet(
            window_bg="#f5f5f5",
            base_bg="#ffffff",
            alt_bg="#fafafa",
            text_color="#1a1a1a",
            text_secondary="#666666",
            accent_color="#0078d4",
            accent_hover="#106ebe",
            accent_pressed="#005a9e",
            border_color="#e0e0e0",
            border_hover="#b0b0b0",
            is_dark=False,
        ),
        "palette": {
            "window": "#f5f5f5",
            "window_text": "#1a1a1a",
            "base": "#ffffff",
            "alternate_base": "#fafafa",
            "tool_tip_base": "#ffffff",
            "tool_tip_text": "#1a1a1a",
            "text": "#1a1a1a",
            "button": "#f5f5f5",
            "button_text": "#1a1a1a",
            "bright_text": "#ff0000",
            "link": "#0078d4",
            "highlight": "#0078d4",
            "highlighted_text": "#ffffff"
        }
    }

