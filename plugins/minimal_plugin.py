"""
Minimal plugin example - contains only what's necessary to register as a plugin.

Uses the toolkit-neutral ``create_tab_content`` entry point and
``GUI.app.ui.definitions`` for content (no direct toolkit imports).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..app.ui.definitions import create_column
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
    plugin_version = "1.2.0"
    plugin_author = "Plugin Creator"
    min_gui_version = "6.0.0"
    required_gui_version = ">=6.0.0"
    disabled_by_default = True

    def __init__(self, container: "ServiceContainer") -> None:
        """Initialize the plugin instance."""
        super().__init__(container)

    # =========================================================================
    # TabExtension Interface
    # =========================================================================

    def create_tab_content(self, context: TabCreateContext) -> TabContent:
        """Create blank tab content via shared UI definitions."""
        return create_column(parent=context.parent, expand=True)


__all__ = ["MinimalTabPlugin"]
