"""
Main window implementation for the GUI application.

This module provides the main application window, including tab management,
plugin loading, menu bar, and user interface components.
"""

from __future__ import annotations

import logging
import platform
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..services.settings_service import SettingsService

from PySide6.QtCore import QPoint, QTimer, Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...plugins import plugin_registry
from ...plugins.plugin_management import PluginManagementDialog
from ...themes.theme_dialog import ThemeDialog
from ...themes.theme_manager import ThemeManager
from ..services.plugin_service import discover_and_register_all_plugins
from ..ui.toast_notification import ToastManager
from ..ui.widgets.admin_required_placeholder import AdminRequiredPlaceholder
from ..ui.widgets.error_placeholder import ErrorPlaceholder
from ..ui.widgets.loading_placeholder import LoadingPlaceholder
from ..utils.admin import needs_admin_for_plugin
from ..utils.display_utils import build_title, build_version_details
from ..utils.imports import get_platforms_constants
from ..utils.shortcuts import ShortcutManager

# Import platform constants using the utility function
constants = get_platforms_constants()
REQUIRE_ADMIN_BY_DEFAULT = constants.REQUIRE_ADMIN_BY_DEFAULT
SUPPORTED_PLATFORMS = constants.SUPPORTED_PLATFORMS
VERSION = constants.VERSION
VERSION_INFO = constants.VERSION_INFO
VERSION_NAME = constants.VERSION_NAME

CURRENT_PLATFORM = platform.system().lower()

try:
    if CURRENT_PLATFORM == "windows":
        from ..utils.elevation_windows import is_admin, run_as_admin
    elif CURRENT_PLATFORM == "linux":
        from ..utils.elevation_linux import get_sudo_status, is_admin
    else:  # pragma: no cover - unsupported platforms
        raise RuntimeError(f"Unsupported platform: {CURRENT_PLATFORM}")
except Exception as e:  # pragma: no cover - import-time platform errors
    raise

logger = logging.getLogger(__name__)


class TabLoaderThread(QThread):
    finished = Signal()
    error = Signal(str)
    add_tab = Signal(str, object)

    def __init__(self, parent: Optional[QWidget] = None, settings_service: Optional["SettingsService"] = None) -> None:
        super().__init__(parent)
        self.setObjectName("TabLoaderThread")
        self.tab_widget: Optional[QTabWidget] = None
        self.settings_service = settings_service

    def set_tab_widget(self, tab_widget: QTabWidget) -> None:
        self.tab_widget = tab_widget

    def run(self) -> None:
        try:
            self.discover_and_register_plugins()
            self._load_plugin_states()
            self._emit_enabled_plugins()
            self.finished.emit()
        except Exception as e:  # pragma: no cover - runtime error path
            logger.error(f"Error in TabLoaderThread: {e}")
            self.error.emit(str(e))

    def _load_plugin_states(self) -> None:
        """Load and apply saved plugin states from settings."""
        if not self.settings_service:
            return

        try:
            saved_disabled = self.settings_service.get_disabled_plugins()
            if saved_disabled:
                self._apply_user_disabled_plugins(saved_disabled)
            else:
                self._handle_first_run()
        except Exception as e:
            logger.warning(f"Failed to load saved plugin states: {e}")

    def _apply_user_disabled_plugins(self, disabled_plugins: List[str]) -> None:
        """Apply user-disabled plugins from settings."""
        logger.info(f"Loading saved user-disabled plugins: {disabled_plugins}")
        for plugin_name in disabled_plugins:
            if plugin_registry.get_plugin(plugin_name):
                plugin_registry.disable_plugin(plugin_name)
                logger.debug(f"Applied user preference: {plugin_name} disabled")

    def _handle_first_run(self) -> None:
        """Handle first run scenario - log defaults and initialize empty disabled list."""
        logger.info("First run detected, applying default plugin states (disabled_by_default flags)")
        # Log default states for information
        enabled_by_default = [name for name in plugin_registry.list_plugin_names() 
                            if plugin_registry.is_enabled(name)]
        disabled_by_default = [name for name in plugin_registry.list_plugin_names() 
                              if not plugin_registry.is_enabled(name)]
        logger.info(f"Default plugin states: {len(enabled_by_default)} enabled, "
                   f"{len(disabled_by_default)} disabled by default")
        if disabled_by_default:
            logger.info(f"Disabled by default: {', '.join(disabled_by_default)}")
        
        # Initialize empty disabled list (user hasn't disabled anything yet)
        if self.settings_service:
            self.settings_service.save_disabled_plugins([])

    def _emit_enabled_plugins(self) -> None:
        """Emit signals for all enabled plugins."""
        enabled_plugins = plugin_registry.get_enabled_plugins()
        for tab_name, plugin_class in enabled_plugins.items():
            self.add_tab.emit(tab_name, plugin_class)

    def discover_and_register_plugins(self) -> None:
        discover_and_register_all_plugins()


class MainWindow(QMainWindow):
    def __init__(self, theme_manager: Optional[ThemeManager] = None, settings_service: Optional["SettingsService"] = None) -> None:
        super().__init__()
        logger.info(f"Initializing MainWindow for {VERSION_NAME} v{VERSION} on {CURRENT_PLATFORM}")
        self.settings_service = settings_service
        self.theme_manager = theme_manager
        self.loaded_tabs: Dict[str, Dict[str, Any]] = {}
        self.is_loading_tab = False
        self._status_timer: Optional[QTimer] = None

        self._setup_admin_status()
        self.setWindowTitle(f"{VERSION_NAME} v{VERSION} ({CURRENT_PLATFORM.capitalize()})")
        self._setup_window_geometry()
        self._setup_ui_components()
        self._setup_status_bar()
        self.setup_toast_manager()
        self.setup_shortcuts()
        QApplication.processEvents()
        self._start_tab_loader()
        self._setup_menu_bar()
        self.update_window_title()
        self.setup_tooltips()

    def _setup_admin_status(self) -> None:
        """Handle all admin/elevation logic for the current platform."""
        if CURRENT_PLATFORM == "windows":
            self._check_windows_admin_status()
        elif CURRENT_PLATFORM == "linux":
            self._check_linux_admin_status()

    def _check_windows_admin_status(self) -> None:
        """Check and handle Windows admin status."""
        self.is_admin = is_admin()
        if self.is_admin:
            logger.info("Application running with admin privileges")
            return

        if REQUIRE_ADMIN_BY_DEFAULT:
            try:
                logger.warning("Attempting to restart with elevated rights...")
                run_as_admin()
            except Exception as e:
                logger.warning(f"Elevation denied or failed ({e}); continuing without admin.")
            self.is_admin = is_admin()
            if not self.is_admin:
                logger.info("Continuing without admin privileges. Some operations will be disabled until elevated.")
        else:
            logger.info("Running without admin privileges by default. Some operations will be disabled until elevated.")

    def _check_linux_admin_status(self) -> None:
        """Check and handle Linux admin status."""
        self.sudo_status = get_sudo_status()
        self.is_admin = self.sudo_status["is_admin"]
        if self.is_admin:
            logger.info("Application running with admin/root privileges")
        else:
            logger.info(f"Application running as user '{self.sudo_status['current_user']}'")
            if self.sudo_status["sudo_available"]:
                logger.info("Sudo is available - operations requiring root will prompt for password")
            else:
                logger.warning("Sudo not available - some operations may not work")

    def _setup_window_geometry(self) -> None:
        """Restore window size and state from settings."""
        if not self.settings_service:
            return

        geom = self.settings_service.get_window_geometry()
        self.resize(geom.width, geom.height)
        if geom.maximized:
            self.showMaximized()

    def _setup_ui_components(self) -> None:
        """Create and configure all UI widgets and layouts."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)

        self.loading_widget = QWidget()
        self.loading_widget.setObjectName("loadingWidget")
        layout.addWidget(self.loading_widget)

        self.tab_widget = QTabWidget()
        self.tab_widget.hide()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.tab_widget.setMovable(True)
        self.tab_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_widget.customContextMenuRequested.connect(self.show_tab_context_menu)
        layout.addWidget(self.tab_widget)

    def _start_tab_loader(self) -> None:
        """Configure and start the tab loading thread."""
        self.tab_loader = TabLoaderThread(settings_service=self.settings_service)
        self.tab_loader.set_tab_widget(self.tab_widget)
        self.tab_loader.finished.connect(self.on_tabs_loaded)
        self.tab_loader.error.connect(self.on_tab_load_error)
        self.tab_loader.add_tab.connect(self.add_tab)
        self.tab_loader.start()

    def _setup_status_bar(self) -> None:
        """Create and configure the status bar."""
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        # Make status bar smaller
        self.status_bar.setMaximumHeight(20)
    
    def show_status(self, message: str, timeout: int = 0) -> None:
        """
        Show a status message in the status bar.
        
        Args:
            message: Status message to display
            timeout: Timeout in milliseconds (0 = permanent, clears on next show_status call)
        """
        # Clear any existing timer
        if self._status_timer:
            self._status_timer.stop()
            self._status_timer.deleteLater()
            self._status_timer = None
        
        # Show the message
        if timeout > 0:
            self.status_bar.showMessage(message, timeout)
            # Set up timer to clear after timeout
            self._status_timer = QTimer(self)
            self._status_timer.setSingleShot(True)
            self._status_timer.timeout.connect(self.clear_status)
            self._status_timer.start(timeout)
        else:
            self.status_bar.showMessage(message)
    
    def clear_status(self) -> None:
        """Clear the status bar message."""
        # Clear any existing timer
        if self._status_timer:
            self._status_timer.stop()
            self._status_timer.deleteLater()
            self._status_timer = None
        self.status_bar.clearMessage()

    def _setup_menu_bar(self) -> None:
        """Create menu bar and all menu items."""
        self.menu_bar = QMenuBar(self)
        self.setMenuBar(self.menu_bar)
        self._create_settings_menu()
        self._create_admin_menu()

    def _create_settings_menu(self) -> None:
        """Create the Settings menu with plugin and theme options."""
        self.settings_menu = QMenu("Settings", self)
        self.menu_bar.addMenu(self.settings_menu)

        self.manage_plugins_action = QAction("Manage Plugins...", self)
        self.settings_menu.addAction(self.manage_plugins_action)
        self.manage_plugins_action.triggered.connect(self.open_plugin_management_dialog)

        self.select_theme_action = QAction("Select Theme...", self)
        self.settings_menu.addAction(self.select_theme_action)
        self.select_theme_action.triggered.connect(self.open_theme_dialog)

        self.settings_menu.addSeparator()

    def _create_admin_menu(self) -> None:
        """Create the Admin menu if needed (Windows only, when not elevated)."""
        if CURRENT_PLATFORM == "windows" and not getattr(self, "is_admin", False):
            self.admin_menu = QMenu("Admin", self)
            self.menu_bar.addMenu(self.admin_menu)
            self.restart_admin_action = QAction("Restart as Administrator", self)
            self.restart_admin_action.triggered.connect(self.restart_as_admin)
            self.admin_menu.addAction(self.restart_admin_action)

    @Slot(str, object)
    def add_tab(self, tab_name: str, plugin_class: object) -> None:
        placeholder = LoadingPlaceholder(tab_name)
        self.loaded_tabs[tab_name] = {
            "plugin_class": plugin_class,
            "instance": None,
            "placeholder": placeholder,
        }
        self.tab_widget.addTab(placeholder, tab_name)
        self.update_window_title()

    def on_tab_changed(self, index: int) -> None:
        if self.is_loading_tab or index < 0:
            return
        
        # Call deactivation hook for previously active tab
        previous_index = getattr(self, '_previous_tab_index', -1)
        if previous_index >= 0 and previous_index != index:
            try:
                prev_tab_name = self.tab_widget.tabText(previous_index)
                prev_tab_info = self.loaded_tabs.get(prev_tab_name)
                if prev_tab_info and prev_tab_info["instance"]:
                    plugin_class = prev_tab_info["plugin_class"]
                    if hasattr(plugin_class, 'on_tab_deactivated'):
                        plugin_class.on_tab_deactivated(prev_tab_info["instance"])
            except Exception as e:
                logger.debug(f"Error calling deactivation hook: {e}")
        
        try:
            self.is_loading_tab = True
            tab_name = self.tab_widget.tabText(index)
            tab_info = self.loaded_tabs.get(tab_name)
            if tab_info and not tab_info["instance"]:
                plugin_class = tab_info["plugin_class"]
                requires_admin = bool(getattr(plugin_class, "requires_admin", False))
                if needs_admin_for_plugin(CURRENT_PLATFORM == "windows", requires_admin, getattr(self, "is_admin", False)):
                    # Show admin required placeholder (works for both Windows and Linux)
                    admin_widget = AdminRequiredPlaceholder(tab_name)
                    admin_widget.restartRequested.connect(self.restart_as_admin)
                    tab_info["instance"] = admin_widget
                else:
                    tab_info["instance"] = plugin_class.create_widget(self.tab_widget)
                self.tab_widget.removeTab(index)
                self.tab_widget.insertTab(index, tab_info["instance"], tab_name)
                self.tab_widget.setCurrentIndex(index)
                logger.info(f"Lazy loaded plugin tab: {tab_name}")
            
            # Call activation hook for newly active tab
            if tab_info and tab_info["instance"]:
                plugin_class = tab_info["plugin_class"]
                if hasattr(plugin_class, 'on_tab_activated'):
                    try:
                        plugin_class.on_tab_activated(tab_info["instance"])
                    except Exception as e:
                        logger.debug(f"Error calling activation hook for {tab_name}: {e}")
        except Exception as e:
            logger.error(f"Error loading tab {tab_name}: {e}")
            # Replace current tab content with an error placeholder
            error_widget = ErrorPlaceholder(tab_name, str(e))
            self.tab_widget.removeTab(index)
            self.tab_widget.insertTab(index, error_widget, tab_name)
            self.tab_widget.setCurrentIndex(index)
        finally:
            self.is_loading_tab = False
            self._previous_tab_index = index
            self.update_window_title()

    def update_window_title(self) -> None:
        base_title = f"{VERSION_NAME} v{VERSION} ({CURRENT_PLATFORM.capitalize()})"
        try:
            current_index = self.tab_widget.currentIndex()
            if current_index is None or current_index < 0:
                self.setWindowTitle(build_title(VERSION_NAME, VERSION, CURRENT_PLATFORM))
                return
            tab_name = self.tab_widget.tabText(current_index)
            plugin_version = None
            tab_info = self.loaded_tabs.get(tab_name)
            if tab_info:
                plugin_class = tab_info.get("plugin_class")
                if plugin_class is not None:
                    plugin_version = getattr(plugin_class, "plugin_version", None)
            self.setWindowTitle(
                build_title(VERSION_NAME, VERSION, CURRENT_PLATFORM, tab_name, plugin_version)
            )
        except Exception:
            self.setWindowTitle(build_title(VERSION_NAME, VERSION, CURRENT_PLATFORM))
    

    def on_tabs_loaded(self) -> None:
        self.loading_widget.hide()
        self.tab_widget.show()
        logger.info("All tabs loaded successfully")
        self.update_window_title()

    def on_tab_load_error(self, error_msg: str) -> None:
        self.loading_widget.hide()
        self.tab_widget.show()
        logger.error(f"Error loading tabs: {error_msg}")
        QMessageBox.critical(self, "Error", f"Failed to load tabs: {error_msg}")

    def get_version_details(self) -> Dict[str, str]:
        return build_version_details(VERSION_INFO, CURRENT_PLATFORM)

    def prompt_for_admin_operation(self, operation_description: str) -> bool:
        if CURRENT_PLATFORM == "windows":
            if self.is_admin:
                return True
            QMessageBox.warning(
                self,
                "Admin Privileges Required",
                f"{operation_description} requires administrator privileges.\n"
                "Please restart the application as administrator.",
            )
            return False
        elif CURRENT_PLATFORM == "linux":
            if self.is_admin:
                return True
            if not self.sudo_status["sudo_available"]:
                QMessageBox.warning(
                    self,
                    "Admin Privileges Required",
                    f"{operation_description} requires root privileges, but sudo is not available.\n"
                    "Please run the application as root or install sudo.",
                )
                return False
            reply = QMessageBox.question(
                self,
                "Admin Privileges Required",
                f"{operation_description} requires root privileges.\n"
                "The application will prompt for your password when needed.\n\n"
                "Do you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            return reply == QMessageBox.StandardButton.Yes
        return False

    def open_plugin_management_dialog(self) -> None:
        dlg = PluginManagementDialog(self, self.settings_service)
        dlg.pluginToggled.connect(self.on_plugin_toggled)
        dlg.resize(900, 560)
        dlg.exec()

    def on_plugin_toggled(self, plugin_name: str, enabled: bool) -> None:
        if enabled:
            if plugin_name not in self.loaded_tabs:
                plugin_class = plugin_registry.get_plugin(plugin_name)
                if plugin_class:
                    self.add_tab(plugin_name, plugin_class)
        else:
            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabText(i) == plugin_name:
                    self.tab_widget.removeTab(i)
                    break
            if plugin_name in self.loaded_tabs:
                del self.loaded_tabs[plugin_name]
        
        # Save user-disabled plugins to settings (excludes plugins disabled by default)
        if self.settings_service:
            try:
                # Determine which plugins are disabled by the user (not by default)
                # Get all disabled plugins
                all_disabled = [name for name in plugin_registry.list_plugin_names() 
                              if not plugin_registry.is_enabled(name)]
                
                # Filter out plugins that are disabled_by_default
                user_disabled = []
                for plugin_name in all_disabled:
                    plugin_class = plugin_registry.get_plugin(plugin_name)
                    if plugin_class and not getattr(plugin_class, 'disabled_by_default', False):
                        user_disabled.append(plugin_name)
                
                logger.debug(f"Saving user-disabled plugins: {user_disabled}")
                self.settings_service.save_disabled_plugins(user_disabled)
            except Exception as e:
                logger.warning(f"Failed to save plugin states: {e}")
        
        self.update_window_title()

    def open_theme_dialog(self) -> None:
        dialog = ThemeDialog(self.theme_manager, self)
        dialog.themeSelected.connect(self.on_theme_selected)
        dialog.exec()

    def on_theme_selected(self, theme_name: str) -> None:
        logger.info(f"Theme selected: {theme_name}")
        # Refresh toast notifications with new theme
        if hasattr(self, 'toast_manager'):
            self.toast_manager.update_theme_manager(self.theme_manager)
            self.toast_manager.refresh_theme()

    def restart_as_admin(self) -> None:
        if CURRENT_PLATFORM == "windows":
            try:
                run_as_admin()
            except Exception as e:
                logger.error(f"Failed to restart as administrator: {e}")
                QMessageBox.critical(self, "Error", f"Failed to restart as administrator:\n{e}")
    
    
    def setup_toast_manager(self) -> None:
        """Setup the toast notification manager."""
        self.toast_manager = ToastManager(self, self.theme_manager)
    
    def setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        if not self.settings_service or not self.settings_service.get_shortcuts_enabled():
            return
            
        self.shortcut_manager = ShortcutManager(self)
        
        # Connect shortcut signals
        self.shortcut_manager.nextTab.connect(self.next_tab)
        self.shortcut_manager.prevTab.connect(self.previous_tab)
        self.shortcut_manager.toggleFullscreen.connect(self.toggle_fullscreen)
    
    def setup_tooltips(self) -> None:
        """Setup tooltips for UI elements."""
        if not self.settings_service or not self.settings_service.get_show_tooltips():
            return
            
        # Add tooltips to menu actions
        if hasattr(self, 'manage_plugins_action'):
            self.manage_plugins_action.setToolTip("Enable or disable plugins and manage their settings")
        if hasattr(self, 'select_theme_action'):
            self.select_theme_action.setToolTip("Choose from available themes or import custom ones")
        if hasattr(self, 'preferences_action'):
            self.preferences_action.setToolTip("Configure application settings and preferences")
        
        if hasattr(self, 'restart_admin_action'):
            self.restart_admin_action.setToolTip("Restart the application with administrator privileges")
    
    
    
    def next_tab(self) -> None:
        """Switch to next tab."""
        current = self.tab_widget.currentIndex()
        if current < self.tab_widget.count() - 1:
            self.tab_widget.setCurrentIndex(current + 1)
    
    def previous_tab(self) -> None:
        """Switch to previous tab."""
        current = self.tab_widget.currentIndex()
        if current > 0:
            self.tab_widget.setCurrentIndex(current - 1)
    
    def close_current_tab(self) -> None:
        """Close the current tab."""
        current = self.tab_widget.currentIndex()
        if current >= 0:
            self.close_tab_by_index(current)
    
    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    
    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event to save settings."""
        if self.settings_service:
            # Save window geometry
            geom = self.geometry()
            self.settings_service.save_window_geometry(
                geom.x(), geom.y(), geom.width(), geom.height()
            )
            
            # Save window state
            if self.isMaximized():
                self.settings_service._settings.window_geometry.maximized = True
            elif self.isFullScreen():
                self.settings_service._settings.window_geometry.fullscreen = True
            else:
                self.settings_service._settings.window_geometry.maximized = False
                self.settings_service._settings.window_geometry.fullscreen = False
            self.settings_service._save_settings()
        
        event.accept()
    
    def show_tab_context_menu(self, position: QPoint) -> None:
        """Show context menu for tabs."""
        # Find the tab at the position
        tab_index = self.tab_widget.tabBar().tabAt(position)
        if tab_index < 0:
            return
        
        tab_name = self.tab_widget.tabText(tab_index)
        
        # Create context menu
        context_menu = QMenu(self)
        
        # Close tab action
        close_action = QAction("Close Tab", self)
        close_action.setShortcut(QKeySequence("Ctrl+W"))
        close_action.triggered.connect(lambda: self.close_tab_by_index(tab_index))
        context_menu.addAction(close_action)
        
        # Close other tabs action
        close_others_action = QAction("Close Other Tabs", self)
        close_others_action.triggered.connect(lambda: self.close_other_tabs(tab_index))
        context_menu.addAction(close_others_action)
        
        # Close all tabs action
        close_all_action = QAction("Close All Tabs", self)
        close_all_action.triggered.connect(self.close_all_tabs)
        context_menu.addAction(close_all_action)
        
        context_menu.addSeparator()
        
        # Plugin info action
        info_action = QAction("Plugin Info", self)
        info_action.triggered.connect(lambda: self.show_plugin_info(tab_name))
        context_menu.addAction(info_action)
        
        # Show the context menu
        context_menu.exec(self.tab_widget.mapToGlobal(position))
    
    def close_tab_by_index(self, index: int) -> None:
        """Close tab by index."""
        if 0 <= index < self.tab_widget.count():
            tab_name = self.tab_widget.tabText(index)
            self.tab_widget.removeTab(index)
            if tab_name in self.loaded_tabs:
                del self.loaded_tabs[tab_name]
            self.update_window_title()
            
            # Show toast notification
            if hasattr(self, 'toast_manager'):
                self.toast_manager.show_info(f"Closed tab: {tab_name}")
    
    def close_other_tabs(self, keep_index: int) -> None:
        """Close all tabs except the one at keep_index."""
        if keep_index < 0 or keep_index >= self.tab_widget.count():
            return
        
        # Close tabs from right to left to avoid index shifting
        for i in range(self.tab_widget.count() - 1, -1, -1):
            if i != keep_index:
                self.close_tab_by_index(i)
    
    def close_all_tabs(self) -> None:
        """Close all tabs."""
        reply = QMessageBox.question(
            self, "Close All Tabs",
            "Are you sure you want to close all tabs?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            while self.tab_widget.count() > 0:
                self.close_tab_by_index(0)
    
    def show_plugin_info(self, tab_name: str) -> None:
        """Show information about the plugin in the tab."""
        if tab_name in self.loaded_tabs:
            tab_info = self.loaded_tabs[tab_name]
            plugin_class = tab_info.get("plugin_class")
            
            if plugin_class:
                info = plugin_class.get_plugin_info()
                
                info_text = f"""Plugin Information:

Name: {info.get('name', 'Unknown')}
Description: {info.get('description', 'No description')}
Version: {info.get('version', 'Unknown')}
Author: {info.get('author', 'Unknown')}
Supported Platforms: {', '.join(info.get('supported_platforms', []))}
Requires Admin: {'Yes' if info.get('requires_admin', False) else 'No'}
Compatible: {'Yes' if info.get('compatible', False) else 'No'}"""
                
                QMessageBox.information(self, f"Plugin Info - {tab_name}", info_text)
            else:
                QMessageBox.information(self, f"Plugin Info - {tab_name}", "No plugin information available.")
        else:
                QMessageBox.warning(self, "Plugin Info", f"Tab '{tab_name}' not found.")


__all__ = ['MainWindow']