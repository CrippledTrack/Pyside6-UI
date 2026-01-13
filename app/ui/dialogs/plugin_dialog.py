"""
Plugin management dialog for enabling, disabling, and configuring plugins.

This module provides a GUI interface for managing plugin lifecycle, including
enabling/disabling plugins, viewing plugin information, and configuring
plugin settings.
"""

from __future__ import annotations

import inspect
import logging
import os
import sys
from typing import Optional, List, Tuple, Any, Type, Dict

from PySide6.QtCore import Signal, Qt, QPoint
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget
)

from ....plugin_system.base import plugin_registry, BaseTabPlugin

logger = logging.getLogger(__name__)


class PluginManagementDialog(QDialog):
    """Dialog for managing plugin lifecycle and configuration."""
    
    plugin_toggled = Signal(str, bool)  # Emitted when a plugin is toggled (name, enabled)
    
    def __init__(self, parent: Optional[QWidget] = None, settings_service: Optional[Any] = None, plugin_controller: Optional[Any] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plugin Management")
        self.resize(900, 560)
        self._all_plugins = []  # List of (name, plugin_class)
        self._rejected_plugins = {}  # Dict of name -> (plugin_class, reason)
        self.settings_service = settings_service
        self.plugin_controller = plugin_controller
        self.setup_ui()
        self.load_plugins()

    def setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Filters/Search bar
        filters_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, author, description...")
        self.search_input.textChanged.connect(self.apply_filters)

        self.type_filter = QComboBox()
        self.type_filter.addItems(["All Types", "Core", "External"])
        self.type_filter.currentIndexChanged.connect(self.apply_filters)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Status", "Enabled", "Disabled", "Incompatible"])
        self.status_filter.currentIndexChanged.connect(self.apply_filters)

        self.perm_filter = QComboBox()
        self.perm_filter.addItems(["All Permissions", "Requires Admin", "No Admin"])
        self.perm_filter.currentIndexChanged.connect(self.apply_filters)

        filters_layout.addWidget(QLabel("Search:"))
        filters_layout.addWidget(self.search_input, stretch=1)
        filters_layout.addWidget(QLabel("Type:"))
        filters_layout.addWidget(self.type_filter)
        filters_layout.addWidget(QLabel("Status:"))
        filters_layout.addWidget(self.status_filter)
        filters_layout.addWidget(QLabel("Permissions:"))
        filters_layout.addWidget(self.perm_filter)
        layout.addLayout(filters_layout)

        # Splitter with table (left) and details (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Table setup
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Enabled", "Name", "Version", "Authors", "Type", "Requires Admin"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_table_context_menu)
        table_layout.addWidget(self.table)

        splitter.addWidget(table_container)

        # Details panel
        details_container = QWidget()
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(8, 8, 8, 8)

        form = QFormLayout()
        self.details_name = QLabel("-")
        self.details_version = QLabel("-")
        self.details_author = QLabel("-")
        self.details_type = QLabel("-")
        self.details_requires_admin = QLabel("-")
        self.details_platforms = QLabel("-")
        self.details_module = QLabel("-")
        self.details_min_gui_version = QLabel("-")
        self.details_required_gui_version = QLabel("-")
        self.details_types = QLabel("-")  # Show plugin types
        form.addRow("Name:", self.details_name)
        form.addRow("Version:", self.details_version)
        form.addRow("Authors:", self.details_author)
        form.addRow("Type:", self.details_type)
        form.addRow("Types:", self.details_types)  # New row for types
        form.addRow("Requires Admin:", self.details_requires_admin)
        form.addRow("Platforms:", self.details_platforms)
        form.addRow("Module:", self.details_module)
        form.addRow("Min GUI Version:", self.details_min_gui_version)
        form.addRow("Required GUI Version:", self.details_required_gui_version)

        details_layout.addLayout(form)
        details_layout.addWidget(QLabel("Description:"))
        self.details_description = QTextEdit()
        self.details_description.setReadOnly(True)
        self.details_description.setFixedHeight(100)
        details_layout.addWidget(self.details_description)
        
        # Extension type toggles section
        extension_group = QGroupBox("Extension Types (toggle to enable/disable)")
        extension_layout = QHBoxLayout(extension_group)
        extension_layout.setContentsMargins(8, 4, 8, 4)
        
        self.ext_checkboxes: Dict[str, QCheckBox] = {}
        for ext_type in ["Tab", "Menu", "Toolbar", "Status", "Service"]:
            cb = QCheckBox(ext_type)
            cb.setChecked(True)  # Default enabled
            cb.setEnabled(False)  # Disabled until a plugin is selected
            cb.stateChanged.connect(lambda state, t=ext_type: self._on_extension_toggled(t, state))
            self.ext_checkboxes[ext_type] = cb
            extension_layout.addWidget(cb)
        extension_layout.addStretch()
        
        details_layout.addWidget(extension_group)

        # Action buttons for details
        action_layout = QHBoxLayout()
        self.enable_selected_btn = QPushButton("Enable Selected")
        self.enable_selected_btn.clicked.connect(self.enable_selected)
        self.disable_selected_btn = QPushButton("Disable Selected")
        self.disable_selected_btn.clicked.connect(self.disable_selected)
        self.configure_btn = QPushButton("Configure...")
        self.configure_btn.clicked.connect(self.configure_selected)
        action_layout.addWidget(self.enable_selected_btn)
        action_layout.addWidget(self.disable_selected_btn)
        action_layout.addStretch()
        action_layout.addWidget(self.configure_btn)
        details_layout.addLayout(action_layout)

        splitter.addWidget(details_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        # Bottom controls
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("")
        bottom_layout.addWidget(self.status_label)

        bottom_layout.addStretch()
        self.enable_all_btn = QPushButton("Enable All")
        self.enable_all_btn.clicked.connect(self.enable_all)
        self.disable_all_btn = QPushButton("Disable All")
        self.disable_all_btn.clicked.connect(self.disable_all)
        self.reload_btn = QPushButton("Reload Plugins")
        self.reload_btn.clicked.connect(self.reload_plugins)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(self.enable_all_btn)
        bottom_layout.addWidget(self.disable_all_btn)
        bottom_layout.addWidget(self.reload_btn)
        bottom_layout.addWidget(self.close_btn)
        layout.addLayout(bottom_layout)

    def _get_extension_types(self, plugin_class: type) -> str:
        """Get a string describing which extension interfaces the plugin implements."""
        extensions = []
        
        # Check for Tab extension (has create_widget method)
        if hasattr(plugin_class, 'create_widget'):
            extensions.append("Tab")
        
        # Check for Menu extension (has get_menu_items method)
        if hasattr(plugin_class, 'get_menu_items'):
            extensions.append("Menu")
        
        # Check for Status extension (has create_status_widget method)
        if hasattr(plugin_class, 'create_status_widget'):
            extensions.append("Status")
        
        # Check for Toolbar extension (has get_toolbar_actions method)
        if hasattr(plugin_class, 'get_toolbar_actions'):
            extensions.append("Toolbar")
        
        # Check for Service extension (has on_application_start OR get_event_subscriptions)
        # Events are grouped under Service for user simplicity
        has_service = hasattr(plugin_class, 'on_application_start')
        has_events = hasattr(plugin_class, 'get_event_subscriptions')
        if has_service or has_events:
            extensions.append("Service")
        
        # Check for Settings extension (has get_settings_widget method)
        # Note: Be careful as BaseTabPlugin also has this - only count if not default
        if hasattr(plugin_class, 'get_settings_widget'):
            method = getattr(plugin_class, 'get_settings_widget')
            # Check if it's overridden (not just inherited from base)
            from ....plugin_system.base import BaseTabPlugin
            base_method = getattr(BaseTabPlugin, 'get_settings_widget', None)
            if method is not base_method:
                extensions.append("Settings")
        
        return ", ".join(extensions) if extensions else ""

    def load_plugins(self) -> None:
        """Load all plugins from the registry, including rejected ones."""
        plugins = plugin_registry.get_all_plugins()
        self._all_plugins = list(plugins.items())
        # Also load rejected (version-incompatible) plugins
        self._rejected_plugins = plugin_registry.get_rejected_plugins()
        self.apply_filters()

    def toggle_plugin(self, name: str, state: int) -> None:
        """Toggle plugin enabled/disabled state.
        
        Only emits the signal - the actual enable/disable is handled by
        PluginController.toggle_plugin() which also handles dynamic
        extension integration.
        """
        # Don't call registry directly - let the controller handle it
        # This ensures dynamic extension integration runs for new plugins
        self.plugin_toggled.emit(name, bool(state))
        
        # If this is the currently selected plugin, refresh the details panel
        # to update the extension checkboxes (grey out if disabled)
        if name == self.get_selected_plugin_name():
            self.on_selection_changed()
    
    def _force_enable_plugin(self, name: str, state: int) -> None:
        """Force-enable a version-incompatible plugin."""
        if not state:
            # Being disabled - let the controller handle it via signal
            self.plugin_toggled.emit(name, False)
            
            # If this is the currently selected plugin, refresh the details panel
            if name == self.get_selected_plugin_name():
                self.on_selection_changed()
            return
        
        # Show warning before force-enabling
        result = QMessageBox.warning(
            self,
            "Force Enable Incompatible Plugin",
            f"Plugin '{name}' is marked as incompatible:\n\n"
            f"{self._rejected_plugins.get(name, ('', 'Unknown reason'))[1]}\n\n"
            "Force-enabling may cause crashes or unexpected behavior.\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if result != QMessageBox.StandardButton.Yes:
            # User cancelled - uncheck the checkbox
            self.apply_filters()
            return
        
        # Force-register the plugin
        if name in self._rejected_plugins:
            plugin_class, reason = self._rejected_plugins[name]
            # Add to main registry (bypass version check)
            plugin_registry._plugins[name] = plugin_class
            plugin_registry._external_plugins[name] = plugin_class
            # Categorize by interface so extension methods work properly
            plugin_registry._categorize_plugin_by_interface(name, plugin_class)
            # Enable it
            plugin_registry.enable_plugin(name)
            self.plugin_toggled.emit(name, True)
            # Reload to update UI
            self.load_plugins()

    def reload_plugins(self) -> None:
        """Reload all plugins from the registry."""
        # Clear and re-discover plugins
        # from ...services.plugin_service import discover_and_register_all_plugins
        plugin_registry.clear()
        # Use the comprehensive plugin discovery from the service
        if self.plugin_controller and self.plugin_controller.plugin_service:
            self.plugin_controller.plugin_service.discover_and_register_all_plugins()
        QMessageBox.information(self, "Plugins Reloaded", "Plugins have been reloaded.")
        self.load_plugins()

    def apply_filters(self) -> None:
        search_text = self.search_input.text().strip().lower()
        type_sel = self.type_filter.currentText()
        status_sel = self.status_filter.currentText()
        perm_sel = self.perm_filter.currentText()

        # Preserve current selection
        selected_name = self.get_selected_plugin_name()

        filtered = []
        core_names = set(plugin_registry.get_core_plugins().keys())
        
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
            is_enabled = plugin_registry.is_enabled(name)
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
        if selected_name:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 1)
                if item and item.text() == selected_name:
                    self.table.selectRow(row)
                    break
        # Update details/status if nothing selected
        if self.table.currentRow() == -1 and self.table.rowCount() > 0:
            self.table.selectRow(0)

        self.update_status_label()

    def populate_table(self, data: List[Tuple[str, Type[BaseTabPlugin]]]) -> None:
        self.table.setRowCount(len(data))
        core_names = set(plugin_registry.get_core_plugins().keys())
        for row, (name, plugin_class) in enumerate(data):
            info = plugin_class.get_plugin_info()
            is_enabled = plugin_registry.is_enabled(name)
            is_core = name in core_names
            is_rejected = name in self._rejected_plugins

            # Enabled checkbox (with incompatibility indicator for rejected plugins)
            if is_rejected:
                # Create container widget with checkbox + warning label
                container = QWidget()
                container.setStyleSheet("background-color: transparent;")
                container_layout = QHBoxLayout(container)
                container_layout.setContentsMargins(4, 0, 4, 0)
                container_layout.setSpacing(4)
                
                cb = QCheckBox()
                rejection_reason = self._rejected_plugins[name][1]
                
                # Allow force-enabling incompatible plugins
                is_loaded = name in dict(self._all_plugins)
                cb.setChecked(is_enabled and is_loaded)  # Only check if actually loaded
                cb.setEnabled(True)   # But can be enabled
                cb.setToolTip(f"⚠ Incompatible: {rejection_reason}\nClick to force-enable anyway")
                cb.stateChanged.connect(lambda state, n=name: self._force_enable_plugin(n, state))
                container_layout.addWidget(cb)
                
                # Add warning label
                warn_label = QLabel("⚠")
                warn_label.setToolTip(f"Incompatible: {rejection_reason}")
                warn_label.setStyleSheet("color: #FFA500; font-weight: bold;")  # Orange warning
                container_layout.addWidget(warn_label)
                container_layout.addStretch()
                
                self.table.setCellWidget(row, 0, container)
            else:
                cb = QCheckBox()
                cb.setChecked(is_enabled)
                cb.stateChanged.connect(lambda state, n=name: self.toggle_plugin(n, state))
                self.table.setCellWidget(row, 0, cb)

            # Name - show in italic/gray if rejected
            name_item = QTableWidgetItem(info['name'])
            if is_rejected:
                name_item.setToolTip(f"Incompatible: {self._rejected_plugins[name][1]}")
                font = name_item.font()
                font.setItalic(True)
                name_item.setFont(font)
            self.table.setItem(row, 1, name_item)
            # Version
            self.table.setItem(row, 2, QTableWidgetItem(str(info['version'])))
            # Authors
            self.table.setItem(row, 3, QTableWidgetItem(info.get('author', '')))
            # Type
            self.table.setItem(row, 4, QTableWidgetItem("Core" if is_core else "External"))
            # Requires Admin
            self.table.setItem(row, 5, QTableWidgetItem("Yes" if info.get('requires_admin') else "No"))

    def on_selection_changed(self) -> None:
        name = self.get_selected_plugin_name()
        if not name:
            self.clear_details()
            return
        
        # Try to get plugin from registry first, then from rejected plugins
        plugin_class = plugin_registry.get_plugin(name)
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
        self.details_name.setText(info['name'])
        self.details_version.setText(str(info['version']))
        authors_list = info.get('authors') or []
        authors_text = ", ".join(authors_list) if authors_list else info.get('author', '')
        self.details_author.setText(authors_text)
        self.details_type.setText("Core" if name in plugin_registry.get_core_plugins() else "External")
        self.details_platforms.setText(', '.join(info['supported_platforms']))
        self.details_requires_admin.setText("Yes" if info.get('requires_admin') else "No")
        self.details_module.setText(plugin_class.__module__)
        self.details_min_gui_version.setText(info.get('min_gui_version') or "-")
        self.details_required_gui_version.setText(info.get('required_gui_version') or "-")
        self.details_description.setPlainText(info.get('description', ''))
        
        # Detect plugin types
        types_str = self._get_extension_types(plugin_class)
        self.details_types.setText(types_str if types_str else "Tab only")
        
        # Check if plugin is enabled
        plugin_is_enabled = plugin_registry.is_enabled(name)
        
        # Update extension type checkboxes
        detected_types = types_str.split(", ") if types_str else []
        for ext_type, cb in self.ext_checkboxes.items():
            has_extension = ext_type in detected_types
            # Only enable checkbox if plugin is enabled AND has this extension type
            cb.setEnabled(has_extension and plugin_is_enabled)
            
            if has_extension and self.settings_service:
                # Load saved state from settings
                is_enabled = self.settings_service.is_extension_enabled(name, ext_type)
                cb.blockSignals(True)  # Prevent triggering handler during load
                # If plugin is disabled, visually uncheck extensions (even if enabled in settings)
                if not plugin_is_enabled:
                    cb.setChecked(False)
                else:
                    cb.setChecked(is_enabled)
                cb.blockSignals(False)
            else:
                cb.blockSignals(True)
                # If disabled or no settings, uncheck/default based on existence
                if not plugin_is_enabled:
                    cb.setChecked(False)
                else:
                    cb.setChecked(has_extension)
                cb.blockSignals(False)

        # Configure button availability
        has_config = any([
            hasattr(plugin_class, 'get_settings_widget') and callable(getattr(plugin_class, 'get_settings_widget', None)),
            hasattr(plugin_class, 'open_settings_dialog'),
            hasattr(plugin_class, 'get_configuration_widget'),
            hasattr(plugin_class, 'configure')
        ])
        self.configure_btn.setEnabled(has_config)

    def clear_details(self) -> None:
        self.details_name.setText("-")
        self.details_version.setText("-")
        self.details_author.setText("-")
        self.details_type.setText("-")
        self.details_types.setText("-")
        self.details_requires_admin.setText("-")
        self.details_platforms.setText("-")
        self.details_module.setText("-")
        self.details_min_gui_version.setText("-")
        self.details_required_gui_version.setText("-")
        self.details_description.setPlainText("")
        self.configure_btn.setEnabled(False)
        
        # Reset extension checkboxes
        for cb in self.ext_checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.setEnabled(False)
            cb.blockSignals(False)
    
    def _on_extension_toggled(self, extension_type: str, state: int) -> None:
        """Handle extension type checkbox toggle.
        
        Args:
            extension_type: The extension type (e.g., "Tab", "Menu", "Toolbar")
            state: Qt checkbox state (0=unchecked, 2=checked)
        """
        name = self.get_selected_plugin_name()
        if not name or not self.settings_service:
            return
        
        enabled = (state == Qt.CheckState.Checked.value)
        self.settings_service.set_extension_enabled(name, extension_type, enabled)
        
        # Service checkbox also controls Events (they're grouped for user simplicity)
        if extension_type == "Service":
            self.settings_service.set_extension_enabled(name, "Events", enabled)
        
        # Refresh extensions to apply the change
        if self.plugin_controller:
            self.plugin_controller.refresh_plugin_extensions(name)

    def update_status_label(self) -> None:
        total = len(self._all_plugins)
        shown = self.table.rowCount()
        enabled_count = sum(1 for name, _ in self._all_plugins if plugin_registry.is_enabled(name))
        self.status_label.setText(f"Showing {shown}/{total} plugins  |  Enabled: {enabled_count}")

    def get_selected_plugin_name(self) -> Optional[str]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 1)
        return item.text() if item else None

    def enable_selected(self) -> None:
        """Enable the currently selected plugin and call lifecycle hook."""
        name = self.get_selected_plugin_name()
        if not name:
            return
        # Only enable if not already enabled to avoid duplicates
        if not plugin_registry.is_enabled(name):
            plugin_registry.enable_plugin(name)
            # Call lifecycle hook
            plugin_class = plugin_registry.get_plugin(name)
            if plugin_class and hasattr(plugin_class, 'on_plugin_enabled'):
                try:
                    plugin_class.on_plugin_enabled()
                except Exception as e:
                    logger.debug(f"Error calling on_plugin_enabled hook for {name}: {e}")
            self.plugin_toggled.emit(name, True)
        self.apply_filters()
        self.on_selection_changed()  # Refresh extension checkboxes

    def disable_selected(self) -> None:
        """Disable the currently selected plugin and call lifecycle hook."""
        name = self.get_selected_plugin_name()
        if not name:
            return
        plugin_registry.disable_plugin(name)
        # Call lifecycle hook
        plugin_class = plugin_registry.get_plugin(name)
        if plugin_class and hasattr(plugin_class, 'on_plugin_disabled'):
            try:
                plugin_class.on_plugin_disabled()
            except Exception as e:
                logger.debug(f"Error calling on_plugin_disabled hook for {name}: {e}")
        self.plugin_toggled.emit(name, False)
        self.apply_filters()
        self.on_selection_changed()  # Refresh extension checkboxes

    def enable_all(self) -> None:
        """Enable all plugins and call lifecycle hooks."""
        for name, _ in self._all_plugins:
            # Only enable if not already enabled to avoid duplicates
            if not plugin_registry.is_enabled(name):
                plugin_registry.enable_plugin(name)
                # Call lifecycle hook
                plugin_class = plugin_registry.get_plugin(name)
                if plugin_class and hasattr(plugin_class, 'on_plugin_enabled'):
                    try:
                        plugin_class.on_plugin_enabled()
                    except Exception as e:
                        logger.debug(f"Error calling on_plugin_enabled hook for {name}: {e}")
                self.plugin_toggled.emit(name, True)
        self.apply_filters()
        self.on_selection_changed()  # Refresh extension checkboxes

    def disable_all(self) -> None:
        """Disable all plugins and call lifecycle hooks."""
        for name, _ in self._all_plugins:
            # Only process if actually enabled
            if not plugin_registry.is_enabled(name):
                continue
            # Emit signal FIRST so plugin controller can remove extensions
            # before the plugin is disabled in the registry
            self.plugin_toggled.emit(name, False)
            # Call lifecycle hook
            plugin_class = plugin_registry.get_plugin(name)
            if plugin_class and hasattr(plugin_class, 'on_plugin_disabled'):
                try:
                    plugin_class.on_plugin_disabled()
                except Exception as e:
                    logger.debug(f"Error calling on_plugin_disabled hook for {name}: {e}")
        self.apply_filters()
        self.on_selection_changed()  # Refresh extension checkboxes

    def on_table_context_menu(self, pos: QPoint) -> None:
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        self.table.selectRow(row)
        name = self.get_selected_plugin_name()
        if not name:
            return
        plugin_class = plugin_registry.get_plugin(name)
        if not plugin_class:
            return
        info = plugin_class.get_plugin_info()
        is_enabled = plugin_registry.is_enabled(name)

        menu = QMenu(self)
        toggle_action = menu.addAction("Disable" if is_enabled else "Enable")
        configure_action = menu.addAction("Configure...")
        configure_action.setEnabled(any([
            hasattr(plugin_class, 'get_settings_widget') and callable(getattr(plugin_class, 'get_settings_widget', None)),
            hasattr(plugin_class, 'open_settings_dialog'),
            hasattr(plugin_class, 'get_configuration_widget'),
            hasattr(plugin_class, 'configure')
        ]))
        menu.addSeparator()
        copy_name_action = menu.addAction("Copy Name")
        copy_info_action = menu.addAction("Copy Full Info")

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == toggle_action:
            if is_enabled:
                self.disable_selected()
            else:
                self.enable_selected()
        elif chosen == configure_action:
            self.configure_selected()
        elif chosen == copy_name_action:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(name)
        elif chosen == copy_info_action:
            from PySide6.QtWidgets import QApplication
            lines = [
                f"Name: {info['name']}",
                f"Version: {info['version']}",
                f"Author: {info['author']}",
                f"Type: {'Core' if name in plugin_registry.get_core_plugins() else 'External'}",
                f"Requires Admin: {'Yes' if info.get('requires_admin') else 'No'}",
                f"Compatible: {'Yes' if info.get('compatible', True) else 'No'}",
                f"Platforms: {', '.join(info['supported_platforms'])}",
                f"Module: {plugin_class.__module__}",
                f"Description: {info.get('description', '')}",
            ]
            QApplication.clipboard().setText("\n".join(lines))
        # Removed "Open Module Location" from context menu since Module column was removed

    def configure_selected(self) -> None:
        """Configure the selected plugin using get_settings_widget() method."""
        name = self.get_selected_plugin_name()
        if not name:
            return
        plugin_class = plugin_registry.get_plugin(name)
        if not plugin_class:
            return
        
        try:
            # Try new get_settings_widget() method first
            if hasattr(plugin_class, 'get_settings_widget') and callable(getattr(plugin_class, 'get_settings_widget')):
                settings_widget = plugin_class.get_settings_widget(self)
                if settings_widget:
                    # Load current settings
                    current_settings = {}
                    if self.settings_service:
                        current_settings = self.settings_service.get_plugin_settings(name)
                    
                    # If widget has a load_settings method, call it
                    if hasattr(settings_widget, 'load_settings') and callable(getattr(settings_widget, 'load_settings')):
                        settings_widget.load_settings(current_settings)
                    
                    # Create and show dialog
                    dlg = QDialog(self)
                    dlg.setWindowTitle(f"Configure {name}")
                    layout = QVBoxLayout(dlg)
                    layout.addWidget(settings_widget)
                    
                    # Add buttons
                    button_layout = QHBoxLayout()
                    button_layout.addStretch()
                    cancel_btn = QPushButton("Cancel")
                    cancel_btn.clicked.connect(dlg.reject)
                    save_btn = QPushButton("Save")
                    save_btn.clicked.connect(dlg.accept)
                    save_btn.setDefault(True)
                    button_layout.addWidget(cancel_btn)
                    button_layout.addWidget(save_btn)
                    layout.addLayout(button_layout)
                    
                    dlg.resize(480, 360)
                    if dlg.exec() == QDialog.DialogCode.Accepted:
                        # Extract settings from widget
                        if hasattr(settings_widget, 'get_settings') and callable(getattr(settings_widget, 'get_settings')):
                            new_settings = settings_widget.get_settings()
                            # Save settings
                            if self.settings_service:
                                self.settings_service.save_plugin_settings(name, new_settings)
                            # Call settings changed hook
                            if hasattr(plugin_class, 'on_settings_changed'):
                                try:
                                    plugin_class.on_settings_changed(new_settings)
                                except Exception as e:
                                    import logging
                                    logger = logging.getLogger(__name__)
                                    logger.debug(f"Error calling on_settings_changed hook for {name}: {e}")
                    return
            
            # Fallback to legacy methods for backward compatibility
            if hasattr(plugin_class, 'open_settings_dialog') and callable(getattr(plugin_class, 'open_settings_dialog')):
                plugin_class.open_settings_dialog(self)
                return
            if hasattr(plugin_class, 'get_configuration_widget') and callable(getattr(plugin_class, 'get_configuration_widget')):
                widget = plugin_class.get_configuration_widget(self)
                if widget:
                    dlg = QDialog(self)
                    dlg.setWindowTitle(f"Configure {name}")
                    v = QVBoxLayout(dlg)
                    v.addWidget(widget)
                    buttons = QHBoxLayout()
                    close_btn = QPushButton("Close")
                    close_btn.clicked.connect(dlg.accept)
                    buttons.addStretch()
                    buttons.addWidget(close_btn)
                    v.addLayout(buttons)
                    dlg.resize(480, 360)
                    dlg.exec()
                    return
            if hasattr(plugin_class, 'configure') and callable(getattr(plugin_class, 'configure')):
                plugin_class.configure(self)
                return
            
            QMessageBox.information(self, "No Configuration", f"Plugin '{name}' has no configurable settings.")
        except Exception as e:
            QMessageBox.critical(self, "Configuration Error", f"Failed to open configuration for '{name}':\n{e}")

    def open_module_location(self, plugin_class: Type[BaseTabPlugin]) -> None:
        try:
            path = inspect.getsourcefile(plugin_class)
            if not path:
                module = sys.modules.get(plugin_class.__module__)
                path = getattr(module, '__file__', None)
            if not path:
                QMessageBox.warning(self, "Open Location", "Could not determine module file path.")
                return
            folder = os.path.dirname(os.path.abspath(path))
            if sys.platform.startswith('win'):
                os.startfile(folder)  # type: ignore
            elif sys.platform.startswith('darwin'):
                import subprocess
                subprocess.Popen(['open', folder])
            else:
                import subprocess
                subprocess.Popen(['xdg-open', folder])
        except Exception as e:
            QMessageBox.critical(self, "Open Location", f"Failed to open location: {e}")


__all__ = ['PluginManagementDialog']

