"""Green theme - nature-inspired colors."""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet


def get_theme() -> Dict[str, Any]:
    """Get Green theme data."""
    return {
        "name": "Green",
        "description": "Green theme with nature-inspired colors",
        "stylesheet": generate_stylesheet(
            window_bg="#1b4332",
            base_bg="#2d6a4f",
            alt_bg="#357a5c",
            text_color="#ffffff",
            text_secondary="#b7e4c7",
            accent_color="#95d5b2",
            accent_hover="#b7e4c7",
            accent_pressed="#74c69d",
            border_color="#40916c",
            border_hover="#52a37e",
            button_text="#1b4332",
            is_dark=True,
        ),
        "palette": {
            "window": "#1b4332",
            "window_text": "#ffffff",
            "base": "#2d6a4f",
            "alternate_base": "#40916c",
            "tool_tip_base": "#2d6a4f",
            "tool_tip_text": "#ffffff",
            "text": "#ffffff",
            "button": "#2d6a4f",
            "button_text": "#ffffff",
            "bright_text": "#95d5b2",
            "link": "#95d5b2",
            "highlight": "#95d5b2",
            "highlighted_text": "#1b4332"
        }
    }

