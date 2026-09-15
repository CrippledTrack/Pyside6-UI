"""Toolkit-neutral UI abstractions."""

from .types import (
    MenuItemSpec,
    ToolbarActionSpec,
    MenuItemHandle,
    ToolbarActionHandle,
    StatusWidgetHandle,
    ToastType,
)
from .event_loop import IUIEventLoop
from .application import IUIApplication
from .shell import IMainWindowShell
from .presenters import IDialogPresenter
from .plugin_host import IPluginTabHost

__all__ = [
    'MenuItemSpec',
    'ToolbarActionSpec',
    'MenuItemHandle',
    'ToolbarActionHandle',
    'StatusWidgetHandle',
    'ToastType',
    'IUIEventLoop',
    'IUIApplication',
    'IMainWindowShell',
    'IDialogPresenter',
    'IPluginTabHost',
]
