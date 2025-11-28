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
            window_bg="#f0f0f0",
            base_bg="#ffffff",
            alt_bg="#f8f8f8",
            text_color="#1a1a1a",
            text_secondary="#555555",
            accent_color="#0078d4",
            accent_hover="#106ebe",
            accent_pressed="#005a9e",
            border_color="#d0d0d0",
            border_hover="#a0a0a0",
            is_dark=False,
        ),
        "palette": {
            "window": "#f0f0f0",
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

