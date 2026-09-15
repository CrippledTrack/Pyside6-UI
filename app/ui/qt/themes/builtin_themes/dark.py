"""Dark theme - calming dark theme with blue accents."""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet


def get_theme() -> Dict[str, Any]:
    """Get Dark theme data."""
    return {
        "name": "Dark",
        "description": "A calming dark theme with blue and teal colors",
        "stylesheet": generate_stylesheet(
            window_bg="#0f1419",
            base_bg="#1a2332",
            alt_bg="#232f3e",
            text_color="#e6f3ff",
            text_secondary="#94a3b8",
            accent_color="#3182ce",
            accent_hover="#4299e1",
            accent_pressed="#2b6cb0",
            border_color="#2d3748",
            border_hover="#4a5568",
            is_dark=True,
        ),
        "palette": {
            "window": "#0f1419",
            "window_text": "#e6f3ff",
            "base": "#1a2332",
            "alternate_base": "#2d3748",
            "tool_tip_base": "#1a2332",
            "tool_tip_text": "#e6f3ff",
            "text": "#e6f3ff",
            "button": "#1a2332",
            "button_text": "#e6f3ff",
            "bright_text": "#3182ce",
            "link": "#3182ce",
            "highlight": "#3182ce",
            "highlighted_text": "#ffffff"
        }
    }

