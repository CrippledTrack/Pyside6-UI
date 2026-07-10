"""Cyberpunk theme - neon colors with sharp edges."""

from __future__ import annotations

from typing import Dict, Any

from ._base import generate_stylesheet, BORDER_RADIUS_SHARP


def get_theme() -> Dict[str, Any]:
    """Get Cyberpunk theme data."""
    return {
        "name": "Cyberpunk",
        "description": "Cyberpunk theme with neon colors",
        "stylesheet": generate_stylesheet(
            window_bg="#0a0a0a",
            base_bg="#1a1a1a",
            alt_bg="#222222",
            text_color="#00ff41",
            text_secondary="#00cc33",
            accent_color="#ff006e",
            accent_hover="#ff1a7a",
            accent_pressed="#cc0057",
            border_color="#00ff41",
            border_hover="#00cc33",
            button_text="#ffffff",
            is_dark=True,
            border_radius=BORDER_RADIUS_SHARP,  # Sharp edges for cyberpunk aesthetic
            border_width="2px",                 # 2px borders everywhere via structural token
            # Inverted tab colours: green-on-black selected, dark text on hover
            tab_selected_bg="#00ff41",
            tab_selected_text="#0a0a0a",
            tab_hover_bg="#00cc33",
            tab_hover_text="#0a0a0a",
            scrollbar_handle_radius="0px",      # Sharp square scrollbar handles
        ),
        # Classic mode structural tokens (v5.1.0)
        "classic_border_width": "2px",
        "classic_border_radius": "0px",
        "classic_tab_selected_bg": "#00ff41",    # Inverted: green bg on selected tab
        "classic_tab_selected_text": "#0a0a0a",  # Inverted: dark text on green tab
        "classic_tab_hover_bg": "#00cc33",        # Inverted: darker green on hover
        "classic_tab_hover_text": "#0a0a0a",      # Dark text on hover
        "classic_scrollbar_handle_radius": "0px", # Square handles
        "classic_input_border_color": "#00ff41",  # Neon green input border
        "classic_button_border": "2px solid #ff006e",  # Pink neon button border
        "classic_button_border_radius": "0px",    # Sharp button corners
        "palette": {
            "window": "#0a0a0a",
            "window_text": "#00ff41",
            "base": "#1a1a1a",
            "alternate_base": "#2a2a2a",
            "tool_tip_base": "#1a1a1a",
            "tool_tip_text": "#00ff41",
            "text": "#00ff41",
            "button": "#1a1a1a",
            "button_text": "#00ff41",
            "bright_text": "#ff006e",
            "link": "#ff006e",
            "highlight": "#ff006e",
            "highlighted_text": "#ffffff"
        }
    }
