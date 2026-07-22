"""Toolkit-neutral plugin extension host.

Integrates Menu / Status / Toolbar / Service extensions into an
``IMainWindowShell``. Qt and TUI backends share this orchestration;
toolkit-specific chrome lives in each shell implementation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from ..services.interfaces import ISettingsService
from ..services.plugin_registry_facade import PluginRegistryFacade
from ..services.plugin_service import PluginService
from .abstractions.shell import IMainWindowShell
from .abstractions.types import (
    MenuItemHandle,
    MenuItemSpec,
    StatusWidgetHandle,
    ToolbarActionHandle,
    ToolbarActionSpec,
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
        self.registry = container.get(PluginRegistryFacade)

        self._main_window: Optional[IMainWindowShell] = None
        self._plugin_menu_actions: Dict[str, List[MenuItemHandle]] = {}
        self._plugin_toolbar_actions: Dict[str, List[ToolbarActionHandle]] = {}
        self._plugin_status_widgets: Dict[str, List[StatusWidgetHandle]] = {}
        self._plugin_created_menus: Dict[str, List[str]] = {}
        self._service_extensions_started: bool = False

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

    def is_extension_enabled(self, plugin_name: str, extension_type: str) -> bool:
        """Check if a specific extension type is enabled for a plugin."""
        if not self.settings_service:
            return True
        return self.settings_service.is_extension_enabled(plugin_name, extension_type)

    def integrate_extensions(self, main_window: IMainWindowShell) -> None:
        """Integrate Menu/Status/Toolbar extensions and start services."""
        self._main_window = main_window
        self.cleanup_all_extensions()

        try:
            registry_queries = {
                "Menu": self.registry.get_menu_extensions,
                "Status": self.registry.get_status_extensions,
                "Toolbar": self.registry.get_toolbar_extensions,
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
            if self._service_extensions_started:
                self.shutdown_service_extensions()

            for plugin_name in list(self._plugin_menu_actions.keys()):
                for handle in self._plugin_menu_actions[plugin_name]:
                    try:
                        self._main_window.remove_menu_item(handle)
                    except Exception as exc:
                        logger.debug("Error removing menu item: %s", exc)
                del self._plugin_menu_actions[plugin_name]

            for plugin_name in list(self._plugin_created_menus.keys()):
                for menu_title in self._plugin_created_menus[plugin_name]:
                    try:
                        self._main_window.remove_menu_if_empty(menu_title)
                    except Exception as exc:
                        logger.debug("Error removing created menu: %s", exc)
                del self._plugin_created_menus[plugin_name]

            for plugin_name in list(self._plugin_toolbar_actions.keys()):
                for handle in self._plugin_toolbar_actions[plugin_name]:
                    try:
                        self._main_window.remove_toolbar_action(handle)
                    except Exception as exc:
                        logger.debug("Error removing toolbar action: %s", exc)
                del self._plugin_toolbar_actions[plugin_name]

            for plugin_name in list(self._plugin_status_widgets.keys()):
                for handle in self._plugin_status_widgets[plugin_name]:
                    try:
                        self._main_window.remove_status_widget(handle)
                    except Exception as exc:
                        logger.debug("Error removing status widget: %s", exc)
                del self._plugin_status_widgets[plugin_name]

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
                                plugin_name,
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
        """Remove extensions for a plugin that was just disabled."""
        try:
            if plugin_name in self._plugin_menu_actions:
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
                if plugin_name in self._plugin_created_menus:
                    del self._plugin_created_menus[plugin_name]
                logger.info("Removed menu extensions for '%s'", plugin_name)

            if plugin_name in self._plugin_toolbar_actions:
                for handle in self._plugin_toolbar_actions[plugin_name]:
                    try:
                        if self._main_window:
                            self._main_window.remove_toolbar_action(handle)
                    except Exception as exc:
                        logger.debug("Error removing toolbar action: %s", exc)
                del self._plugin_toolbar_actions[plugin_name]
                logger.info("Removed toolbar actions for '%s'", plugin_name)

            if plugin_name in self._plugin_status_widgets:
                for handle in self._plugin_status_widgets[plugin_name]:
                    try:
                        if self._main_window:
                            self._main_window.remove_status_widget(handle)
                    except Exception as exc:
                        logger.debug("Error removing status widget: %s", exc)
                del self._plugin_status_widgets[plugin_name]
                logger.info("Removed status extensions for '%s'", plugin_name)

            if hasattr(plugin_class, "on_application_shutdown"):
                try:
                    if self.registry.has_plugin_instance(plugin_name):
                        instance = self.registry.get_plugin_instance(plugin_name)
                        instance.on_application_shutdown()
                        logger.info("Shutdown service extension for '%s'", plugin_name)
                    else:
                        logger.debug(
                            "Skipping service shutdown for '%s' - instance not created",
                            plugin_name,
                        )
                except Exception as exc:
                    logger.error(
                        "Error shutting down service extension '%s': %s",
                        plugin_name,
                        exc,
                    )
        except Exception as exc:
            logger.error("Error removing extensions for '%s': %s", plugin_name, exc)

    def refresh_plugin_extensions(self, plugin_name: str) -> None:
        """Remove and re-integrate extensions for one enabled plugin."""
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

        self.remove_plugin_extensions_dynamic(plugin_name, plugin_class)
        self.integrate_plugin_extensions_dynamic(plugin_name, plugin_class)

        from ...plugin_system.extensions import get_extension_point

        tab_ep = get_extension_point("Tab")
        if tab_ep and tab_ep.check_implements(plugin_class) and self._main_window:
            should_have_tab = self.is_extension_enabled(plugin_name, "Tab")
            tab_exists = self._main_window.has_plugin_tab(plugin_name)

            if should_have_tab and not tab_exists:
                self._main_window.add_plugin_tab(plugin_name, plugin_class)
                logger.info("Dynamically added tab for '%s'", plugin_name)
            elif not should_have_tab and tab_exists:
                self._main_window.remove_plugin_tab(plugin_name)
                logger.info("Dynamically removed tab for '%s'", plugin_name)

        logger.info("Refreshed extensions for '%s'", plugin_name)

    def has_chrome_for_plugin(self, plugin_name: str) -> bool:
        """Return True if menu/toolbar/status chrome is already tracked."""
        return (
            plugin_name in self._plugin_menu_actions
            or plugin_name in self._plugin_toolbar_actions
            or plugin_name in self._plugin_status_widgets
        )

    def start_service_extensions(self) -> None:
        """Start all enabled ServiceExtension plugins."""
        try:
            service_plugins = self.registry.get_service_extensions(enabled_only=True)
            for name, plugin_class in service_plugins.items():
                try:
                    if self.is_extension_enabled(name, "Service"):
                        self._integrate_service_extension(name, plugin_class)
                    else:
                        logger.debug("Service extension disabled for '%s'", name)
                except Exception as exc:
                    logger.error("Failed to start service extension '%s': %s", name, exc)
            self._service_extensions_started = True
        except Exception as exc:
            logger.error("Error starting service extensions: %s", exc)

    def shutdown_service_extensions(self) -> None:
        """Shutdown all ServiceExtension plugins that have instances."""
        try:
            service_plugins = self.registry.get_service_extensions(enabled_only=True)
            for name, _plugin_class in service_plugins.items():
                try:
                    if self.registry.has_plugin_instance(name):
                        instance = self.registry.get_plugin_instance(name)
                        logger.info("Shutting down service extension: %s", name)
                        instance.on_application_shutdown()
                except Exception as exc:
                    logger.error(
                        "Error shutting down service extension '%s': %s", name, exc
                    )
            self._service_extensions_started = False
        except Exception as exc:
            logger.error("Error shutting down service extensions: %s", exc)

    def _integrate_menu_extension(self, name: str, plugin_class: type) -> None:
        del plugin_class
        if not self._main_window:
            return

        instance = self.registry.get_plugin_instance(name)
        menu_items = instance.get_menu_items()

        if name not in self._plugin_menu_actions:
            self._plugin_menu_actions[name] = []
        if name not in self._plugin_created_menus:
            self._plugin_created_menus[name] = []

        for item in menu_items:
            spec = MenuItemSpec(
                menu_title=item.menu,
                label=item.label,
                callback=item.callback,
                shortcut=item.shortcut,
                icon=item.icon,
                enabled=item.enabled,
                separator_before=item.separator_before,
                separator_after=item.separator_after,
            )
            handle = self._main_window.add_menu_item(spec)
            self._plugin_menu_actions[name].append(handle)
            if spec.menu_title not in self._plugin_created_menus.get(name, []):
                self._plugin_created_menus.setdefault(name, []).append(spec.menu_title)
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

        instance = self.registry.get_plugin_instance(name)
        handle = self._main_window.add_status_widget_for_plugin(name, instance)
        if handle:
            if name not in self._plugin_status_widgets:
                self._plugin_status_widgets[name] = []
            self._plugin_status_widgets[name].append(handle)
            logger.debug("Added status bar widget from plugin '%s'", name)

    def _integrate_toolbar_extension(self, name: str, plugin_class: type) -> None:
        del plugin_class
        if not self._main_window:
            return

        instance = self.registry.get_plugin_instance(name)
        actions = instance.get_toolbar_actions()

        if name not in self._plugin_toolbar_actions:
            self._plugin_toolbar_actions[name] = []

        for action_def in actions:
            spec = ToolbarActionSpec(
                label=action_def.label,
                callback=action_def.callback,
                icon=action_def.icon,
                tooltip=action_def.tooltip,
                checkable=action_def.checkable,
                checked=action_def.checked,
            )
            handle = self._main_window.add_toolbar_action(spec)
            self._plugin_toolbar_actions[name].append(handle)
            logger.debug(
                "Added toolbar action '%s' from plugin '%s'", action_def.label, name
            )

    def _integrate_service_extension(self, name: str, plugin_class: type) -> None:
        del plugin_class
        instance = self.registry.get_plugin_instance(name)
        logger.info("Starting service extension: %s", name)
        instance.on_application_start(self.container)


__all__ = ["PluginExtensionHost"]
