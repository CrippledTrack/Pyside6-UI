"""Toolkit-neutral UI types and specs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, NewType

# Opaque handles returned by shell operations; Qt backend maps to QAction/QMenu/etc.
MenuItemHandle = NewType('MenuItemHandle', str)
ToolbarActionHandle = NewType('ToolbarActionHandle', str)
StatusWidgetHandle = NewType('StatusWidgetHandle', str)


class ToastType(str, Enum):
    """Toast notification severity."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class MenuItemSpec:
    """Specification for a menu item."""
    menu_title: str
    label: str
    callback: Callable[[], None]
    shortcut: Optional[str] = None
    icon: Optional[str] = None
    enabled: bool = True
    separator_before: bool = False
    separator_after: bool = False


@dataclass(frozen=True)
class ToolbarActionSpec:
    """Specification for a toolbar action."""
    label: str
    callback: Callable[[], None]
    icon: Optional[str] = None
    tooltip: Optional[str] = None
    checkable: bool = False
    checked: bool = False


@dataclass
class MenuItemRegistration:
    """Result of registering a menu item."""
    handle: MenuItemHandle
    menu_title: str
    created_menu: bool = False


__all__ = [
    'MenuItemHandle',
    'ToolbarActionHandle',
    'StatusWidgetHandle',
    'ToastType',
    'MenuItemSpec',
    'ToolbarActionSpec',
    'MenuItemRegistration',
]
