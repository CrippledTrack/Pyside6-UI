"""Red theme - bold red styling."""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet


def get_theme() -> Dict[str, Any]:
    """Get Red theme data."""
    return {
        "name": "Red",
        "description": "Red theme with bold styling",
        "stylesheet": generate_stylesheet(
            window_bg="#660708",
            base_bg="#a4161a",
            alt_bg="#b22025",
            text_color="#ffffff",
            text_secondary="#ffcccb",
            accent_color="#dc2f02",
            accent_hover="#e85d04",
            accent_pressed="#b91c1c",
            border_color="#ba181b",
            border_hover="#d4292d",
            is_dark=True,
        ),
        "palette": {
            "window": "#660708",
            "window_text": "#ffffff",
            "base": "#a4161a",
            "alternate_base": "#ba181b",
            "tool_tip_base": "#a4161a",
            "tool_tip_text": "#ffffff",
            "text": "#ffffff",
            "button": "#a4161a",
            "button_text": "#ffffff",
            "bright_text": "#dc2f02",
            "link": "#dc2f02",
            "highlight": "#dc2f02",
            "highlighted_text": "#ffffff"
        }
    }

