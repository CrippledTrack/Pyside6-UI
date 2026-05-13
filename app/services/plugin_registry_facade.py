"""
Facade for GUI access to the plugin registry.

This keeps UI controllers insulated from registry internals.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from ...plugin_system.registry import PluginRegistry


class PluginRegistryFacade:
    """GUI-facing facade over the injected plugin registry."""

    def __init__(self, container: Any, registry: Optional["PluginRegistry"] = None) -> None:
        if registry is None:
            from ...plugin_system.registry import PluginRegistry as _PR
            registry = _PR()
        self._registry = registry
        self._registry.set_container(container)

    def publish_event(self, event_name: str, event_data: Dict[str, Any] | None = None) -> None:
        """Publish a plugin event to subscribers."""
        self._registry.publish_event(event_name, event_data)

    def get_plugin_instance(self, name: str) -> Any:
        """Get or create a plugin instance by name."""
        return self._registry.get_plugin_instance(name)

    def has_plugin_instance(self, name: str) -> bool:
        """Check if a plugin instance is cached."""
        return self._registry.has_plugin_instance(name)

    def get_menu_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get MenuExtension plugin classes."""
        return self._registry.get_menu_extensions(enabled_only=enabled_only)

    def get_status_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get StatusExtension plugin classes."""
        return self._registry.get_status_extensions(enabled_only=enabled_only)

    def get_toolbar_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get ToolbarExtension plugin classes."""
        return self._registry.get_toolbar_extensions(enabled_only=enabled_only)

    def get_service_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get ServiceExtension plugin classes."""
        return self._registry.get_service_extensions(enabled_only=enabled_only)


__all__ = ["PluginRegistryFacade"]
