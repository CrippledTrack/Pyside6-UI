"""
Plugin management controller.

Qt-facing wrapper around the toolkit-neutral PluginExtensionHost, plus
plugin enable/disable and Qt signals.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..bindings import QObject, Signal

from ....services.plugin_service import PluginService
from ....services.interfaces import ISettingsService
from ....services.plugin_registry_facade import PluginRegistryFacade
from ...abstractions.shell import IMainWindowShell
from ...plugin_extension_host import PluginExtensionHost

if TYPE_CHECKING:
    from ....services.container import ServiceContainer

logger = logging.getLogger(__name__)


class PluginController(QObject):
    """Controller for managing plugins and their lifecycle."""

    plugin_toggled = Signal(str, bool)  # Emitted when a plugin is toggled (name, enabled)
    plugin_state_changed = Signal()  # Emitted when plugin states change

    def __init__(
        self,
        container: "ServiceContainer",
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.container = container
        self._host = PluginExtensionHost(container)

        self.settings_service = container.get(ISettingsService)
        self.plugin_service = container.get(PluginService)
        self.registry = container.get(PluginRegistryFacade)

    @property
    def _main_window(self) -> Optional[IMainWindowShell]:
        return self._host.main_window

    @_main_window.setter
    def _main_window(self, value: Optional[IMainWindowShell]) -> None:
        self._host.set_main_window(value)

    def toggle_plugin(self, plugin_name: str, enabled: bool) -> bool:
        """Toggle a plugin on or off."""
        plugin_class = self.plugin_service.get_plugin(plugin_name)
        if not plugin_class:
            logger.warning("Plugin '%s' not found", plugin_name)
            return False

        if enabled:
            if not self.plugin_service.is_enabled(plugin_name):
                self.plugin_service.enable_plugin(plugin_name)
                logger.info("Enabled plugin: %s", plugin_name)
                try:
                    instance = self.registry.get_plugin_instance(plugin_name)
                    if hasattr(instance, "on_plugin_enabled"):
                        instance.on_plugin_enabled()
                except Exception as e:
                    logger.error(
                        "Error calling on_plugin_enabled for '%s': %s", plugin_name, e
                    )
                self.registry.publish_event(
                    "plugin_enabled", {"plugin_name": plugin_name}
                )

            if self._host.main_window is not None:
                if not self._host.has_chrome_for_plugin(plugin_name):
                    self._host.integrate_plugin_extensions_dynamic(
                        plugin_name, plugin_class
                    )
                else:
                    logger.debug("Extensions already integrated for '%s'", plugin_name)
            else:
                logger.warning(
                    "Cannot dynamically integrate extensions for '%s': MainWindow not set",
                    plugin_name,
                )
        else:
            if self.plugin_service.is_enabled(plugin_name):
                try:
                    if self.registry.has_plugin_instance(plugin_name):
                        instance = self.registry.get_plugin_instance(plugin_name)
                        if hasattr(instance, "on_plugin_disabled"):
                            instance.on_plugin_disabled()
                except Exception as e:
                    logger.error(
                        "Error calling on_plugin_disabled for '%s': %s", plugin_name, e
                    )
                self.plugin_service.disable_plugin(plugin_name)
                logger.info("Disabled plugin: %s", plugin_name)
                self.registry.publish_event(
                    "plugin_disabled", {"plugin_name": plugin_name}
                )

            if self._host.main_window is not None:
                self._host.remove_plugin_extensions_dynamic(plugin_name, plugin_class)

        self._save_plugin_states()
        self.plugin_toggled.emit(plugin_name, enabled)
        self.plugin_state_changed.emit()

        if not enabled:
            try:
                self.registry.unload_plugin_instance(plugin_name)
            except Exception as e:
                logger.error("Error unloading plugin instance '%s': %s", plugin_name, e)

        return True

    def is_plugin_enabled(self, plugin_name: str) -> bool:
        return self.plugin_service.is_enabled(plugin_name)

    def refresh_plugin_extensions(self, plugin_name: str) -> None:
        self._host.refresh_plugin_extensions(plugin_name)

    def get_plugin(self, plugin_name: str) -> Optional[Any]:
        return self.plugin_service.get_plugin(plugin_name)

    def get_enabled_plugins(self) -> Dict[str, Any]:
        return self.plugin_service.get_enabled_plugins()

    def get_all_plugins(self) -> Dict[str, Any]:
        return self.plugin_service.get_all_plugins()

    def list_plugin_names(self) -> list[str]:
        return self.plugin_service.list_plugin_names()

    def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        plugin_class = self.plugin_service.get_plugin(plugin_name)
        if not plugin_class:
            return None
        return plugin_class.get_plugin_info()

    def _is_extension_enabled(self, plugin_name: str, extension_type: str) -> bool:
        return self._host.is_extension_enabled(plugin_name, extension_type)

    def _save_plugin_states(self) -> None:
        if not self.settings_service:
            return

        try:
            all_disabled = [
                name
                for name in self.plugin_service.list_plugin_names()
                if not self.plugin_service.is_enabled(name)
            ]

            user_disabled = []
            for plugin_name in all_disabled:
                plugin_class = self.plugin_service.get_plugin(plugin_name)
                if plugin_class and not getattr(
                    plugin_class, "disabled_by_default", False
                ):
                    user_disabled.append(plugin_name)

            logger.debug("Saving user-disabled plugins: %s", user_disabled)
            self.settings_service.save_disabled_plugins(user_disabled)
        except Exception as e:
            logger.warning("Failed to save plugin states: %s", e)

    def load_plugin_states(self) -> None:
        if not self.settings_service:
            return

        try:
            saved_disabled = self.settings_service.get_disabled_plugins()
            if saved_disabled:
                logger.info("Loading saved user-disabled plugins: %s", saved_disabled)

                cleaned_disabled = []
                for plugin_name in saved_disabled:
                    plugin_class = self.plugin_service.get_plugin(plugin_name)
                    if plugin_class:
                        if getattr(plugin_class, "disabled_by_default", False):
                            logger.debug(
                                "Removing disabled_by_default plugin from settings: %s",
                                plugin_name,
                            )
                        else:
                            self.plugin_service.disable_plugin(plugin_name)
                            cleaned_disabled.append(plugin_name)
                            logger.debug(
                                "Applied user preference: %s disabled", plugin_name
                            )
                    else:
                        logger.debug("Skipping non-existent plugin: %s", plugin_name)

                if len(cleaned_disabled) != len(saved_disabled):
                    logger.info(
                        "Cleaning up settings: removed %s disabled_by_default plugins",
                        len(saved_disabled) - len(cleaned_disabled),
                    )
                    self.settings_service.save_disabled_plugins(cleaned_disabled)
        except Exception as e:
            logger.warning("Failed to load plugin states: %s", e)

    def cleanup_all_extensions(self) -> None:
        self._host.cleanup_all_extensions()

    def integrate_extensions(self, main_window: IMainWindowShell) -> None:
        self._host.integrate_extensions(main_window)

    def start_service_extensions(self) -> None:
        self._host.start_service_extensions()

    def shutdown_service_extensions(self) -> None:
        self._host.shutdown_service_extensions()


__all__ = ["PluginController"]
