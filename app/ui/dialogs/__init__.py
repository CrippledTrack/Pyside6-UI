"""Toolkit-neutral host dialog controllers.

These dialogs build content through :mod:`GUI.app.ui.definitions` and do not
import a specific UI toolkit. Qt-only dialogs (for example Theme) remain under
``GUI.app.ui.qt.dialogs``.
"""

from .about_dialog import AboutDialog, create_about_dialog
from .log_viewer_dialog import LogViewerDialog, UIThreadLogHandler
from .plugin_dialog import PluginManagementDialog

__all__ = [
    "AboutDialog",
    "create_about_dialog",
    "LogViewerDialog",
    "UIThreadLogHandler",
    "PluginManagementDialog",
]
