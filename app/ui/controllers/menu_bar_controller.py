"""
Menu bar controller.

This module provides MenuBarController to handle menu bar creation,
state management, and menu item updates, extracted from MainWindow.
"""

from __future__ import annotations

import logging
from typing import Optional, Callable, TYPE_CHECKING, Any

from ...qt_bindings import QObject, Signal, QAction, QMenuBar, QMenu, QWidget

from ...constants import CURRENT_PLATFORM

if TYPE_CHECKING:
    from ...services.container import ServiceContainer

logger = logging.getLogger(__name__)


class MenuBarController(QObject):
    """Controller for managing menu bar and menu items."""
    
    # Signal emitted when cross-platform tabs toggle changes
    cross_platform_toggled = Signal(bool)
    
    def __init__(
        self,
        menu_bar: QMenuBar,
        container: "ServiceContainer",
        parent_widget: Optional[QWidget] = None
    ) -> None:
        """Initialize the menu bar controller.
        
        Args:
            menu_bar: The menu bar widget to manage
            container: Service container for dependency injection
            parent_widget: Optional parent widget for menu items
        """
        super().__init__(parent_widget)
        self.menu_bar = menu_bar
        self.container = container
        self.parent_widget = parent_widget
        
        # Retrieve services from container
        from ...services.admin_service import AdminService
        from ...services.daemon_service import DaemonService
        from ...services.settings_service import SettingsService
        
        self.admin_service = container.get(AdminService)
        self.daemon_service = container.get(DaemonService) if CURRENT_PLATFORM == "linux" else None
        self.settings_service = container.get(SettingsService)
        
        # Menu actions (stored for state management)
        self.manage_plugins_action: Optional[QAction] = None
        self.select_theme_action: Optional[QAction] = None
        self.toggle_new_ui_action: Optional[QAction] = None
        self.restart_admin_action: Optional[QAction] = None
        self.start_pipe_daemon_action: Optional[QAction] = None
        self.show_all_platforms_action: Optional[QAction] = None
        self.view_logs_action: Optional[QAction] = None
        self.about_action: Optional[QAction] = None
    
    def setup(
        self,
        on_manage_plugins: Callable[[], None],
        on_select_theme: Callable[[], None],
        on_restart_admin: Callable[[], None],
        on_view_logs: Optional[Callable[[], None]] = None,
        on_about: Optional[Callable[[], None]] = None,
        on_toggle_new_ui: Optional[Callable[[], None]] = None,
        on_start_pipe_daemon: Optional[Callable[[], None]] = None
    ) -> None:
        """Setup the menu bar with all menus and actions.
        
        Args:
            on_manage_plugins: Callback for manage plugins action
            on_select_theme: Callback for select theme action
            on_restart_admin: Callback for restart admin action
            on_view_logs: Optional callback for view logs action
            on_about: Optional callback for about action
            on_toggle_new_ui: Optional callback for toggle new UI action
            on_start_pipe_daemon: Optional callback for starting pipe daemon
        """
        self._create_settings_menu(on_manage_plugins, on_select_theme, on_toggle_new_ui)
        self._create_admin_menu(on_restart_admin, on_start_pipe_daemon)
        self._create_dev_menu()
        self._create_help_menu(on_view_logs, on_about)
        self._setup_tooltips()
        logger.debug("Menu bar setup complete")
    
    def _create_settings_menu(
        self,
        on_manage_plugins: Callable[[], None],
        on_select_theme: Callable[[], None],
        on_toggle_new_ui: Optional[Callable[[], None]] = None
    ) -> None:
        """Create the Settings menu with plugin and theme options.
        
        Args:
            on_manage_plugins: Callback for manage plugins action
            on_select_theme: Callback for select theme action
            on_toggle_new_ui: Optional callback for toggle new UI action
        """
        settings_menu = QMenu("Settings", self.parent_widget)
        self.menu_bar.addMenu(settings_menu)
        
        self.manage_plugins_action = QAction("Manage Plugins...", self.parent_widget)
        settings_menu.addAction(self.manage_plugins_action)
        self.manage_plugins_action.triggered.connect(on_manage_plugins)
        
        self.select_theme_action = QAction("Select Theme...", self.parent_widget)
        settings_menu.addAction(self.select_theme_action)
        self.select_theme_action.triggered.connect(on_select_theme)
        
        # Note: UI toggle has been moved to the theme dialog
        # Keeping the action reference for backward compatibility but not adding to menu
        
        logger.debug("Settings menu created")
    
    def _update_new_ui_action_text(self) -> None:
        """Update the new UI toggle action text based on current state."""
        if self.toggle_new_ui_action and self.settings_service:
            is_enabled = self.settings_service.get_new_ui_enabled()
            self.toggle_new_ui_action.setText("Enable New UI" if not is_enabled else "Disable New UI")
            self.toggle_new_ui_action.setToolTip(
                "Toggle the new UI overhaul features. Requires application restart to take full effect."
            )
    
    def update_new_ui_action(self) -> None:
        """Update the new UI toggle action state."""
        if self.toggle_new_ui_action and self.settings_service:
            # Block signals temporarily to avoid triggering the callback
            self.toggle_new_ui_action.blockSignals(True)
            self.toggle_new_ui_action.setChecked(self.settings_service.get_new_ui_enabled())
            self._update_new_ui_action_text()
            self.toggle_new_ui_action.blockSignals(False)
    
    def _create_admin_menu(
        self,
        on_restart_admin: Callable[[], None],
        on_start_pipe_daemon: Optional[Callable[[], None]] = None
    ) -> None:
        """Create the Admin menu if needed.
        
        Args:
            on_restart_admin: Callback for restart admin action
            on_start_pipe_daemon: Optional callback for starting pipe daemon
            
        Note:
            On Windows: Shows when not running as administrator.
            On Linux: Always shows to allow starting the daemon.
        """
        # Allow hiding the Admin menu/button (e.g., kiosk/demo mode)
        force_show_for_dev = False
        try:
            # In dev mode, always show the Admin menu (temporary override)
            from ...utils.admin import is_dev_mode
            dev_mode_active = bool(is_dev_mode())

            if self.settings_service and self.settings_service.get_hide_admin_menu() and not dev_mode_active:
                logger.debug("Admin menu hidden by settings (hide_admin_menu=true)")
                return
            if self.settings_service and self.settings_service.get_hide_admin_menu() and dev_mode_active:
                logger.debug("Dev mode active - overriding hide_admin_menu to show Admin menu")
                force_show_for_dev = True
        except Exception:
            # Fail open: if settings are unavailable, keep existing behavior
            pass

        should_show = False
        if CURRENT_PLATFORM == "windows":
            if self.admin_service:
                should_show = not self.admin_service.is_admin()
            else:
                should_show = True
        elif CURRENT_PLATFORM == "linux":
            # On Linux, always show the menu to allow starting the daemon
            should_show = True

        if force_show_for_dev:
            should_show = True

        if should_show:
            admin_menu = QMenu("Admin", self.parent_widget)
            self.menu_bar.addMenu(admin_menu)
            
            # Platform-specific menu text
            if CURRENT_PLATFORM == "linux":
                # Check if daemon is already running
                is_running = self.daemon_service and self.daemon_service.is_available()
                
                # Check which daemon is active
                from ...utils.imports import get_platforms_constants
                use_pipe_daemon = getattr(get_platforms_constants(), 'USE_PIPE_DAEMON', False)
                
                if is_running:
                    if use_pipe_daemon:
                        action_text = "Pipe Daemon Running (Beta)"
                    else:
                        action_text = "Daemon Running"
                    tooltip_text = "The privileged daemon is currently running"
                    enabled = False
                else:
                    action_text = "Start Privileged Daemon"
                    tooltip_text = "Start the privileged daemon for root operations"
                    enabled = True
                
                self.restart_admin_action = QAction(action_text, self.parent_widget)
                self.restart_admin_action.setToolTip(tooltip_text)
                self.restart_admin_action.setEnabled(enabled)
                self.restart_admin_action.triggered.connect(on_restart_admin)
                admin_menu.addAction(self.restart_admin_action)
                
                # Add Pipe Daemon action
                self.start_pipe_daemon_action = QAction("Start Pipe Daemon (Beta)", self.parent_widget)
                self.start_pipe_daemon_action.setToolTip("Start the experimental pipe-based daemon")
                self.start_pipe_daemon_action.setEnabled(not is_running)
                if on_start_pipe_daemon:
                    self.start_pipe_daemon_action.triggered.connect(on_start_pipe_daemon)
                admin_menu.addAction(self.start_pipe_daemon_action)
            else:
                action_text = "Restart as Administrator"
                tooltip_text = "Restart the application with administrator privileges"
                enabled = True
                
                self.restart_admin_action = QAction(action_text, self.parent_widget)
                self.restart_admin_action.setToolTip(tooltip_text)
                self.restart_admin_action.setEnabled(enabled)
                self.restart_admin_action.triggered.connect(on_restart_admin)
                admin_menu.addAction(self.restart_admin_action)
                
            logger.debug(f"Admin menu created (platform: {CURRENT_PLATFORM})")
    
    def _create_dev_menu(self) -> None:
        """Create the Dev menu if in dev mode.
        
        This menu provides developer-only options for testing and debugging.
        Only shown when the application is started with -dev or --dev flag.
        """
        try:
            from ...utils.admin import is_dev_mode, set_show_all_platforms, is_show_all_platforms
        except ImportError:
            logger.debug("Dev mode utilities not available, skipping dev menu")
            return
        
        if not is_dev_mode():
            return
        
        dev_menu = QMenu("Dev", self.parent_widget)
        self.menu_bar.addMenu(dev_menu)
        
        # Menu text now reflects that we load tabs from *all* other platforms,
        # not just a single opposite platform.
        self.show_all_platforms_action = QAction("Show All Platform Tabs", self.parent_widget)
        self.show_all_platforms_action.setCheckable(True)
        self.show_all_platforms_action.setChecked(is_show_all_platforms())
        
        # Build a human-readable list of other platforms for the tooltip
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
        
        self.show_all_platforms_action.setToolTip(
            f"Show tabs from {other_text} for testing purposes. "
            "Requires application restart to take effect."
        )
        self.show_all_platforms_action.triggered.connect(self._on_show_all_platforms_toggled)
        dev_menu.addAction(self.show_all_platforms_action)
        
        logger.debug("Dev menu created")
    
    def _on_show_all_platforms_toggled(self, checked: bool) -> None:
        """Handle show all platforms toggle.
        
        Args:
            checked: True if the action is checked, False otherwise
        """
        try:
            from ...utils.admin import set_show_all_platforms
            set_show_all_platforms(checked)
            self.cross_platform_toggled.emit(checked)
            logger.info(f"Show all platforms set to: {checked}")
        except ImportError:
            logger.warning("Could not import set_show_all_platforms")
    
    def _create_help_menu(
        self,
        on_view_logs: Optional[Callable[[], None]] = None,
        on_about: Optional[Callable[[], None]] = None
    ) -> None:
        """Create the Help menu.
        
        Args:
            on_view_logs: Optional callback for view logs action
            on_about: Optional callback for about action
        """
        help_menu = QMenu("Help", self.parent_widget)
        self.menu_bar.addMenu(help_menu)
        
        # View Logs action
        self.view_logs_action = QAction("View Logs...", self.parent_widget)
        self.view_logs_action.setToolTip("Open the log viewer to see application logs")
        if on_view_logs:
            self.view_logs_action.triggered.connect(on_view_logs)
        help_menu.addAction(self.view_logs_action)
        
        help_menu.addSeparator()
        
        # About action
        self.about_action = QAction("About...", self.parent_widget)
        self.about_action.setToolTip("Show information about this application")

        if on_about:
            self.about_action.triggered.connect(on_about)
        help_menu.addAction(self.about_action)
        
        logger.debug("Help menu created")
    
    def _setup_tooltips(self) -> None:
        """Setup tooltips for menu actions."""
        if not self.settings_service or not self.settings_service.get_show_tooltips():
            return
        
        if self.manage_plugins_action:
            self.manage_plugins_action.setToolTip(
                "Enable or disable plugins and manage their settings"
            )
        if self.select_theme_action:
            self.select_theme_action.setToolTip(
                "Choose from available themes or import custom ones"
            )
        
        if self.restart_admin_action:
            # Update tooltip based on platform
            if CURRENT_PLATFORM == "linux":
                self.restart_admin_action.setToolTip(
                    "Start the privileged daemon for root operations"
                )
            else:
                self.restart_admin_action.setToolTip(
                    "Restart the application with administrator privileges"
                )

    def refresh_for_theme_change(self) -> None:
        """Force menu bar widgets to re-polish after theme changes."""
        if not self.menu_bar:
            return
        
        try:
            style = self.menu_bar.style()
            style.unpolish(self.menu_bar)
            style.polish(self.menu_bar)
            self.menu_bar.updateGeometry()
            self.menu_bar.update()
        except Exception:
            pass
    
    def update_admin_menu(self) -> None:
        """Update the admin menu based on current state.
        
        This method is called when admin/daemon status changes to refresh
        the admin menu appearance and state.
        """
        if not self.restart_admin_action:
            return
        
        if CURRENT_PLATFORM == "linux":
            if self.daemon_service and self.daemon_service.is_available():
                from ...utils.imports import get_platforms_constants
                use_pipe_daemon = getattr(get_platforms_constants(), 'USE_PIPE_DAEMON', False)
                if use_pipe_daemon:
                    self.restart_admin_action.setText("Pipe Daemon Running (Beta)")
                else:
                    self.restart_admin_action.setText("Daemon Running")
                self.restart_admin_action.setEnabled(False)
                self.restart_admin_action.setToolTip(
                    "The privileged daemon is currently running"
                )
                if self.start_pipe_daemon_action:
                    self.start_pipe_daemon_action.setEnabled(False)
                    self.start_pipe_daemon_action.setToolTip(
                        "The privileged daemon is currently running"
                    )
                logger.debug("Admin menu updated: daemon running")
            else:
                self.restart_admin_action.setText("Start Privileged Daemon")
                self.restart_admin_action.setEnabled(True)
                self.restart_admin_action.setToolTip(
                    "Start the privileged daemon for root operations"
                )
                if self.start_pipe_daemon_action:
                    self.start_pipe_daemon_action.setEnabled(True)
                    self.start_pipe_daemon_action.setToolTip(
                        "Start the experimental pipe-based daemon"
                    )
                logger.debug("Admin menu updated: daemon not running")


__all__ = ['MenuBarController']

