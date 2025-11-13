"""
Plugin management dialog for enabling, disabling, and configuring plugins.

This module provides a GUI interface for managing plugin lifecycle, including
enabling/disabling plugins, viewing plugin information, and configuring
plugin settings.
"""

from __future__ import annotations

import inspect
import os
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QMessageBox, QLineEdit, QComboBox, QSplitter, QWidget, QFormLayout,
    QTextEdit, QAbstractItemView, QMenu
)
from PySide6.QtCore import Signal, Qt, QPoint
from typing import Optional, List, Tuple, Any, Type
from ....plugins.base import plugin_registry, BaseTabPlugin


class PluginManagementDialog(QDialog):
    """Dialog for managing plugin lifecycle and configuration."""
    
    pluginToggled = Signal(str, bool)
    
    def __init__(self, parent: Optional[QWidget] = None, settings_service: Optional[Any] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plugin Management")
        self.resize(900, 560)
        self._all_plugins = []  # List of (name, plugin_class)
        self.settings_service = settings_service
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
        self.status_filter.addItems(["All Status", "Enabled", "Disabled"])
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
        form.addRow("Name:", self.details_name)
        form.addRow("Version:", self.details_version)
        form.addRow("Authors:", self.details_author)
        form.addRow("Type:", self.details_type)
        form.addRow("Requires Admin:", self.details_requires_admin)
        form.addRow("Platforms:", self.details_platforms)
        form.addRow("Module:", self.details_module)
        form.addRow("Min GUI Version:", self.details_min_gui_version)
        form.addRow("Required GUI Version:", self.details_required_gui_version)

        details_layout.addLayout(form)
        details_layout.addWidget(QLabel("Description:"))
        self.details_description = QTextEdit()
        self.details_description.setReadOnly(True)
        self.details_description.setFixedHeight(140)
        details_layout.addWidget(self.details_description)

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

    def load_plugins(self) -> None:
        """Load all plugins from the registry."""
        plugins = plugin_registry.get_all_plugins()
        self._all_plugins = list(plugins.items())
        self.apply_filters()

    def toggle_plugin(self, name: str, state: int) -> None:
        """Toggle plugin enabled/disabled state."""
        if state:
            plugin_registry.enable_plugin(name)
        else:
            plugin_registry.disable_plugin(name)
        self.pluginToggled.emit(name, bool(state))

    def reload_plugins(self) -> None:
        """Reload all plugins from the registry."""
        # Clear and re-discover plugins
        from ...services.plugin_service import discover_and_register_all_plugins
        plugin_registry.clear()
        # Use the comprehensive plugin discovery that handles both external and built-in plugins
        discover_and_register_all_plugins()
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
        for name, plugin_class in self._all_plugins:
            info = plugin_class.get_plugin_info()

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
            if status_sel == "Enabled" and not is_enabled:
                continue
            if status_sel == "Disabled" and is_enabled:
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

            # Enabled checkbox
            cb = QCheckBox()
            cb.setChecked(is_enabled)
            cb.stateChanged.connect(lambda state, n=name: self.toggle_plugin(n, state))
            self.table.setCellWidget(row, 0, cb)

            # Name
            self.table.setItem(row, 1, QTableWidgetItem(info['name']))
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
        plugin_class = plugin_registry.get_plugin(name)
        if not plugin_class:
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
        self.details_platforms.setText("-")
        self.details_module.setText("-")
        self.details_min_gui_version.setText("-")
        self.details_required_gui_version.setText("-")
        self.details_description.setPlainText("")
        self.configure_btn.setEnabled(False)

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
        plugin_registry.enable_plugin(name)
        # Call lifecycle hook
        plugin_class = plugin_registry.get_plugin(name)
        if plugin_class and hasattr(plugin_class, 'on_plugin_enabled'):
            try:
                plugin_class.on_plugin_enabled()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Error calling on_plugin_enabled hook for {name}: {e}")
        self.pluginToggled.emit(name, True)
        self.apply_filters()

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
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Error calling on_plugin_disabled hook for {name}: {e}")
        self.pluginToggled.emit(name, False)
        self.apply_filters()

    def enable_all(self) -> None:
        """Enable all plugins and call lifecycle hooks."""
        for name, _ in self._all_plugins:
            plugin_registry.enable_plugin(name)
            # Call lifecycle hook
            plugin_class = plugin_registry.get_plugin(name)
            if plugin_class and hasattr(plugin_class, 'on_plugin_enabled'):
                try:
                    plugin_class.on_plugin_enabled()
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Error calling on_plugin_enabled hook for {name}: {e}")
            self.pluginToggled.emit(name, True)
        self.apply_filters()

    def disable_all(self) -> None:
        """Disable all plugins and call lifecycle hooks."""
        for name, _ in self._all_plugins:
            plugin_registry.disable_plugin(name)
            # Call lifecycle hook
            plugin_class = plugin_registry.get_plugin(name)
            if plugin_class and hasattr(plugin_class, 'on_plugin_disabled'):
                try:
                    plugin_class.on_plugin_disabled()
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Error calling on_plugin_disabled hook for {name}: {e}")
            self.pluginToggled.emit(name, False)
        self.apply_filters()

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

