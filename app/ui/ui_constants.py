"""
UI spacing and layout constants for consistent styling.

This module provides standard values for margins, padding, spacing, and
border radius to maintain visual consistency across the application.
"""

from __future__ import annotations

from typing import NamedTuple


class Spacing(NamedTuple):
    """Standard spacing values for consistent UI layout.
    
    Use these values for margins, padding, and gaps between elements
    to maintain visual consistency across the application.
    
    Example usage:
        layout.setSpacing(Spacing.MEDIUM)
        layout.setContentsMargins(Spacing.LARGE, Spacing.MEDIUM, Spacing.LARGE, Spacing.MEDIUM)
    """
    # Extra small spacing - for tight layouts, icon gaps
    XS: int = 4
    # Small spacing - between related items
    SMALL: int = 8
    # Medium spacing - standard gap between elements
    MEDIUM: int = 12
    # Large spacing - between sections or groups
    LARGE: int = 16
    # Extra large spacing - for major section separation
    XL: int = 24
    # Extra extra large - for page-level margins
    XXL: int = 32


# Create a singleton instance for easy access
SPACING = Spacing(
    XS=4,
    SMALL=8,
    MEDIUM=12,
    LARGE=16,
    XL=24,
    XXL=32,
)


class Margins(NamedTuple):
    """Standard margin presets for common layout patterns.
    
    Each preset returns a tuple of (left, top, right, bottom) values
    suitable for use with setContentsMargins().
    
    Example usage:
        layout.setContentsMargins(*Margins.CARD)
    """
    # No margins
    NONE: tuple = (0, 0, 0, 0)
    # Tight margins for compact elements
    TIGHT: tuple = (4, 4, 4, 4)
    # Small margins for list items, buttons
    SMALL: tuple = (8, 8, 8, 8)
    # Standard margins for most containers
    STANDARD: tuple = (12, 12, 12, 12)
    # Card container margins
    CARD: tuple = (16, 16, 16, 16)
    # Large margins for dialogs, main content areas
    LARGE: tuple = (20, 20, 20, 20)
    # Page-level margins for main window content
    PAGE: tuple = (24, 24, 24, 24)


# Create a singleton instance
MARGINS = Margins(
    NONE=(0, 0, 0, 0),
    TIGHT=(4, 4, 4, 4),
    SMALL=(8, 8, 8, 8),
    STANDARD=(12, 12, 12, 12),
    CARD=(16, 16, 16, 16),
    LARGE=(20, 20, 20, 20),
    PAGE=(24, 24, 24, 24),
)


class BorderRadius(NamedTuple):
    """Standard border radius values for rounded corners.
    
    Example usage:
        widget.setStyleSheet(f"border-radius: {BorderRadius.MEDIUM}px;")
    """
    # No rounding (sharp corners)
    NONE: int = 0
    # Subtle rounding
    SMALL: int = 4
    # Standard rounding for most elements
    MEDIUM: int = 6
    # Larger rounding for cards, dialogs
    LARGE: int = 8
    # Maximum rounding for pills, circles
    FULL: int = 9999


BORDER_RADIUS = BorderRadius(
    NONE=0,
    SMALL=4,
    MEDIUM=6,
    LARGE=8,
    FULL=9999,
)


# Common layout configurations as dictionaries for convenience
LAYOUT_COMPACT = {
    "margins": MARGINS.TIGHT,
    "spacing": SPACING.SMALL,
}

LAYOUT_STANDARD = {
    "margins": MARGINS.STANDARD,
    "spacing": SPACING.MEDIUM,
}

LAYOUT_RELAXED = {
    "margins": MARGINS.LARGE,
    "spacing": SPACING.LARGE,
}


__all__ = [
    'Spacing',
    'SPACING',
    'Margins',
    'MARGINS',
    'BorderRadius',
    'BORDER_RADIUS',
    'LAYOUT_COMPACT',
    'LAYOUT_STANDARD',
    'LAYOUT_RELAXED',
]

