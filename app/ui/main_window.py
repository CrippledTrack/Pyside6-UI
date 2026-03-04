"""
Main window implementation for the GUI application.

This module provides the main application window, using controllers,
managers, and builders for better separation of concerns.
"""

from __future__ import annotations

import logging
import platform
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..services.container import ServiceContainer
    from ..services.settings_service import SettingsService
    from ...themes.theme_manager import ThemeManager

from ..qt_bindings import (
    QPoint,
    Qt,
    Slot,
    QAction,
    QCloseEvent,
    QKeySequence,
    QApplication,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..services.plugin_service import PluginService
from ..services.admin_service import AdminService
from ..services.daemon_service import DaemonService
from ..services.tab_loader_service import TabLoaderThread
from ..services.plugin_registry_facade import PluginRegistryFacade
from .controllers.tab_controller import TabController
from .controllers.plugin_controller import PluginController
from .controllers.menu_bar_controller import MenuBarController
from .controllers.window_title_manager import WindowTitleManager
from .controllers.status_bar_manager import StatusBarManager
from .controllers.shortcut_manager import ShortcutManager
from .controllers.toast_manager import ToastManager
from .dialogs.plugin_dialog import PluginManagementDialog
from .dialogs.theme_dialog import ThemeDialog
from .dialogs.log_viewer_dialog import LogViewerDialog
from ..utils.display_utils import build_version_details
from ..utils.imports import get_platforms_constants

# Import platform constants using the utility function
constants = get_platforms_constants()
VERSION = constants.VERSION
VERSION_INFO = constants.VERSION_INFO
VERSION_NAME = constants.VERSION_NAME

# Import centralized platform constant
from ..constants import CURRENT_PLATFORM

# Platform-specific elevation imports (for restart_as_admin)
if CURRENT_PLATFORM == "windows":
    from ..utils.elevation_windows import run_as_admin
elif CURRENT_PLATFORM == "linux":
    from ..utils.elevation_linux import run_as_admin

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(
        self,
        theme_manager: Optional["ThemeManager"] = None,
        settings_service: Optional["SettingsService"] = None,
        container: "ServiceContainer" = None  # type: ignore[assignment]
    ) -> None:
        """Initialize the main window.
        
        Args:
            theme_manager: Optional theme manager instance (retrieved from container if not provided)
            settings_service: Optional settings service instance
            container: Service container for dependency injection (required)
            
        Raises:
            ValueError: If container is None
        """
        super().__init__()
        logger.info(f"Initializing MainWindow for {VERSION_NAME} v{VERSION} on {CURRENT_PLATFORM}")
        
        if container is None:
            raise ValueError("ServiceContainer is required for MainWindow initialization")
        
        self.container = container
        self.settings_service = settings_service
        
        # Get ThemeManager from container if not explicitly provided
        if theme_manager is None:
            from ...themes.theme_manager import ThemeManager
            theme_manager = container.get(ThemeManager)
        self.theme_manager = theme_manager
        
        self._theme_dialog: Optional[ThemeDialog] = None
        self._plugin_dialog: Optional[PluginManagementDialog] = None
        self._log_viewer_dialog: Optional[LogViewerDialog] = None
        self._about_dialog: Optional[QMessageBox] = None
        
        # Get services from container
        self.admin_service = container.get(AdminService)
        self.daemon_service = container.get(DaemonService)
        self.plugin_registry = container.get(PluginRegistryFacade)
        
        # Register daemon refresh callback on Linux
        if CURRENT_PLATFORM == "linux":
            self.daemon_service.register_refresh_callback(self._refresh_admin_tabs)
        
        # Initialize UI components
        self._setup_window_geometry()
        self._setup_ui_components()
        self._setup_controllers()
        self._setup_managers()
        self._setup_status_bar()
        self.setup_toast_manager()
        self.setup_shortcuts()
        QApplication.processEvents()
        self._start_tab_loader()
        self._setup_menu_bar()
        self._update_window_title()
        self._setup_tooltips()
    
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
        self.tab_widget.setMovable(True)
        self.tab_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_widget.customContextMenuRequested.connect(self.show_tab_context_menu)
        layout.addWidget(self.tab_widget)
    
    def _setup_controllers(self) -> None:
        """Setup controllers for tab and plugin management."""
        # Create tab controller - now accepts container directly
        self.tab_controller = TabController(
            self.tab_widget,
            self.container,
            self
        )
        # Connect tab controller signals
        self.tab_controller.title_update_requested.connect(self._update_window_title)
        self.tab_controller.set_restart_admin_callback(self.restart_as_admin)
        
        # Create plugin controller - now accepts container directly
        self.plugin_controller = PluginController(
            self.container,
            self
        )
        # Set main_window reference for dynamic extension integration
        self.plugin_controller._main_window = self
        # Connect plugin controller signals
        self.plugin_controller.plugin_toggled.connect(self._on_plugin_toggled)
    
    def _setup_managers(self) -> None:
        """Setup UI controllers for window title and status bar."""
        # Create window title manager
        self.title_manager = WindowTitleManager(self, self.tab_controller)
        
        # Status bar manager will be created in _setup_status_bar
        self.status_bar_manager: Optional[StatusBarManager] = None
    
    def _setup_status_bar(self) -> None:
        """Create and configure the status bar."""
        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)
        status_bar.setMaximumHeight(20)
        
        # Get notification service
        from ..services.notification_service import NotificationService
        notification_service = self.container.get(NotificationService)
        
        # Create status bar manager
        self.status_bar_manager = StatusBarManager(
            status_bar, 
            self, 
            notification_service,
            self.theme_manager
        )
    
    def _setup_menu_bar(self) -> None:
        """Create menu bar and all menu items."""
        menu_bar = QMenuBar(self)
        
        # Apply menu bar styling only if new UI is enabled
        if self.settings_service and self.settings_service.get_new_ui_enabled():
            menu_bar.setStyleSheet("""
                QMenuBar {
                    padding: 2px 0px;
                }
                QMenuBar::item {
                    padding: 4px 8px;
                }
            """)
        
        self.setMenuBar(menu_bar)
        
        # Create menu bar controller - now accepts container directly
        self.menu_controller = MenuBarController(
            menu_bar,
            self.container,
            self
        )
        
        # Setup menu bar (UI toggle removed - now in theme dialog)
        self.menu_controller.setup(
            on_manage_plugins=self.open_plugin_management_dialog,
            on_select_theme=self.open_theme_dialog,
            on_restart_admin=self.restart_as_admin,
            on_view_logs=self.open_log_viewer_dialog,
            on_about=self.show_about_dialog,
            on_toggle_new_ui=None  # Moved to theme dialog
        )
    
        # Connect dev menu signals
        self.menu_controller.cross_platform_toggled.connect(self._on_cross_platform_toggled)
    
    def _start_tab_loader(self) -> None:
        """Configure and start the tab loading thread."""
        # Clean up any previously running tab loader thread
        if hasattr(self, 'tab_loader') and self.tab_loader is not None:
            try:
                # Disconnect signals to prevent duplicate callbacks
                self.tab_loader.finished.disconnect()
                self.tab_loader.error.disconnect()
                self.tab_loader.add_tab.disconnect()
            except (RuntimeError, TypeError):
                # Signals may already be disconnected
                pass
            
            # Wait for the thread to finish if still running
            if self.tab_loader.isRunning():
                logger.debug("Waiting for previous tab loader thread to finish...")
                self.tab_loader.cancel()
                self.tab_loader.wait(5000)  # Wait up to 5 seconds
                if self.tab_loader.isRunning():
                    logger.warning("Previous tab loader thread did not finish in time")
        
        plugin_service = self.container.get(PluginService)
        self.tab_loader = TabLoaderThread(
            plugin_service=plugin_service,
            settings_service=self.settings_service
        )
        self.tab_loader.finished.connect(self.on_tabs_loaded)
        self.tab_loader.error.connect(self.on_tab_load_error)
        self.tab_loader.add_tab.connect(self.tab_controller.add_tab)
        self.tab_loader.start()
    
    def _update_window_title(self) -> None:
        """Update the window title."""
        if self.title_manager:
            self.title_manager.update_title()
    
    def on_tabs_loaded(self) -> None:
        """Handle tab loading completion."""
        self.loading_widget.hide()
        self.tab_widget.show()
        
        # Fix for table header resizing issues (only in new UI)
        if self.settings_service and self.settings_service.get_new_ui_enabled():
            from ..qt_bindings import QTableView, QHeaderView, QTreeWidget
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                # Recursively find all QTableViews and QTreeWidgets
                for table in widget.findChildren(QTableView):
                    try:
                        header = table.horizontalHeader()
                        # Check if sections are visible before resizing
                        if header.count() > 0:
                            # Set resize mode to Interactive but resize to contents initially
                            # This allows users to resize but starts with good width
                            for col in range(header.count()):
                                # Don't override if specifically set to something else by the plugin
                                # Only apply if using default behavior
                                if header.sectionResizeMode(col) == QHeaderView.ResizeMode.Interactive:
                                    header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
                    except Exception:
                        pass
                
                for tree in widget.findChildren(QTreeWidget):
                    try:
                        header = tree.header()
                        if header.count() > 0:
                            for col in range(header.count()):
                                if header.sectionResizeMode(col) == QHeaderView.ResizeMode.Interactive:
                                    header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
                    except Exception:
                        pass

        logger.info("All tabs loaded successfully")
        self._update_window_title()
        
        # Restore last active tab
        if self.settings_service:
            last_active = self.settings_service.get_last_active_tab()
            if last_active:
                # Find index of this tab
                for i in range(self.tab_widget.count()):
                    if self.tab_widget.tabText(i) == last_active:
                        self.tab_widget.setCurrentIndex(i)
                        break
        
        # Integrate extension plugins (Menu, Status, Toolbar, Service)
        self.plugin_controller.integrate_extensions(self)
    
    def on_tab_load_error(self, error_msg: str) -> None:
        """Handle tab loading error."""
        self.loading_widget.hide()
        self.tab_widget.show()
        logger.error(f"Error loading tabs: {error_msg}")
        QMessageBox.critical(self, "Error", f"Failed to load tabs: {error_msg}")
    
    def get_version_details(self) -> Dict[str, str]:
        """Get version details."""
        return build_version_details(VERSION_INFO, CURRENT_PLATFORM)
    
    def prompt_for_admin_operation(self, operation_description: str) -> bool:
        """Prompt user for admin operation and check if admin is available.
        
        Args:
            operation_description: Description of the operation requiring admin
            
        Returns:
            True if admin is available, False otherwise
        """
        return self.admin_service.prompt_for_admin_operation(operation_description, self)
    
    def open_plugin_management_dialog(self) -> None:
        """Open the plugin management dialog (non-modal)."""
        if self._plugin_dialog and self._plugin_dialog.isVisible():
            self._plugin_dialog.raise_()
            self._plugin_dialog.activateWindow()
            return

        dlg = PluginManagementDialog(self, self.settings_service, self.plugin_controller)
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.plugin_toggled.connect(self.plugin_controller.toggle_plugin)
        dlg.destroyed.connect(lambda: setattr(self, "_plugin_dialog", None))
        dlg.resize(900, 560)

        self._plugin_dialog = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
    
    def _on_plugin_toggled(self, plugin_name: str, enabled: bool) -> None:
        """Handle plugin toggle event.
        
        Args:
            plugin_name: Name of the plugin
            enabled: True if enabled, False if disabled
        """
        if enabled:
            plugin_class = self.plugin_controller.get_plugin(plugin_name)
            if plugin_class:
                # Check if Tab extension is enabled
                if self.settings_service.is_extension_enabled(plugin_name, "Tab"):
                    self.tab_controller.add_tab(plugin_name, plugin_class)
        else:
            self.tab_controller.remove_tab(plugin_name)
        
        self._update_window_title()
    
    def open_theme_dialog(self) -> None:
        """Open the theme selection dialog (non-modal)."""
        if self._theme_dialog and self._theme_dialog.isVisible():
            self._theme_dialog.raise_()
            self._theme_dialog.activateWindow()
            return

        dialog = ThemeDialog(self.theme_manager, self.settings_service, self)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.theme_selected.connect(self.on_theme_selected)
        dialog.ui_toggle_changed.connect(self._on_ui_toggle_from_dialog)
        dialog.destroyed.connect(lambda: setattr(self, "_theme_dialog", None))

        self._theme_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
    
    def _on_ui_toggle_from_dialog(self, enabled: bool) -> None:
        """Handle UI toggle change from theme dialog."""
        # Update menu action if it exists (for consistency)
        if self.menu_controller:
            self.menu_controller.update_new_ui_action()
        
        # Reapply current theme with new UI flag setting
        if self.theme_manager:
            current_theme = self.theme_manager.get_current_theme()
            if current_theme:
                self.theme_manager.apply_theme(current_theme, new_ui_enabled=enabled)
        
        # Show notification
        state_text = "enabled" if enabled else "disabled"
        self.toast_manager.show_info(
            f"New UI {state_text}. Some changes may require restart to take full effect."
        )
        
        logger.info(f"New UI toggled from theme dialog: {enabled}")
    
    def open_log_viewer_dialog(self) -> None:
        """Open the log viewer dialog (non-modal)."""
        if self._log_viewer_dialog and self._log_viewer_dialog.isVisible():
            self._log_viewer_dialog.raise_()
            self._log_viewer_dialog.activateWindow()
            return

        dialog = LogViewerDialog(self)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.destroyed.connect(lambda: setattr(self, "_log_viewer_dialog", None))

        self._log_viewer_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
    
    def show_about_dialog(self) -> None:
        """Show the About dialog without blocking the main window."""
        from ..constants import VERSION as GUI_VERSION, VERSION_NAME as DEFAULT_VERSION_NAME
        from ..utils.about_info import create_about_dialog
        
        if self._about_dialog and self._about_dialog.isVisible():
            self._about_dialog.raise_()
            self._about_dialog.activateWindow()
            return

        has_external_constants = VERSION_NAME != DEFAULT_VERSION_NAME
        msg = create_about_dialog(
            self,
            app_name=VERSION_NAME,
            app_version=VERSION if has_external_constants else None,
            gui_api_version=GUI_VERSION,
            platform_name=CURRENT_PLATFORM,
        )
        msg.destroyed.connect(lambda: setattr(self, "_about_dialog", None))

        self._about_dialog = msg
        msg.show()
        msg.raise_()
        msg.activateWindow()
    
    def on_theme_selected(self, theme_name: str) -> None:
        """Handle theme selection.
        
        Args:
            theme_name: Name of the selected theme
        """
        logger.info(f"Theme selected: {theme_name}")
        # Reapply theme with current UI flag setting
        if self.settings_service:
            new_ui_enabled = self.settings_service.get_new_ui_enabled()
            self.theme_manager.apply_theme(theme_name, new_ui_enabled=new_ui_enabled)
        else:
            self.theme_manager.apply_theme(theme_name)
        # Refresh toast notifications with new theme
        if hasattr(self, 'toast_manager'):
            self.toast_manager.update_theme_manager(self.theme_manager)
            self.toast_manager.refresh_theme()
        
        # Refresh status bar notifications with new theme
        if hasattr(self, 'status_bar_manager') and self.status_bar_manager:
            self.status_bar_manager.refresh_theme()

        # Refresh menu bar styling (especially for blank/default stylesheets)
        if self.menu_controller:
            self.menu_controller.refresh_for_theme_change()
        
        # Publish event for subscribers
        self.plugin_registry.publish_event("theme_changed", {"theme": theme_name})

    
    def restart_as_admin(self) -> None:
        """Restart the application with administrator/root privileges.
        
        On Windows: Restarts the entire application as administrator.
        On Linux: Starts the privileged daemon (GUI continues running as normal user).
        """
        try:
            if CURRENT_PLATFORM == "windows":
                run_as_admin()
            elif CURRENT_PLATFORM == "linux":
                # Use daemon service to start the daemon
                success, error_msg = self.daemon_service.start()
                
                if success:
                    self.toast_manager.show_success("Privileged daemon started successfully")
                else:
                    self.toast_manager.show_error(
                        f"Failed to start daemon: {error_msg or 'Check system permissions'}"
                    )
            else:
                logger.warning(f"Restart as admin not supported on platform: {CURRENT_PLATFORM}")
                self.toast_manager.show_warning(
                    f"Not supported on {CURRENT_PLATFORM}"
                )
        except Exception as e:
            logger.error(f"Failed to restart as administrator: {e}")
            self.toast_manager.show_error(f"Failed to restart as administrator: {e}")
    
    def _refresh_admin_tabs(self) -> None:
        """Refresh tabs that require admin privileges.
        
        This is called automatically by the daemon service when the daemon becomes available.
        """
        logger.info("Refreshing admin-required tabs")
        
        # Update menu bar
        if self.menu_controller:
            self.menu_controller.update_admin_menu()
        
        # Refresh admin tabs through tab controller
        # The tab controller will handle reloading tabs when they are activated
        # We just need to trigger a refresh of the current tab if it's an admin placeholder
        if CURRENT_PLATFORM == "linux" and self.daemon_service.is_available():
            current_index = self.tab_widget.currentIndex()
            if current_index >= 0:
                # Trigger tab change to reload if needed
                self.tab_controller.on_tab_changed(current_index)
    
    def _on_cross_platform_toggled(self, enabled: bool) -> None:
        """Handle cross-platform tabs toggle from dev menu.
        
        Args:
            enabled: True if cross-platform tabs should be shown
        """
        # Human-readable names for known platforms, used in toast messages.
        platform_labels = {
            "windows": "Windows",
            "linux": "Linux",
            "darwin": "macOS",
        }
        all_platform_keys = ["windows", "linux", "darwin"]
        current_key = CURRENT_PLATFORM
        other_platforms = [
            platform_labels[p]
            for p in all_platform_keys
            if p != current_key and p in platform_labels
        ]
        other_text = ", ".join(other_platforms) if other_platforms else "other platforms"
        
        # Always clear the cross-platform plugin cache so that any subsequent
        # discovery run reflects the new toggle state and (for dev mode) the
        # correct mock modules installed by PluginService.
        try:
            from ..utils.dev_mode_utils.cross_platform_plugins import clear_cross_platform_cache
            clear_cross_platform_cache()
        except ImportError:
            logger.warning("Could not clear cross-platform plugin cache")
        
        # Reload plugins with the new cross-platform setting applied.
        self._reload_all_plugins()
        
        if enabled:
            self.toast_manager.show_info(
                f"Loading tabs from {other_text}... Some features may not work on this platform."
            )
        else:
            self.toast_manager.show_info(f"Removed tabs from {other_text}")
    
    def _reload_all_plugins(self) -> None:
        """Reload all plugins and tabs.
        
        This clears the plugin registry and re-discovers all plugins,
        then reloads the tabs. Used when toggling cross-platform tabs.
        """
        logger.info("Reloading all plugins...")
        
        # Clean up all previously integrated extensions before clearing registry
        # This prevents duplicate menu items, toolbar actions, and status widgets
        # and ensures ServiceExtension plugins are properly shut down
        self.plugin_controller.cleanup_all_extensions()
        
        # Clear existing tabs
        while self.tab_widget.count() > 0:
            self.tab_widget.removeTab(0)
        
        # Clear tab controller state
        self.tab_controller.clear_loaded_tabs()
        
        # Clear plugin registry
        self.container.get(PluginService).clear()
        
        # Show loading state
        self.tab_widget.hide()
        self.loading_widget.show()
        
        # Re-run tab loader
        self._start_tab_loader()
    
    def setup_toast_manager(self) -> None:
        """Setup the toast notification manager."""
        from ..services.notification_service import NotificationService
        notification_service = self.container.get(NotificationService)
        self.toast_manager = ToastManager(self, self.theme_manager, notification_service)
    
    def setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        if not self.settings_service or not self.settings_service.get_shortcuts_enabled():
            return
        
        self.shortcut_manager = ShortcutManager(self)
        
        # Connect shortcut signals
        self.shortcut_manager.nextTab.connect(self.next_tab)
        self.shortcut_manager.prevTab.connect(self.previous_tab)
        self.shortcut_manager.toggleFullscreen.connect(self.toggle_fullscreen)
    
    def _setup_tooltips(self) -> None:
        """Setup tooltips for UI elements."""
        # Tooltips are handled by MenuBarController
        pass
    
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
            self.settings_service.save_window_state(
                geom.x(),
                geom.y(),
                geom.width(),
                geom.height(),
                maximized=self.isMaximized(),
                fullscreen=self.isFullScreen()
            )
            
            # Save session state (tab order and active tab)
            tab_order = self.tab_controller.get_tab_order()
            active_tab = self.tab_controller.get_current_tab_name()
            self.settings_service.save_session_state(tab_order, active_tab)
            
        # Shutdown ServiceExtension plugins
        self.plugin_controller.shutdown_service_extensions()
        
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
            self.tab_controller.remove_tab_by_index(index)
            self._update_window_title()
            
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
        plugin_info = self.plugin_controller.get_plugin_info(tab_name)
        
        if plugin_info:
            info_text = f"""Plugin Information:

Name: {plugin_info.get('name', 'Unknown')}
Description: {plugin_info.get('description', 'No description')}
Version: {plugin_info.get('version', 'Unknown')}
Author: {plugin_info.get('author', 'Unknown')}
Supported Platforms: {', '.join(plugin_info.get('supported_platforms', []))}
Requires Admin: {'Yes' if plugin_info.get('requires_admin', False) else 'No'}
Compatible: {'Yes' if plugin_info.get('compatible', False) else 'No'}"""
            
            QMessageBox.information(self, f"Plugin Info - {tab_name}", info_text)
        else:
            QMessageBox.warning(self, "Plugin Info", f"Plugin '{tab_name}' not found.")
    
    def show_status(self, message: str, timeout: int = 0) -> None:
        """Show a status message in the status bar.
        
        Args:
            message: Status message to display
            timeout: Timeout in milliseconds (0 = permanent)
        """
        if self.status_bar_manager:
            self.status_bar_manager.show_status(message, timeout)
    
    def clear_status(self) -> None:
        """Clear the status bar message."""
        if self.status_bar_manager:
            self.status_bar_manager.clear_status()
    
    def toggle_new_ui(self) -> None:
        """Toggle the new UI overhaul flag.
        
        This allows users to switch between the new UI overhaul and the old UI.
        Some changes may require an application restart to take full effect.
        """
        if not self.settings_service or not self.menu_controller:
            return
        
        # Get the new state from the action (Qt already toggled it)
        toggle_action = self.menu_controller.toggle_new_ui_action
        if not toggle_action:
            return
        
        new_state = toggle_action.isChecked()
        
        # Save the new state
        self.settings_service.save_new_ui_enabled(new_state)
        
        # Update menu action text
        self.menu_controller._update_new_ui_action_text()
        
        # Update menu bar styling immediately
        menu_bar = self.menuBar()
        if menu_bar:
            if new_state:
                menu_bar.setStyleSheet("""
                    QMenuBar {
                        padding: 2px 0px;
                    }
                    QMenuBar::item {
                        padding: 4px 8px;
                    }
                """)
            else:
                # Old UI: no custom styling
                menu_bar.setStyleSheet("")
        
        # Reapply current theme with new UI flag setting
        # This will automatically switch between legacy and new theme managers
        if self.theme_manager:
            current_theme = self.theme_manager.get_current_theme()
            if current_theme:
                # Force reapply with new flag - this will switch theme managers if needed
                self.theme_manager.apply_theme(current_theme, new_ui_enabled=new_state)
            else:
                # If no theme is set, apply auto theme with new flag
                self.theme_manager.apply_auto_theme()
        
        # Note: Table header resizing changes will apply on next tab load
        # Margins stay the same (20, 20, 20, 20) in both versions
        
        # Show notification
        state_text = "enabled" if new_state else "disabled"
        self.toast_manager.show_info(
            f"New UI {state_text}. Some changes may require restart to take full effect."
        )
        
        logger.info(f"New UI toggled: {new_state}")


__all__ = ['MainWindow']
