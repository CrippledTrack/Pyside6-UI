"""Blue theme - modern dark blue with pink accents."""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet


def get_theme() -> Dict[str, Any]:
    """Get Blue theme data."""
    return {
        "name": "Blue",
        "description": "Blue theme with modern styling",
        "stylesheet": generate_stylesheet(
            window_bg="#1a1a2e",
            base_bg="#16213e",
            alt_bg="#1f2b47",
            text_color="#ffffff",
            text_secondary="#94a3b8",
            accent_color="#e94560",
            accent_hover="#f06292",
            accent_pressed="#c2185b",
            border_color="#0f3460",
            border_hover="#1e4976",
            is_dark=True,
        ),
        "palette": {
            "window": "#1a1a2e",
            "window_text": "#ffffff",
            "base": "#16213e",
            "alternate_base": "#0f3460",
            "tool_tip_base": "#16213e",
            "tool_tip_text": "#ffffff",
            "text": "#ffffff",
            "button": "#16213e",
            "button_text": "#ffffff",
            "bright_text": "#e94560",
            "link": "#e94560",
            "highlight": "#e94560",
            "highlighted_text": "#ffffff"
        }
    }

