"""Toolkit-neutral plugin lifecycle controller.

Wraps :class:`~GUI.app.ui.plugin_extension_host.PluginExtensionHost` and
exposes enable/disable plus optional listeners for shell updates.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from ....plugin_system.identity import plugin_ui_label
from ...services.plugin_service import PluginService
from ...services.interfaces import ISettingsService
from ..abstractions.shell import IMainWindowShell
from ..plugin_extension_host import PluginExtensionHost

if TYPE_CHECKING:
    from ...services.container import ServiceContainer

logger = logging.getLogger(__name__)

PluginToggledListener = Callable[[str, bool], None]
PluginStateChangedListener = Callable[[], None]


class PluginController:
    """Controller for managing plugins and their lifecycle."""

    def __init__(self, container: "ServiceContainer") -> None:
        self.container = container
        self._host = PluginExtensionHost(container)

        self.settings_service = container.get(ISettingsService)
        self.plugin_service = container.get(PluginService)

        self._plugin_toggled_listeners: List[PluginToggledListener] = []
        self._plugin_state_changed_listeners: List[PluginStateChangedListener] = []

    @property
    def _main_window(self) -> Optional[IMainWindowShell]:
        return self._host.main_window

    @_main_window.setter
    def _main_window(self, value: Optional[IMainWindowShell]) -> None:
        self._host.set_main_window(value)

    def add_plugin_toggled_listener(self, callback: PluginToggledListener) -> None:
        """Register a listener invoked after a successful plugin toggle."""
        if callback not in self._plugin_toggled_listeners:
            self._plugin_toggled_listeners.append(callback)

    def remove_plugin_toggled_listener(self, callback: PluginToggledListener) -> None:
        """Remove a previously registered plugin-toggled listener."""
        try:
            self._plugin_toggled_listeners.remove(callback)
        except ValueError:
            pass

    def add_plugin_state_changed_listener(
        self, callback: PluginStateChangedListener
    ) -> None:
        """Register a listener invoked when plugin enabled/disabled state changes."""
        if callback not in self._plugin_state_changed_listeners:
            self._plugin_state_changed_listeners.append(callback)

    def remove_plugin_state_changed_listener(
        self, callback: PluginStateChangedListener
    ) -> None:
        """Remove a previously registered state-changed listener."""
        try:
            self._plugin_state_changed_listeners.remove(callback)
        except ValueError:
            pass

    def _notify_plugin_toggled(self, plugin_name: str, enabled: bool) -> None:
        for callback in list(self._plugin_toggled_listeners):
            try:
                callback(plugin_name, enabled)
            except Exception:
                logger.exception("plugin_toggled listener failed")

    def _notify_plugin_state_changed(self) -> None:
        for callback in list(self._plugin_state_changed_listeners):
            try:
                callback()
            except Exception:
                logger.exception("plugin_state_changed listener failed")

    def toggle_plugin(self, plugin_name: str, enabled: bool) -> bool:
        """Toggle a plugin on or off.

        Enablement is committed only after construction and ``on_plugin_enabled``
        succeed. Disabling a provider also disables enabled dependents.
        Unchanged requests are no-ops (no persist, notify, or integrate).
        """
        plugin_class = self.plugin_service.get_plugin(plugin_name)
        if not plugin_class:
            logger.warning("Plugin '%s' not found", plugin_name)
            return False

        key = self.plugin_service.resolve_plugin_key(plugin_name) or plugin_name

        if enabled:
            if self.plugin_service.is_enabled(key):
                return True
            if not self.plugin_service.activate_plugin(key):
                err = self.plugin_service.get_last_activation_error()
                logger.error(
                    "Failed to enable plugin '%s'%s",
                    key,
                    f": {err}" if err else "",
                )
                return False
            logger.info("Enabled plugin: %s", plugin_ui_label(plugin_class))

            if self._host.main_window is not None:
                self._host.integrate_plugin_extensions_dynamic(key, plugin_class)
            else:
                logger.warning(
                    "Cannot dynamically integrate extensions for '%s': MainWindow not set",
                    key,
                )
            self._save_plugin_states()
            self._notify_plugin_toggled(key, True)
            self._notify_plugin_state_changed()
            return True

        if not self.plugin_service.is_enabled(key) and not self.plugin_service.has_plugin_instance(key):
            return True

        targets = self.plugin_service.list_deactivation_targets(key)
        for did in targets:
            cls = self.plugin_service.get_plugin(did)
            self._host.teardown_plugin(did, cls)

        deactivated = self.plugin_service.deactivate_plugin(key)

        self._save_plugin_states()
        for did in deactivated:
            self._notify_plugin_toggled(did, False)
        if not deactivated:
            self._notify_plugin_toggled(key, False)
        self._notify_plugin_state_changed()
        return True

    def is_plugin_enabled(self, plugin_name: str) -> bool:
        return self.plugin_service.is_enabled(plugin_name)

    def refresh_plugin_extensions(
        self, plugin_name: str, extension_type: Optional[str] = None
    ) -> None:
        self._host.refresh_plugin_extensions(plugin_name, extension_type)

    def get_plugin(self, plugin_name: str) -> Optional[Any]:
        return self.plugin_service.get_plugin(plugin_name)

    def get_enabled_plugins(self) -> Dict[str, Any]:
        return self.plugin_service.get_enabled_plugins()

    def get_all_plugins(self) -> Dict[str, Any]:
        return self.plugin_service.get_all_plugins()

    def list_plugin_names(self) -> list[str]:
        """Return registry keys (``plugin_id`` values) for all registered plugins."""
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
            user_disabled = []
            user_enabled = []
            for plugin_name in self.plugin_service.list_plugin_names():
                plugin_class = self.plugin_service.get_plugin(plugin_name)
                if not plugin_class:
                    continue
                default_off = getattr(plugin_class, "disabled_by_default", False)
                is_enabled = self.plugin_service.is_enabled(plugin_name)
                if not is_enabled and not default_off:
                    user_disabled.append(plugin_name)
                elif is_enabled and default_off:
                    user_enabled.append(plugin_name)

            logger.debug(
                "Saving plugin state overrides: disabled=%s enabled=%s",
                user_disabled,
                user_enabled,
            )
            saver = getattr(self.settings_service, "save_plugin_overrides", None)
            if callable(saver):
                saver(user_disabled, user_enabled)
            else:
                self.settings_service.save_disabled_plugins(user_disabled)
                self.settings_service.save_enabled_plugins(user_enabled)
        except Exception as e:
            logger.warning("Failed to save plugin states: %s", e)

    def cleanup_all_extensions(self) -> None:
        self._host.cleanup_all_extensions()

    def integrate_extensions(self, main_window: IMainWindowShell) -> None:
        self._host.integrate_extensions(main_window)

    def start_service_extensions(self) -> None:
        self._host.start_service_extensions()

    def shutdown_service_extensions(self) -> None:
        self._host.shutdown_service_extensions()


__all__ = ["PluginController"]
