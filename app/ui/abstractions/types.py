"""Toolkit-neutral UI types and specs.

Menu/toolbar contribution types are defined once in ``plugin_system.types``
and re-exported here so shell and plugin APIs share a single shape.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType

from ....plugin_system.types import MenuItemDefinition, ToolbarAction

# Opaque handles returned by shell operations; Qt backend maps to QAction/QMenu/etc.
MenuItemHandle = NewType('MenuItemHandle', str)
ToolbarActionHandle = NewType('ToolbarActionHandle', str)
StatusWidgetHandle = NewType('StatusWidgetHandle', str)

# Canonical aliases used by IMainWindowShell
MenuItemSpec = MenuItemDefinition
ToolbarActionSpec = ToolbarAction


class ToastType(str, Enum):
    """Toast notification severity."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


__all__ = [
    'MenuItemHandle',
    'ToolbarActionHandle',
    'StatusWidgetHandle',
    'ToastType',
    'MenuItemSpec',
    'ToolbarActionSpec',
]
