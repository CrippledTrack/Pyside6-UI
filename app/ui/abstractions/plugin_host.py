"""Plugin tab hosting abstraction.

``IPluginTabHost`` is a structural subset of ``IMainWindowShell`` for callers
that only need tab add/remove/clear. The shell is the primary host contract;
``clear_tabs_for_plugins`` is defined on both so tab-focused code can depend
on this narrower protocol.
"""

from __future__ import annotations

from typing import List, Protocol, Type


class IPluginTabHost(Protocol):
    """Protocol for UI shell tab hosting operations (subset of IMainWindowShell)."""

    def has_plugin_tab(self, plugin_name: str) -> bool:
        """Check if a plugin tab is currently loaded."""
        ...

    def add_plugin_tab(self, plugin_name: str, plugin_class: Type) -> None:
        """Add a tab for a plugin."""
        ...

    def remove_plugin_tab(self, plugin_name: str) -> None:
        """Remove a tab for a plugin."""
        ...

    def clear_tabs_for_plugins(self, plugin_names: List[str]) -> None:
        """Remove tabs and clear stale references for unloaded plugins."""
        ...


__all__ = ['IPluginTabHost']
