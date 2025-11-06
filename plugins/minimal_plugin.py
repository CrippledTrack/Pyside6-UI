"""
Minimal plugin example - contains only what's necessary to register as a plugin.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtWidgets import QWidget, QLabel
from GUI.plugins.base import BaseTabPlugin


class MinimalPlugin(BaseTabPlugin):
    """Minimal plugin with only required components."""
    
    tab_name = "Minimal Plugin"
    tab_description = "A minimal plugin with only required components"
    supported_platforms = ["Windows", "Linux"]
    plugin_version = "1.0.1"
    plugin_author = "Plugin Creator"
    min_gui_version = "3.0.0"
    disabled_by_default = True

    @classmethod
    def create_widget(cls, parent: Optional[QWidget] = None) -> QWidget:
        """Create the widget for this tab."""
        return MinimalWidget(parent)


class MinimalWidget(QWidget):
    """Minimal widget that is completely blank."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
