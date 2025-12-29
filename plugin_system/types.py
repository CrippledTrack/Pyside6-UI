"""
Type definitions for plugin extensions (stubs).

These are placeholder types that allow plugins designed for future
versions (v3.4.0+) to be loaded by the current version.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Dict, List


@dataclass
class MenuItemDefinition:
    """Definition for a menu item contributed by a plugin (stub)."""
    menu: str  # Name of menu to add to (e.g., "Tools", "Help")
    label: str  # Label text for the menu item
    callback: Callable[[], None] = field(default=lambda: None)  # Function to call
    shortcut: Optional[str] = None  # Keyboard shortcut (e.g., "Ctrl+Shift+E")
    enabled: bool = True  # Whether the item is enabled
    separator_before: bool = False  # Add separator before this item
    separator_after: bool = False  # Add separator after this item


@dataclass
class ToolbarAction:
    """Definition for a toolbar action contributed by a plugin (stub)."""
    label: str  # Button label/text
    callback: Callable[[], None] = field(default=lambda: None)  # Function to call
    tooltip: Optional[str] = None  # Tooltip text
    icon: Optional[str] = None  # Icon path or name
    checkable: bool = False  # Whether the action is checkable/toggleable
    checked: bool = False  # Initial checked state (if checkable)


@dataclass
class PluginEvent:
    """Represents an event in the plugin event bus (stub)."""
    name: str  # Event name (e.g., "plugin_enabled", "theme_changed")
    data: Dict[str, Any] = field(default_factory=dict)  # Event payload


__all__ = [
    'MenuItemDefinition',
    'ToolbarAction',
    'PluginEvent',
]
