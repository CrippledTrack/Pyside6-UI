"""Toolkit-neutral plugin extension host.

Integrates Menu / Status / Toolbar / Service extensions into an
``IMainWindowShell``. Qt and TUI backends share this orchestration;
toolkit-specific chrome lives in each shell implementation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set

from ...plugin_system.identity import plugin_ui_label
from ..services.interfaces import ISettingsService
from ..services.plugin_service import PluginService
from .abstractions.shell import IMainWindowShell
from .abstractions.types import (
    MenuItemHandle,
    StatusWidgetHandle,
    ToolbarActionHandle,
)

if TYPE_CHECKING:
    from ..services.container import ServiceContainer

logger = logging.getLogger(__name__)


class PluginExtensionHost:
    """Integrate and tear down plugin extensions against a main-window shell."""

    def __init__(self, container: "ServiceContainer") -> None:
        self.container = container
        self.settings_service = container.get(ISettingsService)
        self.plugin_service = container.get(PluginService)

        self._main_window: Optional[IMainWindowShell] = None
        self._plugin_menu_actions: Dict[str, List[MenuItemHandle]] = {}
        self._plugin_toolbar_actions: Dict[str, List[ToolbarActionHandle]] = {}
        self._plugin_status_widgets: Dict[str, List[StatusWidgetHandle]] = {}
        self._plugin_created_menus: Dict[str, List[str]] = {}
        self._started_services: Set[str] = set()

        self._integration_handlers: Dict[str, Callable[[str, type], None]] = {
            "Menu": self._integrate_menu_extension,
            "Status": self._integrate_status_extension,
            "Toolbar": self._integrate_toolbar_extension,
            "Service": self._integrate_service_extension,
        }

    @property
    def main_window(self) -> Optional[IMainWindowShell]:
        return self._main_window

    def set_main_window(self, main_window: Optional[IMainWindowShell]) -> None:
        self._main_window = main_window

    def _label(self, plugin_id: str, plugin_class: Optional[type] = None) -> str:
        if plugin_class is not None:
            return plugin_ui_label(plugin_class)
        return self.plugin_service.plugin_label(plugin_id)

    def is_extension_enabled(self, plugin_name: str, extension_type: str) -> bool:
        """Check if a specific extension type is enabled for a plugin."""
        if not self.settings_service:
            return True
        return self.settings_service.is_extension_enabled(plugin_name, extension_type)

    def has_started_service(self, plugin_name: str) -> bool:
        """Return True if this plugin's service start hook has been run."""
        return plugin_name in self._started_services

    def integrate_extensions(self, main_window: IMainWindowShell) -> None:
        """Integrate Menu/Status/Toolbar extensions and start services."""
        self._main_window = main_window
        self.cleanup_all_extensions()

        try:
            registry_queries = {
                "Menu": self.plugin_service.get_menu_extensions,
                "Status": self.plugin_service.get_status_extensions,
                "Toolbar": self.plugin_service.get_toolbar_extensions,
            }

            for ext_name, query_func in registry_queries.items():
                plugins = query_func(enabled_only=True)
                for name, plugin_class in plugins.items():
                    try:
                        if self.is_extension_enabled(name, ext_name):
                            handler = self._integration_handlers.get(ext_name)
                            if handler:
                                handler(name, plugin_class)
                        else:
                            logger.debug("%s extension disabled for '%s'", ext_name, name)
                    except Exception as exc:
                        logger.error(
                            "Failed to integrate %s extension '%s': %s",
                            ext_name,
                            name,
                            exc,
                        )

            self.start_service_extensions()
            logger.info("Integrated extensions")
        except Exception as exc:
            logger.error("Error integrating plugin extensions: %s", exc)

    def cleanup_all_extensions(self) -> None:
        """Remove all integrated chrome and shut down services."""
        if not self._main_window:
            return

        logger.info("Cleaning up all plugin extensions...")
        try:
            if self._started_services:
                self.shutdown_service_extensions()

            for plugin_name in list(self._plugin_menu_actions.keys()):
                self._remove_menu_chrome(plugin_name)

            for plugin_name in list(self._plugin_toolbar_actions.keys()):
                self._remove_toolbar_chrome(plugin_name)

            for plugin_name in list(self._plugin_status_widgets.keys()):
                self._remove_status_chrome(plugin_name)

            logger.info("Cleaned up all plugin extensions")
        except Exception as exc:
            logger.error("Error cleaning up extensions: %s", exc)

    def integrate_plugin_extensions_dynamic(
        self, plugin_name: str, plugin_class: type
    ) -> None:
        """Integrate extensions for a single plugin that was just enabled."""
        try:
            from ...plugin_system.extensions import EXTENSION_POINTS

            for ep in EXTENSION_POINTS:
                if ep.name in self._integration_handlers:
                    if ep.check_implements(plugin_class):
                        toggle_name = ep.parent_toggle if ep.parent_toggle else ep.name
                        if self.is_extension_enabled(plugin_name, toggle_name):
                            handler = self._integration_handlers[ep.name]
                            handler(plugin_name, plugin_class)
                            logger.info(
                                "Dynamically integrated %s extension for '%s'",
                                ep.name,
                                plugin_ui_label(plugin_class),
                            )
                        else:
                            logger.debug(
                                "%s extension disabled for '%s'", ep.name, plugin_name
                            )
        except Exception as exc:
            logger.error(
                "Error dynamically integrating extensions for '%s': %s",
                plugin_name,
                exc,
            )

    def remove_plugin_extensions_dynamic(
        self, plugin_name: str, plugin_class: type
    ) -> None:
        """Remove chrome for a plugin. Service shutdown is a separate step."""
        del plugin_class
        self._remove_menu_chrome(plugin_name)
        self._remove_toolbar_chrome(plugin_name)
        self._remove_status_chrome(plugin_name)

    def teardown_plugin(
        self, plugin_name: str, plugin_class: Optional[type] = None
    ) -> None:
        """Shutdown the service (while the instance exists), then remove chrome."""
        self.shutdown_plugin_service(plugin_name, plugin_class)
        self.remove_plugin_extensions_dynamic(plugin_name, plugin_class or type(None))
        if self._main_window is not None and self._main_window.has_plugin_tab(plugin_name):
            self._main_window.remove_plugin_tab(plugin_name)

    def refresh_plugin_extensions(
        self, plugin_name: str, extension_type: Optional[str] = None
    ) -> None:
        """Reconcile extensions for one enabled plugin.

        When *extension_type* is given, only that type is rebuilt. Service
        start/shutdown runs only when the Service toggle itself changed.
        """
        if not self._main_window:
            logger.debug("Cannot refresh extensions: main window not set")
            return

        plugin_class = self.plugin_service.get_plugin(plugin_name)
        if not plugin_class:
            logger.warning("Plugin '%s' not found", plugin_name)
            return

        if not self.plugin_service.is_enabled(plugin_name):
            logger.debug("Plugin '%s' is disabled, skipping refresh", plugin_name)
            return

        if extension_type in (None, "Tab"):
            self._reconcile_tab(plugin_name, plugin_class)

        if extension_type in (None, "Menu"):
            self._remove_menu_chrome(plugin_name)
            if self.is_extension_enabled(plugin_name, "Menu"):
                from ...plugin_system.extensions import get_extension_point

                ep = get_extension_point("Menu")
                if ep and ep.check_implements(plugin_class):
                    self._integrate_menu_extension(plugin_name, plugin_class)

        if extension_type in (None, "Toolbar"):
            self._remove_toolbar_chrome(plugin_name)
            if self.is_extension_enabled(plugin_name, "Toolbar"):
                from ...plugin_system.extensions import get_extension_point

                ep = get_extension_point("Toolbar")
                if ep and ep.check_implements(plugin_class):
                    self._integrate_toolbar_extension(plugin_name, plugin_class)

        if extension_type in (None, "Status"):
            self._remove_status_chrome(plugin_name)
            if self.is_extension_enabled(plugin_name, "Status"):
                from ...plugin_system.extensions import get_extension_point

                ep = get_extension_point("Status")
                if ep and ep.check_implements(plugin_class):
                    self._integrate_status_extension(plugin_name, plugin_class)

        if extension_type in (None, "Service", "Events"):
            from ...plugin_system.extensions import get_extension_point

            ep = get_extension_point("Service")
            implements = bool(ep and ep.check_implements(plugin_class))
            should_run = implements and self.is_extension_enabled(plugin_name, "Service")
            if should_run:
                self._integrate_service_extension(plugin_name, plugin_class)
            else:
                self.shutdown_plugin_service(plugin_name, plugin_class)

        logger.info("Refreshed extensions for '%s'", plugin_ui_label(plugin_class))

    def _reconcile_tab(self, plugin_name: str, plugin_class: type) -> None:
        from ...plugin_system.extensions import get_extension_point

        tab_ep = get_extension_point("Tab")
        if not (tab_ep and tab_ep.check_implements(plugin_class) and self._main_window):
            return

        should_have_tab = self.is_extension_enabled(plugin_name, "Tab")
        tab_exists = self._main_window.has_plugin_tab(plugin_name)

        if should_have_tab and not tab_exists:
            self._main_window.add_plugin_tab(plugin_name, plugin_class)
            logger.info("Dynamically added tab for '%s'", plugin_ui_label(plugin_class))
        elif not should_have_tab and tab_exists:
            self._main_window.remove_plugin_tab(plugin_name)
            logger.info("Dynamically removed tab for '%s'", plugin_ui_label(plugin_class))

    def has_chrome_for_plugin(self, plugin_name: str) -> bool:
        """Return True if menu/toolbar/status chrome is already tracked."""
        return (
            plugin_name in self._plugin_menu_actions
            or plugin_name in self._plugin_toolbar_actions
            or plugin_name in self._plugin_status_widgets
        )

    def start_service_extensions(self) -> None:
        """Start all enabled ServiceExtension plugins in dependency order."""
        try:
            service_plugins = self.plugin_service.get_service_extensions(enabled_only=True)
            for name in self.plugin_service.get_startup_order():
                plugin_class = service_plugins.get(name)
                if plugin_class is None:
                    continue
                try:
                    if self.is_extension_enabled(name, "Service"):
                        self._integrate_service_extension(name, plugin_class)
                    else:
                        logger.debug("Service extension disabled for '%s'", name)
                except Exception as exc:
                    logger.error("Failed to start service extension '%s': %s", name, exc)
        except Exception as exc:
            logger.error("Error starting service extensions: %s", exc)

    def shutdown_service_extensions(self) -> None:
        """Shutdown ServiceExtension plugins (consumers first) while instances exist."""
        try:
            names = [
                name
                for name in self.plugin_service.get_shutdown_order()
                if name in self._started_services
            ]
            for leftover in list(self._started_services):
                if leftover not in names:
                    names.append(leftover)
            for name in names:
                plugin_class = self.plugin_service.get_plugin(name)
                self.shutdown_plugin_service(plugin_name=name, plugin_class=plugin_class)
        except Exception as exc:
            logger.error("Error shutting down service extensions: %s", exc)

    def shutdown_plugin_service(
        self, plugin_name: str, plugin_class: Optional[type] = None
    ) -> None:
        """Call ``on_application_shutdown`` while the instance is still cached."""
        should_stop = plugin_name in self._started_services or (
            plugin_class is not None and hasattr(plugin_class, "on_application_shutdown")
        )
        if not should_stop:
            return
        try:
            if self.plugin_service.has_plugin_instance(plugin_name):
                instance = self.plugin_service.get_plugin_instance(plugin_name)
                if hasattr(instance, "on_application_shutdown"):
                    logger.info(
                        "Shutting down service extension: %s",
                        self._label(plugin_name, plugin_class),
                    )
                    instance.on_application_shutdown()
            else:
                logger.debug(
                    "Skipping service shutdown for '%s' - instance not created",
                    plugin_name,
                )
        except Exception as exc:
            logger.error(
                "Error shutting down service extension '%s': %s", plugin_name, exc
            )
        finally:
            self._started_services.discard(plugin_name)

    def _remove_menu_chrome(self, plugin_name: str) -> None:
        if plugin_name not in self._plugin_menu_actions:
            return
        plugin_class = self.plugin_service.get_plugin(plugin_name)
        for handle in self._plugin_menu_actions[plugin_name]:
            try:
                if self._main_window:
                    self._main_window.remove_menu_item(handle)
            except Exception as exc:
                logger.debug("Error removing menu item: %s", exc)
        if self._main_window and plugin_name in self._plugin_created_menus:
            for menu_title in self._plugin_created_menus[plugin_name]:
                try:
                    self._main_window.remove_menu_if_empty(menu_title)
                except Exception as exc:
                    logger.debug("Error removing empty menu: %s", exc)
        del self._plugin_menu_actions[plugin_name]
        self._plugin_created_menus.pop(plugin_name, None)
        if plugin_class is not None:
            logger.info("Removed menu extensions for '%s'", plugin_ui_label(plugin_class))

    def _remove_toolbar_chrome(self, plugin_name: str) -> None:
        if plugin_name not in self._plugin_toolbar_actions:
            return
        plugin_class = self.plugin_service.get_plugin(plugin_name)
        for handle in self._plugin_toolbar_actions[plugin_name]:
            try:
                if self._main_window:
                    self._main_window.remove_toolbar_action(handle)
            except Exception as exc:
                logger.debug("Error removing toolbar action: %s", exc)
        del self._plugin_toolbar_actions[plugin_name]
        if plugin_class is not None:
            logger.info("Removed toolbar actions for '%s'", plugin_ui_label(plugin_class))

    def _remove_status_chrome(self, plugin_name: str) -> None:
        if plugin_name not in self._plugin_status_widgets:
            return
        plugin_class = self.plugin_service.get_plugin(plugin_name)
        for handle in self._plugin_status_widgets[plugin_name]:
            try:
                if self._main_window:
                    self._main_window.remove_status_widget(handle)
            except Exception as exc:
                logger.debug("Error removing status widget: %s", exc)
        del self._plugin_status_widgets[plugin_name]
        if plugin_class is not None:
            logger.info("Removed status extensions for '%s'", plugin_ui_label(plugin_class))

    def _integrate_menu_extension(self, name: str, plugin_class: type) -> None:
        del plugin_class
        if not self._main_window:
            return
        if name in self._plugin_menu_actions:
            return

        instance = self.plugin_service.get_plugin_instance(name)
        menu_items = instance.get_menu_items()

        self._plugin_menu_actions[name] = []
        self._plugin_created_menus[name] = []

        for item in menu_items:
            handle = self._main_window.add_menu_item(item)
            self._plugin_menu_actions[name].append(handle)
            if item.menu not in self._plugin_created_menus.get(name, []):
                self._plugin_created_menus.setdefault(name, []).append(item.menu)
            logger.debug(
                "Added menu item '%s' to '%s' from plugin '%s'",
                item.label,
                item.menu,
                name,
            )

    def _integrate_status_extension(self, name: str, plugin_class: type) -> None:
        del plugin_class
        if not self._main_window:
            return
        if name in self._plugin_status_widgets:
            return

        instance = self.plugin_service.get_plugin_instance(name)
        handle = self._main_window.add_status_widget_for_plugin(name, instance)
        if handle:
            self._plugin_status_widgets[name] = [handle]
            logger.debug("Added status bar widget from plugin '%s'", name)

    def _integrate_toolbar_extension(self, name: str, plugin_class: type) -> None:
        del plugin_class
        if not self._main_window:
            return
        if name in self._plugin_toolbar_actions:
            return

        instance = self.plugin_service.get_plugin_instance(name)
        actions = instance.get_toolbar_actions()

        self._plugin_toolbar_actions[name] = []

        for action_def in actions:
            handle = self._main_window.add_toolbar_action(action_def)
            self._plugin_toolbar_actions[name].append(handle)
            logger.debug(
                "Added toolbar action '%s' from plugin '%s'", action_def.label, name
            )

    def _integrate_service_extension(self, name: str, plugin_class: type) -> None:
        if name in self._started_services:
            return
        instance = self.plugin_service.get_plugin_instance(name)
        logger.info("Starting service extension: %s", self._label(name, plugin_class))
        instance.on_application_start(self.container)
        self._started_services.add(name)


__all__ = ["PluginExtensionHost"]
