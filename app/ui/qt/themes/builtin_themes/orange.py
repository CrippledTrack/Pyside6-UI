"""Orange theme - warm colors."""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet


def get_theme() -> Dict[str, Any]:
    """Get Orange theme data."""
    return {
        "name": "Orange",
        "description": "Orange theme with warm colors",
        "stylesheet": generate_stylesheet(
            window_bg="#783937",
            base_bg="#9c6644",
            alt_bg="#a67552",
            text_color="#ffffff",
            text_secondary="#e6ccb2",
            accent_color="#ddb892",
            accent_hover="#e6ccb2",
            accent_pressed="#c4a484",
            border_color="#b08968",
            border_hover="#c49a79",
            button_text="#783937",
            is_dark=True,
        ),
        "palette": {
            "window": "#783937",
            "window_text": "#ffffff",
            "base": "#9c6644",
            "alternate_base": "#b08968",
            "tool_tip_base": "#9c6644",
            "tool_tip_text": "#ffffff",
            "text": "#ffffff",
            "button": "#9c6644",
            "button_text": "#ffffff",
            "bright_text": "#ddb892",
            "link": "#ddb892",
            "highlight": "#ddb892",
            "highlighted_text": "#783937"
        }
    }

