"""
Main window implementation for the GUI application.

This module provides the main application window, using controllers,
managers, and builders for better separation of concerns.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Set

# PERF: We use TYPE_CHECKING to hide these imports from the runtime. This provides full
# IDE autocompletion and static analysis support without paying the 100ms+ startup
# penalty of importing these heavy UI controllers during module load.
if TYPE_CHECKING:
    from ...services.container import ServiceContainer
    from ...services.interfaces import ISettingsService, IAdminService, IDaemonService, INotificationService
    from .themes.theme_manager import ThemeManager
    from ..dialogs.plugin_dialog import PluginManagementDialog
    from .dialogs.theme_dialog import ThemeDialog
    from ..dialogs.log_viewer_dialog import LogViewerDialog
    from ..dialogs.about_dialog import AboutDialog
    from .controllers.menu_bar_controller import MenuBarController
    from .controllers.window_title_manager import WindowTitleManager
    from .controllers.status_bar_manager import StatusBarManager
    from .controllers.shortcut_manager import ShortcutManager
    from .controllers.toast_manager import ToastManager

from .bindings import (
    Qt,
    QAction,
    QCloseEvent,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QTimer,
    QVBoxLayout,
    QWidget,
    QToolBar,
)

from ...services.interfaces import IAdminService, IDaemonService, ISettingsService
from ...services.plugin_service import PluginService
from .tab_loader import TabLoaderThread
from .controllers.tab_controller import TabController
from ..controllers.plugin_controller import PluginController
from ...utils.imports import get_platforms_constants
from ..abstractions.types import (
    MenuItemHandle,
    MenuItemSpec,
    StatusWidgetHandle,
    ToolbarActionHandle,
    ToolbarActionSpec,
    ToastType,
)
from ...services.notification_service import Notification, NotificationType

# Import platform constants using the utility function
constants = get_platforms_constants()
VERSION = constants.VERSION
VERSION_NAME = constants.VERSION_NAME

# Import centralized platform constant
from ...constants import CURRENT_PLATFORM


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(
        self,
        theme_manager: Optional["ThemeManager"] = None,
        settings_service: Optional["ISettingsService"] = None,
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
            from .themes.theme_manager import ThemeManager
            theme_manager = container.get(ThemeManager)
        self.theme_manager = theme_manager
        
        self._theme_dialog: Optional["ThemeDialog"] = None
        self._plugin_dialog: Optional["PluginManagementDialog"] = None
        self._log_viewer_dialog: Optional["LogViewerDialog"] = None
        self._about_dialog: Optional["AboutDialog"] = None
        self._plugin_toolbar: Optional[QToolBar] = None
        self._menu_handle_map: Dict[MenuItemHandle, tuple] = {}
        self._toolbar_handle_map: Dict[ToolbarActionHandle, QAction] = {}
        self._status_handle_map: Dict[StatusWidgetHandle, QWidget] = {}
        self._created_menu_titles: Set[str] = set()
        
        # Get services from container
        self.admin_service = container.get(IAdminService)
        self.daemon_service = container.get(IDaemonService)
        self.plugin_service = container.get(PluginService)
        
        # Register daemon refresh callback on Linux
        if CURRENT_PLATFORM == "linux":
            self.daemon_service.register_refresh_callback(self._refresh_admin_tabs)
        
        # Pre-declare attributes that are created during deferred init,
        # so early callbacks (e.g. on_tabs_loaded) can guard against None.
        self.title_manager: Optional[WindowTitleManager] = None
        self.status_bar_manager: Optional[StatusBarManager] = None
        self.menu_controller: Optional[MenuBarController] = None
        self.toast_manager: Optional[ToastManager] = None
        self.shortcut_manager: Optional[ShortcutManager] = None
        
        # ── Critical path (must complete before window.show()) ──────────
        self._setup_window_geometry()
        self._setup_ui_components()
        self._setup_controllers()
        
        # ── Complete initialization synchronously before window.show() ──
        # This prevents the brief white/unthemed window and "python" title flash on startup
        self._complete_deferred_init()
    
    def _complete_deferred_init(self) -> None:
        """Finish initializing components that aren't needed for the first paint."""
        self._setup_managers()
        self._setup_status_bar()
        self.setup_toast_manager()
        self.setup_shortcuts()
        self._setup_menu_bar()
        self._update_window_title()
        self._setup_tooltips()
        self._start_tab_loader()
    
    def _setup_window_geometry(self) -> None:
        """Restore window size and state from settings."""
        if not self.settings_service:
            return
        
        geom = self.settings_service.get_window_geometry()
        self.resize(geom.width, geom.height)
        if geom.maximized:
            self.setWindowState(Qt.WindowState.WindowMaximized)
        elif geom.fullscreen:
            self.setWindowState(Qt.WindowState.WindowFullScreen)
    
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
        if getattr(constants, "SINGLE_PLUGIN_MODE", False):
            self.tab_widget.tabBar().hide()
        layout.addWidget(self.tab_widget)
    
    def _setup_controllers(self) -> None:
        """Setup controllers for tab and plugin management."""
        # Create tab controller - now accepts dependencies directly
        self.tab_controller = TabController(
            tab_widget=self.tab_widget,
            admin_service=self.admin_service,
            daemon_service=self.daemon_service,
            plugin_service=self.plugin_service,
            parent=self,
        )
        # Connect tab controller signals
        self.tab_controller.title_update_requested.connect(self._update_window_title)
        self.tab_controller.set_restart_admin_callback(self.restart_as_admin)
        
        # Connect context menu directly to tab_controller
        self.tab_widget.customContextMenuRequested.connect(self.tab_controller.show_tab_context_menu)

        self.plugin_service.subscribe_lifecycle(self.tab_controller)

        # Create plugin controller - now accepts container directly
        self.plugin_controller = PluginController(self.container)
        # Set main_window reference for dynamic extension integration
        self.plugin_controller._main_window = self
        self.plugin_controller.add_plugin_toggled_listener(self._on_plugin_toggled)
    
    def _setup_managers(self) -> None:
        """Setup UI controllers for window title and status bar."""
        from .controllers.window_title_manager import WindowTitleManager
        self.title_manager = WindowTitleManager(self, self.tab_controller)
    
    def _setup_status_bar(self) -> None:
        """Create and configure the status bar."""
        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)
        status_bar.setMaximumHeight(20)
        
        # Create status bar manager - now passes dependencies directly
        from .controllers.status_bar_manager import StatusBarManager
        from ...services.interfaces import INotificationService
        self.status_bar_manager = StatusBarManager(
            status_bar=status_bar, 
            notification_service=self.container.get(INotificationService),
            theme_manager=self.theme_manager,
            parent=self,
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
        
        # Create menu bar controller - now accepts dependencies directly
        from .controllers.menu_bar_controller import MenuBarController
        self.menu_controller = MenuBarController(
            menu_bar=menu_bar,
            admin_service=self.admin_service,
            daemon_service=self.daemon_service,
            settings_service=self.settings_service,
            parent_widget=self,
        )
        
        # Setup menu bar (new vs classic UI is toggled in the theme dialog)
        self.menu_controller.setup(
            on_manage_plugins=self.open_plugin_management_dialog,
            on_select_theme=self.open_theme_dialog,
            on_restart_admin=self.restart_as_admin,
            on_view_logs=self.open_log_viewer_dialog,
            on_about=self.show_about_dialog,
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
        
        # Enable batch loading mode in tab controller to prevent premature tab activation/lazy loading
        # when the first tab is added or during bulk addition.
        self.tab_controller.set_batch_loading(True)
        
        self.tab_loader.start()
    
    def _update_window_title(self) -> None:
        """Update the window title."""
        if self.title_manager:
            self.title_manager.update_title()
    
    def on_tabs_loaded(self) -> None:
        """Handle tab loading completion."""
        self.loading_widget.hide()
        self.tab_widget.show()
        
        # Hide tab bar if single plugin mode is active
        if getattr(constants, "SINGLE_PLUGIN_MODE", False):
            self.tab_widget.tabBar().hide()

        # Disable batch loading so tab activation/loading can proceed
        self.tab_controller.set_batch_loading(False)

        logger.info("All tabs loaded successfully")
        self._update_window_title()
        
        # Restore last active tab or activate first tab before extension chrome
        # so create_widget wins the UI thread; extensions still always run.
        desired_index = 0 if self.tab_widget.count() > 0 else -1
        if self.settings_service:
            last_active = self.settings_service.get_last_active_tab()
            if last_active:
                # Find index of this tab
                for i in range(self.tab_widget.count()):
                    if self.tab_widget.tabText(i) == last_active:
                        desired_index = i
                        break
        
        if desired_index >= 0:
            if self.tab_widget.currentIndex() == desired_index:
                # If current index is already desired_index, setCurrentIndex won't trigger currentChanged signal,
                # so we manually trigger the tab changed slot to lazy load and activate the tab.
                self.tab_controller.on_tab_changed(desired_index)
            else:
                self.tab_widget.setCurrentIndex(desired_index)
            # Defer extension integration so it does not compete with first-tab create_widget
            QTimer.singleShot(0, lambda: self.plugin_controller.integrate_extensions(self))
        else:
            # No tabs (extension-only setups) — integrate immediately
            self.plugin_controller.integrate_extensions(self)
    
    def on_tab_load_error(self, error_msg: str) -> None:
        """Handle tab loading error."""
        self.tab_controller.set_batch_loading(False)
        self.loading_widget.hide()
        self.tab_widget.show()
        if getattr(constants, "SINGLE_PLUGIN_MODE", False):
            self.tab_widget.tabBar().hide()
        logger.error(f"Error loading tabs: {error_msg}")
        QMessageBox.critical(self, "Error", f"Failed to load tabs: {error_msg}")
    
    def prompt_for_admin_operation(self, operation_description: str) -> bool:
        """Prompt user for admin operation and check if admin is available.
        
        Args:
            operation_description: Description of the operation requiring admin
            
        Returns:
            True if admin is available, False otherwise
        """
        return self.admin_service.prompt_for_admin_operation(operation_description)
    
    def open_plugin_management_dialog(self) -> None:
        """Open the plugin management dialog (non-modal)."""
        if getattr(constants, "SINGLE_PLUGIN_MODE", False):
            return

        from .. import definitions as ui

        if self._plugin_dialog is not None:
            ui.open_dialog(self._plugin_dialog.dialog)
            return

        from ..dialogs.plugin_dialog import PluginManagementDialog
        from ..abstractions.presenters import IDialogPresenter

        controller = PluginManagementDialog(
            self,
            self.settings_service,
            self.plugin_controller,
            self.container.get(IDialogPresenter),
            on_plugin_toggled=self.plugin_controller.toggle_plugin,
        )

        def clear_controller(_accepted: bool) -> None:
            if self._plugin_dialog is controller:
                self._plugin_dialog = None

        self._plugin_dialog = controller
        ui.open_dialog(controller.dialog, on_closed=clear_controller)
    
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

        from .dialogs.theme_dialog import ThemeDialog
        dialog = ThemeDialog(
            theme_manager=self.theme_manager,
            settings_service=self.settings_service,
            parent=self,
        )
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
        from .. import definitions as ui
        from ..abstractions import IUIEventLoop

        if self._log_viewer_dialog is not None:
            ui.open_dialog(self._log_viewer_dialog.dialog)
            return

        from ..dialogs.log_viewer_dialog import LogViewerDialog
        controller = LogViewerDialog(
            parent=self,
            event_loop=self.container.get(IUIEventLoop),
        )

        def clear_controller(_accepted: bool) -> None:
            controller.on_closed()
            if self._log_viewer_dialog is controller:
                self._log_viewer_dialog = None

        self._log_viewer_dialog = controller
        ui.open_dialog(controller.dialog, on_closed=clear_controller)
    
    def show_about_dialog(self) -> None:
        """Show the About dialog without blocking the main window."""
        from ...constants import GUI_API_VERSION as GUI_VERSION, VERSION_NAME as DEFAULT_VERSION_NAME
        from ..dialogs import create_about_dialog
        from .. import definitions as ui
        
        if self._about_dialog is not None:
            ui.open_dialog(self._about_dialog.dialog)
            return

        has_external_constants = VERSION_NAME != DEFAULT_VERSION_NAME
        controller = create_about_dialog(
            self,
            app_name=VERSION_NAME,
            app_version=VERSION if has_external_constants else None,
            gui_api_version=GUI_VERSION,
            platform_name=CURRENT_PLATFORM,
        )

        def clear_controller(_accepted: bool) -> None:
            if self._about_dialog is controller:
                self._about_dialog = None

        self._about_dialog = controller
        ui.open_dialog(controller.dialog, on_closed=clear_controller)
    
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
        self.plugin_service.publish_event("theme_changed", {"theme": theme_name})

    
    def restart_as_admin(self) -> None:
        """Restart the application with administrator/root privileges.
        
        On Windows: Restarts the entire application as administrator.
        On Linux: Starts the privileged daemon (GUI continues running as normal user).
        """
        try:
            success, error_msg = self.admin_service.restart_as_admin()
            
            if CURRENT_PLATFORM == "linux":
                if success:
                    self.toast_manager.show_success("Privileged daemon started successfully")
                    if self.menu_controller:
                        self.menu_controller.update_admin_menu()
                else:
                    detail = error_msg or (
                        "Could not start the privileged daemon. "
                        "Approve the pkexec/sudo prompt and check logs."
                    )
                    self.toast_manager.show_error(f"Failed to start daemon: {detail}")
            elif CURRENT_PLATFORM != "windows":
                if not success:
                    self.toast_manager.show_warning(
                        f"Not supported or failed: {error_msg}"
                    )
        except Exception as e:
            logger.error(f"Failed to restart as administrator: {e}")
            if CURRENT_PLATFORM == "linux":
                self.toast_manager.show_error(f"Failed to start privileged daemon: {e}")
            else:
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
        from ...utils.display_utils import get_other_platforms_text
        other_text = get_other_platforms_text()
        
        # Reload plugins with the new cross-platform setting applied.
        self.reload_plugins()
        
        if enabled:
            self.toast_manager.show_info(
                f"Loading tabs from {other_text}... Some features may not work on this platform."
            )
        else:
            self.toast_manager.show_info(f"Removed tabs from {other_text}")
    
    def reload_plugins(self) -> None:
        """Reload all plugins and tabs.
        
        This clears the plugin registry and re-discovers all plugins,
        then reloads the tabs. Used when toggling cross-platform tabs.
        """
        logger.info("Reloading all plugins...")
        
        # Clean up all previously integrated extensions before clearing registry
        # This prevents duplicate menu items, toolbar actions, and status widgets
        # and ensures ServiceExtension plugins are properly shut down
        self.plugin_controller.cleanup_all_extensions()
        
        # Clear all tabs, closing and deleting their widgets
        self.tab_controller.clear_all_tabs()
        
        # Clear plugin registry
        self.container.get(PluginService).clear()
        
        # Show loading state
        self.tab_widget.hide()
        self.loading_widget.show()
        
        # Re-run tab loader
        self._start_tab_loader()

    def setup_toast_manager(self) -> None:
        """Setup the toast notification manager."""
        from .controllers.toast_manager import ToastManager
        from ...services.interfaces import INotificationService
        self.toast_manager = ToastManager(
            theme_manager=self.theme_manager,
            notification_service=self.container.get(INotificationService),
            parent_widget=self,
        )
    
    def setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        if not self.settings_service or not self.settings_service.get_shortcuts_enabled():
            return
        
        from .controllers.shortcut_manager import ShortcutManager
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
            self.tab_controller.close_tab_by_index(current)
    
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
            
        # Cleanly close and destroy all tabs to trigger their closeEvents and stop threads/timers
        self.tab_controller.clear_all_tabs()

        # Shutdown ServiceExtension plugins
        self.plugin_controller.shutdown_service_extensions()
        
        # PERF: Explicitly close and release dialog references to free their widget trees
        # immediately, rather than relying on async destroyed signal lambdas.
        for dlg_attr in ('_theme_dialog', '_plugin_dialog', '_log_viewer_dialog', '_about_dialog'):
            dlg = getattr(self, dlg_attr, None)
            if dlg is not None:
                try:
                    dlg.close()
                except Exception:
                    pass
                setattr(self, dlg_attr, None)
        
        # PERF: Shut down the plugin service's ThreadPoolExecutor so worker threads
        # are joined on app exit, not just during plugin reload.
        try:
            self.plugin_service.shutdown_event_executor()
        except Exception:
            pass
        
        event.accept()
    
    
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
            

    # =========================================================================
    # IMainWindowShell — tabs, toast, notifications, handle-based chrome
    # =========================================================================

    def has_plugin_tab(self, plugin_name: str) -> bool:
        return plugin_name in self.tab_controller.loaded_tabs

    def add_plugin_tab(self, plugin_name: str, plugin_class: type) -> None:
        self.tab_controller.add_tab(plugin_name, plugin_class)

    def remove_plugin_tab(self, plugin_name: str) -> None:
        self.tab_controller.remove_tab(plugin_name)

    def clear_tabs_for_plugins(self, plugin_names: List[str]) -> None:
        self.tab_controller.clear_tabs_for_plugins(plugin_names)

    def show_toast(
        self,
        message: str,
        notification_type: ToastType = ToastType.INFO,
        duration: Optional[int] = None,
    ) -> None:
        if self.toast_manager:
            method = getattr(self.toast_manager, f"show_{notification_type.value}", None)
            if callable(method):
                if duration is not None:
                    method(message, duration)
                else:
                    method(message)
            else:
                self.toast_manager.show_toast(
                    message, notification_type.value, duration or 3000
                )

    def on_notification_added(self, notification: Notification) -> None:
        """Display a toast for notifications not already shown by ToastManager."""
        if not self.toast_manager:
            return
        if getattr(self.toast_manager, "_suppress_bridge_display", False):
            return
        self.toast_manager.display_toast(
            notification.message,
            notification.type.value,
        )

    def on_unread_count_changed(self, count: int) -> None:
        if self.status_bar_manager:
            self.status_bar_manager._update_unread_count(count)

    def add_menu_item(self, spec: MenuItemSpec) -> MenuItemHandle:
        from .shell_chrome import add_menu_action

        handle = MenuItemHandle(str(uuid.uuid4()))
        action, target_menu, was_created, sep_before, sep_after = add_menu_action(
            self,
            menu_title=spec.menu,
            label=spec.label,
            callback=spec.callback,
            shortcut=spec.shortcut,
            icon=spec.icon,
            enabled=spec.enabled,
            separator_before=spec.separator_before,
            separator_after=spec.separator_after,
        )
        self._menu_handle_map[handle] = (action, target_menu, sep_before, sep_after)
        if was_created:
            self._created_menu_titles.add(spec.menu)
        return handle

    def remove_menu_item(self, handle: MenuItemHandle) -> None:
        from .shell_chrome import remove_menu_action

        entry = self._menu_handle_map.pop(handle, None)
        if not entry:
            return
        action, target_menu, sep_before, sep_after = entry
        for item in (sep_before, action, sep_after):
            if item is not None:
                remove_menu_action(item, target_menu)

    def remove_menu_if_empty(self, menu_title: str) -> None:
        from .shell_chrome import remove_qmenu_if_empty

        menu_bar = self.menuBar()
        for action in menu_bar.actions():
            try:
                menu = action.menu()
            except Exception:
                continue
            if action.text().replace("&", "") == menu_title:
                remove_qmenu_if_empty(self, menu)
                break

    def add_status_widget_for_plugin(self, plugin_name: str, plugin_instance: Any) -> StatusWidgetHandle:
        widget = plugin_instance.create_status_widget(self.statusBar())
        handle = StatusWidgetHandle(str(uuid.uuid4()))
        if widget:
            self.statusBar().addPermanentWidget(widget)
            self._status_handle_map[handle] = widget
        return handle

    def remove_status_widget(self, handle: StatusWidgetHandle) -> None:
        from .shell_chrome import remove_status_widget

        widget = self._status_handle_map.pop(handle, None)
        if widget is not None:
            remove_status_widget(self, widget)

    def add_toolbar_action(self, spec: ToolbarActionSpec) -> ToolbarActionHandle:
        from .shell_chrome import add_toolbar_action, get_or_create_plugin_toolbar

        handle = ToolbarActionHandle(str(uuid.uuid4()))
        self._plugin_toolbar = get_or_create_plugin_toolbar(self, self._plugin_toolbar)
        action = add_toolbar_action(
            self,
            self._plugin_toolbar,
            label=spec.label,
            callback=spec.callback,
            icon=spec.icon,
            tooltip=spec.tooltip,
            checkable=spec.checkable,
            checked=spec.checked,
        )
        self._toolbar_handle_map[handle] = action
        return handle

    def remove_toolbar_action(self, handle: ToolbarActionHandle) -> None:
        from .shell_chrome import remove_toolbar_action

        action = self._toolbar_handle_map.pop(handle, None)
        if action is not None:
            remove_toolbar_action(self._plugin_toolbar, action)


__all__ = ['MainWindow']
