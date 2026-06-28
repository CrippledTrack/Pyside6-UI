"""Admin/elevation service for managing privileged operations.

This module provides a centralized service for checking admin status,
handling elevation prompts, and managing platform-specific admin logic
across Windows and Linux systems.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..constants import CURRENT_PLATFORM

if TYPE_CHECKING:
    from ..qt_bindings import QWidget

logger = logging.getLogger(__name__)


class AdminService:
    """Base class and factory for managing admin/elevation status and operations."""
    
    def __new__(cls, daemon_service: Optional[Any] = None) -> AdminService:
        # Factory behavior: return the platform-specific subclass if instantiating the base class
        if cls is AdminService:
            if CURRENT_PLATFORM == "windows":
                return super().__new__(WindowsAdminService)
            elif CURRENT_PLATFORM == "linux":
                return super().__new__(LinuxAdminService)
            else:
                return super().__new__(FallbackAdminService)
        return super().__new__(cls)

    def __init__(self, daemon_service: Optional[Any] = None):
        """Initialize the admin service.
        
        Args:
            daemon_service: Optional daemon service instance
        """
        if hasattr(self, "_initialized") and self._initialized:
            return
            
        self._daemon_service = daemon_service
        self._is_admin: Optional[bool] = None
        self._check_admin_status()
        self._initialized = True

    def _check_admin_status(self) -> None:
        """Check and cache admin status for the current platform."""
        raise NotImplementedError("Subclasses must implement _check_admin_status")

    def is_admin(self) -> bool:
        """Check if the application is running with admin privileges.
        
        Returns:
            True if running as admin/root, False otherwise
        """
        if self._is_admin is None:
            self._check_admin_status()
        return self._is_admin or False

    def get_sudo_status(self) -> Optional[Dict[str, Any]]:
        """Get Linux sudo status information.
        
        Returns:
            Dictionary with sudo status info, or None if not on Linux
        """
        return None

    def prompt_for_admin_operation(
        self, 
        operation_description: str, 
        parent_widget: Optional["QWidget"] = None
    ) -> bool:
        """Prompt user for admin operation and check if admin is available.
        
        Args:
            operation_description: Description of the operation requiring admin
            parent_widget: Optional parent widget for dialogs
            
        Returns:
            True if admin is available, False otherwise
        """
        if self.is_admin():
            return True
        return False

    def restart_as_admin(self) -> tuple[bool, Optional[str]]:
        """Restart the application with administrator/root privileges.
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        return False, f"Admin elevation not supported on {CURRENT_PLATFORM}"

    def needs_admin_for_plugin(self, requires_admin: bool) -> bool:
        """Determine whether admin privileges are required for a plugin."""
        raise NotImplementedError("Subclasses must implement needs_admin_for_plugin")


class WindowsAdminService(AdminService):
    """Windows-specific implementation of AdminService."""
    
    def _check_admin_status(self) -> None:
        """Check and handle Windows admin status."""
        from ..utils.elevation_windows import is_admin as _is_admin_windows
        self._is_admin = _is_admin_windows()
        if self._is_admin:
            logger.info("Application running with admin privileges")
            return
        
        # Check if admin is required by default
        from ..utils.imports import get_platforms_constants
        constants = get_platforms_constants()
        require_admin_by_default = getattr(constants, "REQUIRE_ADMIN_BY_DEFAULT", False)
        
        if require_admin_by_default:
            try:
                logger.warning("Attempting to restart with elevated rights...")
                from ..utils.elevation_windows import run_as_admin
                run_as_admin()
            except Exception as e:
                logger.warning(f"Elevation denied or failed ({e}); continuing without admin.")
            self._is_admin = _is_admin_windows()
            if not self._is_admin:
                logger.info("Continuing without admin privileges. Some operations will be disabled until elevated.")
        else:
            logger.info("Running without admin privileges by default. Some operations will be disabled until elevated.")

    def prompt_for_admin_operation(
        self, 
        operation_description: str, 
        parent_widget: Optional["QWidget"] = None
    ) -> bool:
        """Prompt user for admin operation on Windows."""
        if self.is_admin():
            return True
            
        if parent_widget:
            from ..qt_bindings import QMessageBox
            QMessageBox.warning(
                parent_widget,
                "Admin Privileges Required",
                f"{operation_description} requires administrator privileges.\n"
                "Please restart the application as administrator.",
            )
        return False

    def restart_as_admin(self) -> tuple[bool, Optional[str]]:
        """Restart the application as administrator on Windows."""
        try:
            from ..utils.elevation_windows import run_as_admin
            run_as_admin()
            return True, None
        except Exception as e:
            return False, str(e)

    def needs_admin_for_plugin(self, requires_admin: bool) -> bool:
        """Determine whether admin privileges are required for a plugin on Windows."""
        from ..utils.admin import is_dev_mode
        if is_dev_mode():
            return False
        
        if not requires_admin:
            return False
            
        return not self.is_admin()


class LinuxAdminService(AdminService):
    """Linux-specific implementation of AdminService."""
    
    def __init__(self, daemon_service: Optional[Any] = None):
        self._sudo_status: Optional[Dict[str, Any]] = None
        super().__init__(daemon_service)

    def _check_admin_status(self) -> None:
        """Check and handle Linux admin status."""
        from ..utils.elevation_linux import get_sudo_status
        self._sudo_status = get_sudo_status()
        self._is_admin = self._sudo_status["is_admin"]
        if self._is_admin:
            logger.info("Application running with admin/root privileges")
        else:
            logger.info(f"Application running as user '{self._sudo_status['current_user']}'")
            if self._sudo_status["sudo_available"]:
                logger.info("Sudo is available - operations requiring root will prompt for password")
            else:
                logger.warning("Sudo not available - some operations may not work")

    def get_sudo_status(self) -> Optional[Dict[str, Any]]:
        """Get Linux sudo status information."""
        if self._sudo_status is None:
            self._check_admin_status()
        return self._sudo_status

    def prompt_for_admin_operation(
        self, 
        operation_description: str, 
        parent_widget: Optional["QWidget"] = None
    ) -> bool:
        """Prompt user for admin operation on Linux."""
        if self.is_admin():
            return True
            
        # On Linux, check if daemon is available
        if self._daemon_service and self._daemon_service.is_available():
            return True
            
        if parent_widget:
            from ..qt_bindings import QMessageBox
            QMessageBox.warning(
                parent_widget,
                "Privileged Daemon Required",
                f"{operation_description} requires administrator privileges.\n"
                "The privileged daemon is not running.\n"
                "Please start it from the Admin menu to use this feature.",
            )
        return False

    def restart_as_admin(self) -> tuple[bool, Optional[str]]:
        """Start the privileged daemon on Linux."""
        if self._daemon_service:
            return self._daemon_service.start()
        return False, "Daemon service not available"

    def needs_admin_for_plugin(self, requires_admin: bool) -> bool:
        """Determine whether admin privileges are required for a plugin on Linux."""
        from ..utils.admin import is_dev_mode
        if is_dev_mode():
            return False
            
        if not requires_admin:
            return False
            
        if self.is_admin():
            return False
            
        # Check daemon availability
        if self._daemon_service and self._daemon_service.is_available():
            return False
            
        # As fallback, check the daemon module function if daemon_service is not wired/available yet
        try:
            from ..daemon import is_daemon_available
            return not is_daemon_available()
        except Exception:
            return True


class FallbackAdminService(AdminService):
    """Fallback implementation of AdminService for other platforms."""
    
    def _check_admin_status(self) -> None:
        logger.warning(f"Unsupported platform: {CURRENT_PLATFORM}")
        self._is_admin = False

    def prompt_for_admin_operation(
        self, 
        operation_description: str, 
        parent_widget: Optional["QWidget"] = None
    ) -> bool:
        if self.is_admin():
            return True
            
        if parent_widget:
            from ..qt_bindings import QMessageBox
            reply = QMessageBox.question(
                parent_widget,
                "Admin Privileges Required",
                f"{operation_description} requires root privileges.\n"
                "The application will prompt for your password when needed.\n\n"
                "Do you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            return reply == QMessageBox.StandardButton.Yes
        return False

    def needs_admin_for_plugin(self, requires_admin: bool) -> bool:
        """Determine whether admin privileges are required for a plugin on other platforms."""
        from ..utils.admin import is_dev_mode
        if is_dev_mode():
            return False
            
        if not requires_admin:
            return False
            
        return not self.is_admin()


__all__ = [
    'AdminService',
    'WindowsAdminService',
    'LinuxAdminService',
    'FallbackAdminService',
]
