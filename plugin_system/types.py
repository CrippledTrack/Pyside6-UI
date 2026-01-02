"""
Data types for plugin extensions.

This module provides dataclasses for structured data used by plugin interfaces,
such as menu item definitions and toolbar actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class MenuItemDefinition:
    """Definition for a menu item contributed by a plugin.
    
    Attributes:
        menu: The menu to add this item to ("File", "Edit", "Tools", "Help", etc.)
        label: The display text for the menu item
        callback: Function to call when the menu item is clicked
        shortcut: Optional keyboard shortcut (e.g., "Ctrl+Shift+P")
        icon: Optional path to an icon file
        separator_before: If True, add a separator before this item
        separator_after: If True, add a separator after this item
        enabled: Whether the menu item is enabled by default
    """
    menu: str
    label: str
    callback: Callable[[], None]
    shortcut: Optional[str] = None
    icon: Optional[str] = None
    separator_before: bool = False
    separator_after: bool = False
    enabled: bool = True


@dataclass
class ToolbarAction:
    """Definition for a toolbar action contributed by a plugin.
    
    Attributes:
        label: The display text (used for accessibility/tooltips)
        callback: Function to call when the action is triggered
        icon: Optional path to an icon file (recommended for toolbar items)
        tooltip: Optional tooltip text
        checkable: If True, the action can be toggled on/off
        checked: Initial checked state (only used if checkable is True)
    """
    label: str
    callback: Callable[[], None]
    icon: Optional[str] = None
    tooltip: Optional[str] = None
    checkable: bool = False
    checked: bool = False


@dataclass
class PluginEvent:
    """Represents an event that can be published/subscribed.
    
    Attributes:
        name: Unique event name (e.g., "user_created", "scan_completed")
        data: Arbitrary data associated with the event
        source: Name of the plugin that published the event
    """
    name: str
    data: dict = field(default_factory=dict)
    source: Optional[str] = None


__all__ = [
    'MenuItemDefinition',
    'ToolbarAction',
    'PluginEvent',
]
