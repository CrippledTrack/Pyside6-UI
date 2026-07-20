"""
Minimal plugin example - contains only what's necessary to register as a plugin.

Uses the toolkit-neutral ``create_tab_content`` entry point.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ..app.ui.qt.bindings import QWidget
from ..plugin_system.base import BaseTabPlugin
from ..plugin_system.types import TabContent, TabCreateContext

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
    plugin_version = "1.1.0"
    plugin_author = "Plugin Creator"
    min_gui_version = "6.0.0"
    required_gui_version = ">=6.0.0"
    disabled_by_default = True
    ui_backends = ["qt"]

    def __init__(self, container: "ServiceContainer") -> None:
        """Initialize the plugin instance."""
        super().__init__(container)

    # =========================================================================
    # TabExtension Interface
    # =========================================================================

    def create_tab_content(self, context: TabCreateContext) -> TabContent:
        """Create tab content for the active UI backend."""
        if context.backend_id != "qt":
            raise NotImplementedError(
                f"Minimal Plugin does not support UI backend '{context.backend_id}'"
            )
        return MinimalWidget(context.parent)


class MinimalWidget(QWidget):
    """Minimal widget that is completely blank."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)


__all__ = ["MinimalTabPlugin"]
