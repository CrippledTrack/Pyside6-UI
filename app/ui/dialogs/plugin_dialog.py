"""
Plugin management dialog for enabling, disabling, and configuring plugins.

This module provides a GUI interface for managing plugin lifecycle, including
enabling/disabling plugins, viewing plugin information, and configuring
plugin settings.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from .. import definitions as ui
from ..abstractions.presenters import IDialogPresenter
from ....plugin_system.base import BaseTabPlugin
from ....plugin_system.identity import plugin_display_name

logger = logging.getLogger(__name__)


class PluginManagementDialog:
    """Toolkit-neutral plugin-management content and dialog controller."""

    def __init__(
        self,
        parent: Any = None,
        settings_service: Optional[Any] = None,
        plugin_controller: Optional[Any] = None,
        dialog_presenter: Optional[IDialogPresenter] = None,
        on_plugin_toggled: Optional[Callable[[str, bool], Any]] = None,
    ) -> None:
        self._all_plugins = []  # List of (name, plugin_class)
        self._rejected_plugins = {}  # Dict of name -> (plugin_class, reason)
        self._shown_plugin_count = 0
        self._parent = parent
        self.settings_service = settings_service
        self.plugin_controller = plugin_controller
        if dialog_presenter is None:
            raise ValueError(
                "PluginManagementDialog requires an IDialogPresenter"
            )
        self.dialog_presenter = dialog_presenter
        # Get plugin service from controller (required)
        if plugin_controller and hasattr(plugin_controller, 'plugin_service'):
            self.plugin_service = plugin_controller.plugin_service
        else:
            raise ValueError(
                "PluginManagementDialog requires a plugin_controller with plugin_service"
            )
        self._on_plugin_toggled = (
            on_plugin_toggled or self.plugin_controller.toggle_plugin
        )
        self.dialog = ui.create_dialog(
            "Plugin Management",
            parent=parent,
            modal=False,
            default_size=(900, 560),
        )
        self.setup_ui()
        self.load_plugins()

    def close(self) -> None:
        """Close the definitions-backed management dialog."""
        ui.reject_dialog(self.dialog)

    def setup_ui(self) -> None:
        """Setup the dialog UI."""
        root = ui.create_column(parent=self.dialog, expand=True)

        # Filters/Search bar
        filters = ui.create_row()
        self.search_input = ui.create_input(
            placeholder="Search by name, author, description..."
        )
        ui.set_expand(self.search_input)
        self.type_filter = ui.create_combo(["All Types", "Core", "External"])
        self.status_filter = ui.create_combo(
            ["All Status", "Enabled", "Disabled", "Incompatible"]
        )
        self.perm_filter = ui.create_combo(
            ["All Permissions", "Requires Admin", "No Admin"]
        )
        for label, control in (
            ("Search:", self.search_input),
            ("Type:", self.type_filter),
            ("Status:", self.status_filter),
            ("Permissions:", self.perm_filter),
        ):
            ui.add(filters, ui.create_label(label))
            ui.add(filters, control)
        ui.on_change(self.search_input, lambda _value: self.apply_filters())
        ui.on_change(self.type_filter, lambda _value: self.apply_filters())
        ui.on_change(self.status_filter, lambda _value: self.apply_filters())
        ui.on_change(self.perm_filter, lambda _value: self.apply_filters())
        ui.add(root, filters)

        # Splitter with table (left) and details (right)
        splitter = ui.create_split("horizontal")

        # Table setup
        table_container = ui.create_column(expand=True)
        self.table = ui.create_table(
            ["Enabled", "Name", "Type"],
            check_column=0,
            sortable=True,
            stretch_column=1,
        )
        ui.set_expand(self.table)
        ui.on_select(self.table, lambda _key: self.on_selection_changed())
        ui.on_row_toggled(self.table, self._on_table_toggled)
        ui.on_context_menu(self.table, self._build_table_context_menu)
        ui.add(table_container, self.table)
        ui.add(splitter, table_container)

        # Details panel
        details_container = ui.create_column(expand=True)

        # Details header
        header = ui.create_column()
        self.details_name = ui.create_label("-", role=ui.LabelRole.HEADING)
        self.details_version_author = ui.create_label("-", role=ui.LabelRole.MUTED)
        ui.add(header, self.details_name)
        ui.add(header, self.details_version_author)
        ui.add(details_container, header)

        # Tab Widget
        self.tab_widget = ui.create_tabs()
        ui.add(details_container, self.tab_widget)

        # Tab 1: Overview
        overview_tab = ui.create_column(expand=True)
        ui.add(overview_tab, ui.create_label("Description:"))
        self.details_description = ui.create_text_area(read_only=True, expand=True)
        ui.add(overview_tab, self.details_description)

        # Extension type toggles section
        self.extensions_group = ui.create_group(
            "Extension Types (toggle to enable/disable)"
        )
        extension_row = ui.create_row()
        self.ext_checkboxes: Dict[str, Any] = {}
        from ....plugin_system.extensions import EXTENSION_POINTS
        for ep in EXTENSION_POINTS:
            if not ep.is_user_toggleable:
                continue
            ext_type = ep.name
            cb = ui.create_checkbox(ext_type, checked=True)
            ui.set_enabled(cb, False)
            ui.on_change(
                cb,
                lambda checked, t=ext_type: self._on_extension_toggled(t, checked),
            )
            self.ext_checkboxes[ext_type] = cb
            ui.add(extension_row, cb)

        ui.add_stretch(extension_row)
        ui.add(self.extensions_group, extension_row)
        ui.add(overview_tab, self.extensions_group)
        ui.add_tab(self.tab_widget, overview_tab, "Overview")

        # Tab 2: Technical Details
        tech_tab = ui.create_column()
        form = ui.create_form()
        self.details_plugin_id = ui.create_label("-")
        self.details_type = ui.create_label("-")
        self.details_types = ui.create_label("-")
        self.details_requires_admin = ui.create_label("-")
        self.details_platforms = ui.create_label("-")
        self.details_module = ui.create_label("-")
        self.details_min_gui_version = ui.create_label("-")
        self.details_required_gui_version = ui.create_label("-")
        for label, value in (
            ("Plugin ID:", self.details_plugin_id),
            ("Type:", self.details_type),
            ("Supported Interfaces:", self.details_types),
            ("Requires Admin:", self.details_requires_admin),
            ("Platforms:", self.details_platforms),
            ("Module Path:", self.details_module),
            ("Min GUI Version:", self.details_min_gui_version),
            ("Required GUI Version:", self.details_required_gui_version),
        ):
            ui.add_form_row(form, label, value)
        ui.add(tech_tab, form)
        ui.add_stretch(tech_tab)
        ui.add_tab(self.tab_widget, tech_tab, "Technical Details")

        # Action buttons for details
        actions = ui.create_row()
        self.enable_selected_btn = ui.create_button(
            "Enable Selected", on_click=self.enable_selected
        )
        self.disable_selected_btn = ui.create_button(
            "Disable Selected", on_click=self.disable_selected
        )
        self.configure_btn = ui.create_button(
            "Configure...", on_click=self.configure_selected
        )
        ui.add(actions, self.enable_selected_btn)
        ui.add(actions, self.disable_selected_btn)
        ui.add_stretch(actions)
        ui.add(actions, self.configure_btn)
        ui.add(details_container, actions)

        ui.add(splitter, details_container)
        ui.set_split_proportions(splitter, (1, 1))
        ui.add(root, splitter)

        # Bottom controls
        bottom = ui.create_row()
        self.status_label = ui.create_label("", wrap=False)
        ui.add(bottom, self.status_label)
        ui.add_stretch(bottom)
        self.enable_all_btn = ui.create_button("Enable All", on_click=self.enable_all)
        self.disable_all_btn = ui.create_button(
            "Disable All", on_click=self.disable_all
        )
        self.reload_btn = ui.create_button(
            "Reload Plugins", on_click=self.reload_plugins
        )
        self.close_btn = ui.create_button(
            "Close",
            on_click=lambda: ui.reject_dialog(self.dialog),
        )
        for button in (
            self.enable_all_btn,
            self.disable_all_btn,
            self.reload_btn,
            self.close_btn,
        ):
            ui.add(bottom, button)
        ui.add(root, bottom)
        ui.set_dialog_content(self.dialog, root)

    def _plugin_label(self, plugin_id: str, plugin_class: Optional[Type[Any]] = None) -> str:
        """Display name for UI copy; *plugin_id* remains the registry key."""
        cls = plugin_class
        if cls is None:
            cls = self.plugin_service.get_plugin(plugin_id)
        if cls is None and plugin_id in self._rejected_plugins:
            cls = self._rejected_plugins[plugin_id][0]
        if cls is not None:
            return plugin_display_name(cls)
        return plugin_id

    def _get_extension_types(self, plugin_class: type) -> str:
        """Get a string describing which extension interfaces the plugin implements."""
        from ....plugin_system.extensions import EXTENSION_POINTS
        extensions = []
        for ep in EXTENSION_POINTS:
            if ep.name in ("Events", "PluginProtocol"):
                continue
            if ep.check_implements(plugin_class):
                extensions.append(ep.name)
        return ", ".join(extensions) if extensions else ""

    def load_plugins(self) -> None:
        """Load all plugins from the service, including rejected ones."""
        plugins = self.plugin_service.get_all_plugins()
        self._all_plugins = list(plugins.items())
        # Also load rejected (version-incompatible) plugins
        self._rejected_plugins = self.plugin_service.get_rejected_plugins()
        self.apply_filters()

    def toggle_plugin(self, name: str, state: int | bool) -> None:
        """Toggle plugin enabled/disabled state."""
        enabled = bool(state)
        if not enabled:
            dependents = self.plugin_service.get_enabled_dependents(name)
            if dependents:
                labels = []
                for dep_id in dependents:
                    cls = self.plugin_service.get_plugin(dep_id)
                    labels.append(self._plugin_label(dep_id, cls) if cls else dep_id)
                confirmed = self._confirm(
                    "Disable dependent plugins",
                    "Disabling this plugin will also disable:\n\n"
                    + "\n".join(f"- {label}" for label in labels)
                    + "\n\nContinue?",
                )
                if not confirmed:
                    self.apply_filters()
                    return
        result = self._on_plugin_toggled(name, enabled)
        if result is False:
            err = ""
            getter = getattr(self.plugin_service, "get_last_activation_error", None)
            if callable(getter):
                err = getter() or ""
            self._warning(
                "Plugin not enabled",
                err or f"Failed to enable '{self._plugin_label(name)}'.",
            )
            self.apply_filters()
            return

        # If this is the currently selected plugin, refresh the details panel
        # to update the extension checkboxes (grey out if disabled)
        if name == self.get_selected_plugin_name():
            self.on_selection_changed()
        if not enabled:
            self.apply_filters()
    
    def _force_enable_plugin(self, name: str, state: bool) -> None:
        """Force-enable a version-incompatible plugin."""
        if not state:
            self.toggle_plugin(name, False)
            return
        
        # Show warning before force-enabling
        confirmed = self._confirm(
            "Force Enable Incompatible Plugin",
            f"Plugin '{self._plugin_label(name)}' is marked as incompatible:\n\n"
            f"{self._rejected_plugins.get(name, ('', 'Unknown reason'))[1]}\n\n"
            "Force-enabling may cause crashes or unexpected behavior.\n"
            "Do you want to continue?",
        )
        
        if not confirmed:
            # User cancelled - uncheck the checkbox
            self.apply_filters()
            return
        
        if name in self._rejected_plugins:
            plugin_class, reason = self._rejected_plugins[name]
            self.plugin_service.register_plugin_force(name, plugin_class)
            self.plugin_service.disable_plugin(name)  # Temporarily disable so toggle_plugin executes a full enable cycle
            self.toggle_plugin(name, True)
            self.load_plugins()

    def reload_plugins(self) -> None:
        """Reload all plugins from the registry."""
        if not (self.plugin_controller and self.plugin_controller.plugin_service):
            self._warning(
                "Reload Unavailable",
                "Plugin reload is unavailable because the plugin service is not initialized.",
            )
            return

        # Safely delegate reload to MainWindow if possible to ensure proper UI teardown
        parent = self._parent
        if parent is not None and hasattr(parent, "reload_plugins"):
            parent.reload_plugins()
            ui.accept_dialog(self.dialog)
        else:
            self._warning(
                "Reload Unavailable",
                "Plugin reload requires the main window so tabs and extensions "
                "can be torn down safely. Close this dialog and use Manage Plugins "
                "from the main window, or restart the application.",
            )

    def apply_filters(self) -> None:
        search_text = ui.get_text(self.search_input).strip().lower()
        type_sel = ui.get_text(self.type_filter)
        status_sel = ui.get_text(self.status_filter)
        perm_sel = ui.get_text(self.perm_filter)

        # Preserve current selection
        selected_name = self.get_selected_plugin_name()

        filtered = []
        core_names = set(self.plugin_service.get_core_plugins().keys())
        
        # Combine registered plugins with rejected plugins
        all_plugins_combined = list(self._all_plugins)
        for name, (plugin_class, reason) in self._rejected_plugins.items():
            if name not in dict(all_plugins_combined):
                all_plugins_combined.append((name, plugin_class))
        
        for name, plugin_class in all_plugins_combined:
            info = plugin_class.get_plugin_info()
            is_rejected = name in self._rejected_plugins

            # Text search
            haystack = f"{info['name']} {info['author']} {info['description']} {plugin_class.__module__}".lower()
            if search_text and search_text not in haystack:
                continue

            # Type filter
            is_core = name in core_names
            if type_sel == "Core" and not is_core:
                continue
            if type_sel == "External" and is_core:
                continue

            # Status filter
            is_enabled = self.plugin_service.is_enabled(name)
            if status_sel == "Enabled" and (not is_enabled or is_rejected):
                continue
            if status_sel == "Disabled" and (is_enabled or is_rejected):
                continue
            if status_sel == "Incompatible" and not is_rejected:
                continue

            # Permissions filter
            requires_admin = bool(info.get('requires_admin'))
            if perm_sel == "Requires Admin" and not requires_admin:
                continue
            if perm_sel == "No Admin" and requires_admin:
                continue

            filtered.append((name, plugin_class))

        self.populate_table(filtered)

        # Restore selection
        restored = bool(selected_name and ui.select_row(self.table, selected_name))
        # Update details/status if nothing selected
        if not restored and filtered:
            ui.select_row(self.table, filtered[0][0])

        self.update_status_label()

    def populate_table(self, data: List[Tuple[str, Type[BaseTabPlugin]]]) -> None:
        rows = []
        core_names = set(self.plugin_service.get_core_plugins().keys())
        for name, plugin_class in data:
            info = plugin_class.get_plugin_info()
            is_enabled = self.plugin_service.is_enabled(name)
            is_core = name in core_names
            is_rejected = name in self._rejected_plugins
            tooltip = None
            if is_rejected:
                rejection_reason = self._rejected_plugins[name][1]
                tooltip = (
                    f"Incompatible: {rejection_reason}\n"
                    "Toggle to force-enable anyway"
                )
            rows.append(
                ui.TableRow(
                    key=name,
                    cells=(
                        "⚠" if is_rejected else "",
                        info["name"],
                        "Core" if is_core else "External",
                    ),
                    checked=is_enabled and (
                        not is_rejected or name in dict(self._all_plugins)
                    ),
                    role=ui.LabelRole.WARNING if is_rejected else None,
                    tooltip=tooltip,
                )
            )
        self._shown_plugin_count = len(rows)
        ui.set_table_rows(self.table, rows)

    def _on_table_toggled(self, name: str, checked: bool) -> None:
        """Dispatch a definitions table check change."""
        if name in self._rejected_plugins:
            self._force_enable_plugin(name, checked)
        else:
            self.toggle_plugin(name, checked)

    def on_selection_changed(self) -> None:
        name = self.get_selected_plugin_name()
        if not name:
            self.clear_details()
            return
        
        # Try to get plugin from service first, then from rejected plugins
        plugin_class = self.plugin_service.get_plugin(name)
        is_rejected = False
        if not plugin_class:
            # Check if it's a rejected plugin
            if name in self._rejected_plugins:
                plugin_class, rejection_reason = self._rejected_plugins[name]
                is_rejected = True
            else:
                self.clear_details()
                return
        
        info = plugin_class.get_plugin_info()
        ui.set_text(self.details_name, info['name'])
        
        authors_list = info.get('authors') or []
        authors_text = ", ".join(authors_list) if authors_list else info.get('author', '')
        author_str = f" by {authors_text}" if authors_text else ""
        ui.set_text(
            self.details_version_author,
            f"Version {info['version']}{author_str}",
        )
        
        ui.set_text(
            self.details_plugin_id,
            info.get("plugin_id") or name,
        )
        ui.set_text(
            self.details_type,
            "Core" if name in self.plugin_service.get_core_plugins() else "External",
        )
        ui.set_text(self.details_platforms, ', '.join(info['supported_platforms']))
        ui.set_text(
            self.details_requires_admin,
            "Yes" if info.get('requires_admin') else "No",
        )
        ui.set_text(self.details_module, plugin_class.__module__)
        ui.set_text(
            self.details_min_gui_version,
            info.get('min_gui_version') or "-",
        )
        ui.set_text(
            self.details_required_gui_version,
            info.get('required_gui_version') or "-",
        )
        ui.set_text(self.details_description, info.get('description', ''))
        
        # Detect plugin types
        types_str = self._get_extension_types(plugin_class)
        ui.set_text(self.details_types, types_str if types_str else "Tab only")
        
        # Configure button availability
        has_config = any([
            hasattr(plugin_class, 'get_settings_widget') and callable(getattr(plugin_class, 'get_settings_widget', None)),
            hasattr(plugin_class, 'open_settings_dialog'),
            hasattr(plugin_class, 'get_configuration_widget'),
            hasattr(plugin_class, 'configure')
        ])
        ui.set_enabled(self.configure_btn, has_config)
        
        # Update extension checkboxes
        extension_types = self._get_extension_types(plugin_class).split(", ")
        detected_types = [t.strip() for t in extension_types] if extension_types else []
        is_plugin_enabled = self.plugin_service.is_enabled(name)
        
        any_visible = False
        for ext_type, cb in self.ext_checkboxes.items():
            # Check if plugin supports this certification
            # Note: "Service" checkbox also controls "Events"
            is_supported = ext_type in detected_types
            if ext_type == "Service" and "Events" in detected_types:
                is_supported = True
            
            # Reset state first
            if is_supported:
                ui.set_visible(cb, True)
                ui.set_enabled(cb, is_plugin_enabled)
                any_visible = True
                
                # If plugin is disabled, visually uncheck extensions (even if enabled in settings)
                if not is_plugin_enabled:
                    ui.set_checked(cb, False, notify=False)
                elif self.settings_service:
                    is_ext_enabled = self.settings_service.is_extension_enabled(name, ext_type)
                    ui.set_checked(cb, is_ext_enabled, notify=False)
                else:
                    ui.set_checked(cb, True, notify=False)
            else:
                ui.set_visible(cb, False)
                ui.set_checked(cb, False, notify=False)
                ui.set_enabled(cb, False)
            
        ui.set_visible(self.extensions_group, any_visible)

    def clear_details(self) -> None:
        for widget in (
            self.details_name,
            self.details_version_author,
            self.details_plugin_id,
            self.details_type,
            self.details_types,
            self.details_requires_admin,
            self.details_platforms,
            self.details_module,
            self.details_min_gui_version,
            self.details_required_gui_version,
        ):
            ui.set_text(widget, "-")
        ui.set_text(self.details_description, "")
        ui.set_enabled(self.configure_btn, False)
        
        # Reset extension checkboxes
        for cb in self.ext_checkboxes.values():
            ui.set_checked(cb, False, notify=False)
            ui.set_enabled(cb, False)
    
    def _on_extension_toggled(self, extension_type: str, state: bool) -> None:
        """Handle extension type checkbox toggle.
        
        Args:
            extension_type: The extension type (e.g., "Tab", "Menu", "Toolbar")
            state: Whether the extension is enabled.
        """
        name = self.get_selected_plugin_name()
        if not name or not self.settings_service:
            return
        
        enabled = bool(state)
        self.settings_service.set_extension_enabled(name, extension_type, enabled)
        
        # Service checkbox also controls Events (they're grouped for user simplicity)
        if extension_type == "Service":
            self.settings_service.set_extension_enabled(name, "Events", enabled)
        
        # Refresh extensions to apply the change
        if self.plugin_controller:
            self.plugin_controller.refresh_plugin_extensions(name)

    def update_status_label(self) -> None:
        total = len(self._all_plugins)
        shown = self._shown_plugin_count
        enabled_count = sum(1 for name, _ in self._all_plugins if self.plugin_service.is_enabled(name))
        ui.set_text(
            self.status_label,
            f"Showing {shown}/{total} plugins  |  Enabled: {enabled_count}",
        )

    def get_selected_plugin_name(self) -> Optional[str]:
        key = ui.get_selected_key(self.table)
        return str(key) if key is not None else None

    def enable_selected(self) -> None:
        """Enable the currently selected plugin."""
        name = self.get_selected_plugin_name()
        if not name:
            return
        self.toggle_plugin(name, True)
        self.apply_filters()
        self.on_selection_changed()

    def disable_selected(self) -> None:
        """Disable the currently selected plugin."""
        name = self.get_selected_plugin_name()
        if not name:
            return
        self.toggle_plugin(name, False)
        self.apply_filters()
        self.on_selection_changed()

    def enable_all(self) -> None:
        """Enable all plugins."""
        tab_controller = None
        if self._parent and hasattr(self._parent, "tab_controller"):
            tab_controller = self._parent.tab_controller
            tab_controller.set_batch_loading(True)
            
        try:
            for name, _ in self._all_plugins:
                self.toggle_plugin(name, True)
        finally:
            if tab_controller:
                tab_controller.set_batch_loading(False)
                # Load the currently active tab since batch loading is now off
                if hasattr(self._parent, "tab_widget"):
                    current_index = self._parent.tab_widget.currentIndex()
                    if current_index >= 0:
                        tab_controller.on_tab_changed(current_index)
                        
        self.apply_filters()
        self.on_selection_changed()

    def disable_all(self) -> None:
        """Disable all plugins."""
        tab_controller = None
        if self._parent and hasattr(self._parent, "tab_controller"):
            tab_controller = self._parent.tab_controller
            tab_controller.set_batch_loading(True)
            
        try:
            for name, _ in self._all_plugins:
                self.toggle_plugin(name, False)
        finally:
            if tab_controller:
                tab_controller.set_batch_loading(False)
                if hasattr(self._parent, "tab_widget"):
                    current_index = self._parent.tab_widget.currentIndex()
                    if current_index >= 0:
                        tab_controller.on_tab_changed(current_index)
                        
        self.apply_filters()
        self.on_selection_changed()

    def _build_table_context_menu(self) -> List[ui.MenuAction]:
        """Build context actions for the currently selected plugin."""
        name = self.get_selected_plugin_name()
        if not name:
            return []
        plugin_class = self.plugin_service.get_plugin(name)
        if not plugin_class:
            return []
        info = plugin_class.get_plugin_info()
        is_enabled = self.plugin_service.is_enabled(name)
        has_config = any([
            hasattr(plugin_class, 'get_settings_widget') and callable(getattr(plugin_class, 'get_settings_widget', None)),
            hasattr(plugin_class, 'open_settings_dialog'),
            hasattr(plugin_class, 'get_configuration_widget'),
            hasattr(plugin_class, 'configure')
        ])
        toggle = self.disable_selected if is_enabled else self.enable_selected
        return [
            ui.MenuAction("Disable" if is_enabled else "Enable", toggle),
            ui.MenuAction(
                "Configure...",
                self.configure_selected,
                enabled=has_config,
            ),
            ui.MenuAction(
                "Copy Name",
                lambda: ui.copy_to_clipboard(self._plugin_label(name, plugin_class)),
                separator_before=True,
            ),
            ui.MenuAction(
                "Copy Full Info",
                lambda: self._copy_full_info(name, plugin_class, info),
            ),
        ]

    def _copy_full_info(
        self,
        name: str,
        plugin_class: Type[BaseTabPlugin],
        info: Dict[str, Any],
    ) -> None:
        """Copy the selected plugin's complete summary."""
        lines = [
            f"Name: {info['name']}",
            f"Plugin ID: {info.get('plugin_id') or name}",
            f"Version: {info['version']}",
            f"Author: {info['author']}",
            f"Type: {'Core' if name in self.plugin_service.get_core_plugins() else 'External'}",
            f"Requires Admin: {'Yes' if info.get('requires_admin') else 'No'}",
            f"Compatible: {'Yes' if info.get('compatible', True) else 'No'}",
            f"Platforms: {', '.join(info['supported_platforms'])}",
            f"Module: {plugin_class.__module__}",
            f"Description: {info.get('description', '')}",
        ]
        ui.copy_to_clipboard("\n".join(lines))

    def configure_selected(self) -> None:
        """Configure the selected plugin using get_settings_widget() method."""
        name = self.get_selected_plugin_name()
        if not name:
            return
        plugin_class = self.plugin_service.get_plugin(name)
        if not plugin_class:
            return
        label = self._plugin_label(name, plugin_class)

        plugin_target: Any = plugin_class
        try:
            plugin_target = self.plugin_service.get_plugin_instance(name)
        except Exception as e:
            logger.debug(f"Using plugin class for settings (instance unavailable) '{name}': {e}")
        
        try:
            # Try new get_settings_widget() method first
            if hasattr(plugin_target, 'get_settings_widget') and callable(getattr(plugin_target, 'get_settings_widget')):
                settings_widget = plugin_target.get_settings_widget(self.dialog)
                if settings_widget:
                    # Load current settings
                    current_settings = {}
                    if self.settings_service:
                        current_settings = self.settings_service.get_plugin_settings(name)
                    
                    # If widget has a load_settings method, call it
                    if hasattr(settings_widget, 'load_settings') and callable(getattr(settings_widget, 'load_settings')):
                        settings_widget.load_settings(current_settings)

                    dialog = ui.create_dialog(
                        f"Configure {label}",
                        parent=self.dialog,
                        modal=True,
                    )
                    content = ui.create_column(parent=dialog, expand=True)
                    ui.add(content, settings_widget)
                    ui.add(content, ui.dialog_button_row(dialog))
                    ui.set_dialog_content(dialog, content)
                    ui.open_dialog(
                        dialog,
                        on_closed=lambda accepted: self._finish_configuration(
                            accepted,
                            name,
                            plugin_target,
                            settings_widget,
                        ),
                    )
                    return
            
            # Fallback to legacy methods for backward compatibility
            if hasattr(plugin_target, 'open_settings_dialog') and callable(getattr(plugin_target, 'open_settings_dialog')):
                plugin_target.open_settings_dialog(self.dialog)
                return
            if hasattr(plugin_target, 'get_configuration_widget') and callable(getattr(plugin_target, 'get_configuration_widget')):
                widget = plugin_target.get_configuration_widget(self.dialog)
                if widget:
                    dialog = ui.create_dialog(
                        f"Configure {label}",
                        parent=self.dialog,
                        modal=True,
                    )
                    content = ui.create_column(parent=dialog, expand=True)
                    ui.add(content, widget)
                    ui.add(
                        content,
                        ui.dialog_button_row(dialog, save_cancel=False),
                    )
                    ui.set_dialog_content(dialog, content)
                    ui.open_dialog(dialog)
                    return
            if hasattr(plugin_target, 'configure') and callable(getattr(plugin_target, 'configure')):
                plugin_target.configure(self.dialog)
                return
            
            self._info(
                "No Configuration",
                f"Plugin '{label}' has no configurable settings.",
            )
        except Exception as e:
            self._error(
                "Configuration Error",
                f"Failed to open configuration for '{label}':\n{e}",
            )

    def _finish_configuration(
        self,
        accepted: bool,
        name: str,
        plugin_target: Any,
        settings_widget: Any,
    ) -> None:
        """Persist settings after an asynchronously accepted content dialog."""
        if not accepted:
            return
        try:
            if not (
                hasattr(settings_widget, 'get_settings')
                and callable(getattr(settings_widget, 'get_settings'))
            ):
                return
            new_settings = settings_widget.get_settings()
            if self.settings_service:
                self.settings_service.save_plugin_settings(name, new_settings)
            if hasattr(plugin_target, 'on_settings_changed'):
                try:
                    plugin_target.on_settings_changed(new_settings)
                except Exception as exc:
                    logger.debug(
                        "Error calling on_settings_changed hook for %s: %s",
                        name,
                        exc,
                    )
        except Exception as exc:
            self._error(
                "Configuration Error",
                f"Failed to save configuration for '{self._plugin_label(name)}':\n{exc}",
            )

    def _warning(self, title: str, message: str) -> None:
        """Show a warning through the injected dialog presenter."""
        self.dialog_presenter.warning(title, message)

    def _confirm(self, title: str, message: str) -> bool:
        """Show a confirmation through the injected dialog presenter."""
        return self.dialog_presenter.confirm(title, message)

    def _info(self, title: str, message: str) -> None:
        """Show information through the injected dialog presenter."""
        self.dialog_presenter.info(title, message)

    def _error(self, title: str, message: str) -> None:
        """Show an error through the injected dialog presenter."""
        self.dialog_presenter.error(title, message)


__all__ = ['PluginManagementDialog']

