"""
Minimal plugin example - contains only what's necessary to register as a plugin.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING
from ..app.qt_bindings import QWidget
from ..plugin_system.base import BaseTabPlugin

if TYPE_CHECKING:
    from ..app.services.container import ServiceContainer


class MinimalTabPlugin(BaseTabPlugin):
    """Minimal plugin with only required components."""
    
    # =========================================================================
    # Plugin Metadata
    # =========================================================================
    plugin_name = "Minimal Plugin"
    tab_title = "Minimal Plugin"
    plugin_description = "A minimal plugin with only required components"
    supported_platforms = ["Windows", "Linux", "macOS"]
    requires_admin = False
    plugin_version = "1.0.1"
    plugin_author = "Plugin Creator"
    min_gui_version = "4.0.0"
    required_gui_version = ">=4.0.0"
    disabled_by_default = True

    def __init__(self, container: "ServiceContainer") -> None:
        """Initialize the plugin instance."""
        super().__init__(container)

    # =========================================================================
    # TabExtension Interface
    # =========================================================================

    def create_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        """Create the widget for this tab."""
        return MinimalWidget(parent)


class MinimalWidget(QWidget):
    """Minimal widget that is completely blank."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)


__all__ = ["MinimalTabPlugin"]
