"""Controllers for managing UI components."""

from .tab_controller import TabController
from .plugin_controller import PluginController
from .menu_bar_controller import MenuBarController
from .window_title_manager import WindowTitleManager
from .status_bar_manager import StatusBarManager
from .shortcut_manager import ShortcutManager
from .toast_manager import ToastManager

__all__ = [
    'TabController',
    'PluginController',
    'MenuBarController',
    'WindowTitleManager',
    'StatusBarManager',
    'ShortcutManager',
    'ToastManager',
]

