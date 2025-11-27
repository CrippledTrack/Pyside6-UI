"""
Menu bar controller.

This module provides MenuBarController to handle menu bar creation,
state management, and menu item updates, extracted from MainWindow.
"""

from __future__ import annotations

import logging
import platform
from typing import Optional, Callable, TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenuBar, QMenu, QWidget

if TYPE_CHECKING:
    from ...services.interfaces import IAdminService, IDaemonService, ISettingsService

logger = logging.getLogger(__name__)

CURRENT_PLATFORM = platform.system().lower()


class MenuBarController(QObject):
    """Controller for managing menu bar and menu items."""
    
    # Signal emitted when cross-platform tabs toggle changes
    cross_platform_toggled = Signal(bool)
    
    def __init__(
        self,
        menu_bar: QMenuBar,
        admin_service: Optional["IAdminService"] = None,
        daemon_service: Optional["IDaemonService"] = None,
        settings_service: Optional[Any] = None,
        parent_widget: Optional[QWidget] = None
    ) -> None:
        """Initialize the menu bar controller.
        
        Args:
            menu_bar: The menu bar widget to manage
            admin_service: Optional admin service for checking privileges
            daemon_service: Optional daemon service (for Linux)
            settings_service: Optional settings service for tooltips
            parent_widget: Optional parent widget for menu items
        """
        super().__init__(parent_widget)
        self.menu_bar = menu_bar
        self.admin_service = admin_service
        self.daemon_service = daemon_service
        self.settings_service = settings_service
        self.parent_widget = parent_widget
        
        # Menu actions (stored for state management)
        self.manage_plugins_action: Optional[QAction] = None
        self.select_theme_action: Optional[QAction] = None
        self.restart_admin_action: Optional[QAction] = None
        self.show_all_platforms_action: Optional[QAction] = None
    
    def setup(
        self,
        on_manage_plugins: Callable[[], None],
        on_select_theme: Callable[[], None],
        on_restart_admin: Callable[[], None]
    ) -> None:
        """Setup the menu bar with all menus and actions.
        
        Args:
            on_manage_plugins: Callback for manage plugins action
            on_select_theme: Callback for select theme action
            on_restart_admin: Callback for restart admin action
        """
        self._create_settings_menu(on_manage_plugins, on_select_theme)
        self._create_admin_menu(on_restart_admin)
        self._create_dev_menu()
        self._setup_tooltips()
        logger.debug("Menu bar setup complete")
    
    def _create_settings_menu(
        self,
        on_manage_plugins: Callable[[], None],
        on_select_theme: Callable[[], None]
    ) -> None:
        """Create the Settings menu with plugin and theme options.
        
        Args:
            on_manage_plugins: Callback for manage plugins action
            on_select_theme: Callback for select theme action
        """
        settings_menu = QMenu("Settings", self.parent_widget)
        self.menu_bar.addMenu(settings_menu)
        
        self.manage_plugins_action = QAction("Manage Plugins...", self.parent_widget)
        settings_menu.addAction(self.manage_plugins_action)
        self.manage_plugins_action.triggered.connect(on_manage_plugins)
        
        self.select_theme_action = QAction("Select Theme...", self.parent_widget)
        settings_menu.addAction(self.select_theme_action)
        self.select_theme_action.triggered.connect(on_select_theme)
        
        settings_menu.addSeparator()
        logger.debug("Settings menu created")
    
    def _create_admin_menu(self, on_restart_admin: Callable[[], None]) -> None:
        """Create the Admin menu if needed.
        
        Args:
            on_restart_admin: Callback for restart admin action
            
        Note:
            On Windows: Shows when not running as administrator.
            On Linux: Always shows to allow starting the daemon.
        """
        should_show = False
        if CURRENT_PLATFORM == "windows":
            if self.admin_service:
                should_show = not self.admin_service.is_admin()
            else:
                should_show = True
        elif CURRENT_PLATFORM == "linux":
            # On Linux, always show the menu to allow starting the daemon
            should_show = True
        
        if should_show:
            admin_menu = QMenu("Admin", self.parent_widget)
            self.menu_bar.addMenu(admin_menu)
            
            # Platform-specific menu text
            if CURRENT_PLATFORM == "linux":
                # Check if daemon is already running
                if self.daemon_service and self.daemon_service.is_available():
                    action_text = "Daemon Running"
                    tooltip_text = "The privileged daemon is currently running"
                    enabled = False
                else:
                    action_text = "Start Privileged Daemon"
                    tooltip_text = "Start the privileged daemon for root operations"
                    enabled = True
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
        
        # Platform name for menu item
        other_platform = "Windows" if CURRENT_PLATFORM == "linux" else "Linux"
        
        self.show_all_platforms_action = QAction(f"Show {other_platform} Tabs", self.parent_widget)
        self.show_all_platforms_action.setCheckable(True)
        self.show_all_platforms_action.setChecked(is_show_all_platforms())
        self.show_all_platforms_action.setToolTip(
            f"Show tabs from {other_platform} for testing purposes. "
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
    
    def update_admin_menu(self) -> None:
        """Update the admin menu based on current state.
        
        This method is called when admin/daemon status changes to refresh
        the admin menu appearance and state.
        """
        if not self.restart_admin_action:
            return
        
        if CURRENT_PLATFORM == "linux":
            if self.daemon_service and self.daemon_service.is_available():
                self.restart_admin_action.setText("Daemon Running")
                self.restart_admin_action.setEnabled(False)
                self.restart_admin_action.setToolTip(
                    "The privileged daemon is currently running"
                )
                logger.debug("Admin menu updated: daemon running")
            else:
                self.restart_admin_action.setText("Start Privileged Daemon")
                self.restart_admin_action.setEnabled(True)
                self.restart_admin_action.setToolTip(
                    "Start the privileged daemon for root operations"
                )
                logger.debug("Admin menu updated: daemon not running")


__all__ = ['MenuBarController']

