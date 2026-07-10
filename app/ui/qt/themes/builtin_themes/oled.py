"""OLED Dark theme - pure black backgrounds with vibrant cyan accents for OLED displays."""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet


def get_theme() -> Dict[str, Any]:
    """Get OLED Dark theme data."""
    return {
        "name": "OLED Dark",
        "description": "OLED-friendly high-contrast dark theme with pure black backgrounds",
        "stylesheet": generate_stylesheet(
            window_bg="#000000",
            base_bg="#000000",
            alt_bg="#121212",
            text_color="#ffffff",
            text_secondary="#94a3b8",
            accent_color="#3182ce",
            accent_hover="#4299e1",
            accent_pressed="#2b6cb0",
            border_color="#222222",
            border_hover="#444444",
            button_text="#e6f3ff",
            is_dark=True,
        ),
        # Classic mode structural overrides to prevent UI from blending into black
        "classic_input_border_color": "#2d3748",
        "classic_tab_selected_bg": "#1a2332",
        "classic_tab_hover_bg": "#232f3e",
        "palette": {
            "window": "#000000",
            "window_text": "#ffffff",
            "base": "#000000",
            "alternate_base": "#121212",
            "tool_tip_base": "#000000",
            "tool_tip_text": "#ffffff",
            "text": "#ffffff",
            "button": "#1a2332",
            "button_text": "#e6f3ff",
            "bright_text": "#3182ce",
            "link": "#3182ce",
            "highlight": "#3182ce",
            "highlighted_text": "#ffffff"
        }
    }
