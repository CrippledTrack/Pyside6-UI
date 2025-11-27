"""Purple Dark theme - dark theme with purple accents."""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet


def get_theme() -> Dict[str, Any]:
    """Get Purple Dark theme data."""
    return {
        "name": "Purple Dark",
        "description": "Dark theme with purple accents",
        "stylesheet": generate_stylesheet(
            window_bg="#1e1e1e",
            base_bg="#2d2d2d",
            alt_bg="#353535",
            text_color="#ffffff",
            text_secondary="#a0a0a0",
            accent_color="#6c3483",
            accent_hover="#884ea0",
            accent_pressed="#512e5f",
            border_color="#3c3c3c",
            border_hover="#4c4c4c",
            is_dark=True,
        ),
        "palette": {
            "window": "#1e1e1e",
            "window_text": "#ffffff",
            "base": "#2d2d2d",
            "alternate_base": "#353535",
            "tool_tip_base": "#2d2d2d",
            "tool_tip_text": "#ffffff",
            "text": "#ffffff",
            "button": "#2d2d2d",
            "button_text": "#ffffff",
            "bright_text": "#c77dff",
            "link": "#c77dff",
            "highlight": "#6c3483",
            "highlighted_text": "#ffffff"
        }
    }

