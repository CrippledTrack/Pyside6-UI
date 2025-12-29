"""
Extension interface stubs for plugin detection.

These are placeholder interfaces that allow plugins designed for future
versions (v3.4.0+) to be loaded and detected by the current version.
The actual extension functionality is not implemented in this version.

Plugins implementing these interfaces will be loaded as normal TabExtension
plugins, but their Menu, Status, Toolbar, Service, and EventSubscriber
features will not be active.
"""
from __future__ import annotations

from abc import ABC
from typing import Any, Dict, List, Optional, Callable


class Plugin(ABC):
    """Base interface for all plugins (stub for future versions)."""
    pass


class TabExtension(ABC):
    """Interface for plugins that provide a tab widget (stub)."""
    pass


class MenuExtension(ABC):
    """Interface for plugins that contribute menu items (stub - not functional)."""
    
    @classmethod
    def get_menu_items(cls) -> List[Any]:
        """Return menu items. Not functional in this version."""
        return []


class StatusExtension(ABC):
    """Interface for plugins that provide status bar widgets (stub - not functional)."""
    
    @classmethod
    def create_status_widget(cls, parent: Optional[Any] = None) -> Optional[Any]:
        """Create status widget. Not functional in this version."""
        return None


class ToolbarExtension(ABC):
    """Interface for plugins that contribute toolbar actions (stub - not functional)."""
    
    @classmethod
    def get_toolbar_actions(cls) -> List[Any]:
        """Return toolbar actions. Not functional in this version."""
        return []


class ServiceExtension(ABC):
    """Interface for plugins that provide background services (stub - not functional)."""
    
    @classmethod
    def on_application_start(cls, container: Any) -> None:
        """Called on application start. Not functional in this version."""
        pass
    
    @classmethod
    def on_application_shutdown(cls) -> None:
        """Called on application shutdown. Not functional in this version."""
        pass


class EventSubscriberExtension(ABC):
    """Interface for plugins that subscribe to events (stub - not functional)."""
    
    @classmethod
    def get_event_subscriptions(cls) -> Dict[str, Callable]:
        """Return event subscriptions. Not functional in this version."""
        return {}


class SettingsExtension(ABC):
    """Interface for plugins that provide settings (stub - not functional)."""
    
    @classmethod
    def get_settings_widget(cls, parent: Optional[Any] = None) -> Optional[Any]:
        """Get settings widget. Not functional in this version."""
        return None
    
    @classmethod
    def on_settings_changed(cls, settings_dict: Dict[str, Any]) -> None:
        """Called when settings change. Not functional in this version."""
        pass


__all__ = [
    'Plugin',
    'TabExtension',
    'MenuExtension',
    'StatusExtension',
    'ToolbarExtension',
    'ServiceExtension',
    'EventSubscriberExtension',
    'SettingsExtension',
]
