"""Plugin tab hosting abstraction."""

from __future__ import annotations

from typing import List, Protocol, Type


class IPluginTabHost(Protocol):
    """Protocol for UI shell tab hosting operations."""

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
