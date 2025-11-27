"""Purple theme - elegant purple styling."""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet


def get_theme() -> Dict[str, Any]:
    """Get Purple theme data."""
    return {
        "name": "Purple",
        "description": "Purple theme with elegant styling",
        "stylesheet": generate_stylesheet(
            window_bg="#2d1b69",
            base_bg="#3c096c",
            alt_bg="#4a0f7a",
            text_color="#ffffff",
            text_secondary="#d8b4fe",
            accent_color="#c77dff",
            accent_hover="#e0aaff",
            accent_pressed="#9d4edd",
            border_color="#5a189a",
            border_hover="#7c3aab",
            button_text="#2d1b69",
            is_dark=True,
        ),
        "palette": {
            "window": "#2d1b69",
            "window_text": "#ffffff",
            "base": "#3c096c",
            "alternate_base": "#5a189a",
            "tool_tip_base": "#3c096c",
            "tool_tip_text": "#ffffff",
            "text": "#ffffff",
            "button": "#3c096c",
            "button_text": "#ffffff",
            "bright_text": "#c77dff",
            "link": "#c77dff",
            "highlight": "#c77dff",
            "highlighted_text": "#2d1b69"
        }
    }

