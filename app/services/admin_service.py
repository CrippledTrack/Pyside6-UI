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

if CURRENT_PLATFORM == "windows":
    from ..utils.elevation_windows import is_admin as _is_admin_windows, run_as_admin
elif CURRENT_PLATFORM == "linux":
    from ..utils.elevation_linux import get_sudo_status, is_admin as _is_admin_linux, run_as_admin
else:
    # Dummy functions for unsupported platforms
    def _is_admin_windows() -> bool:
        return False
    
    def _is_admin_linux() -> bool:
        return False
    
    def get_sudo_status() -> Dict[str, Any]:
        return {"is_admin": False, "current_user": "unknown", "sudo_available": False}
    
    def run_as_admin() -> None:
        raise RuntimeError("Admin elevation not supported on this platform")


class AdminService:
    """Service for managing admin/elevation status and operations."""
    
    def __init__(self, daemon_service: Optional[Any] = None):
        """Initialize the admin service.
        
        Args:
            daemon_service: Optional daemon service instance (for Linux)
        """
        self._daemon_service = daemon_service
        self._is_admin: Optional[bool] = None
        self._sudo_status: Optional[Dict[str, Any]] = None
        self._check_admin_status()
    
    def _check_admin_status(self) -> None:
        """Check and cache admin status for the current platform."""
        if CURRENT_PLATFORM == "windows":
            self._check_windows_admin_status()
        elif CURRENT_PLATFORM == "linux":
            self._check_linux_admin_status()
        else:
            logger.warning(f"Unsupported platform: {CURRENT_PLATFORM}")
            self._is_admin = False
    
    def _check_windows_admin_status(self) -> None:
        """Check and handle Windows admin status."""
        self._is_admin = _is_admin_windows()
        if self._is_admin:
            logger.info("Application running with admin privileges")
            return
        
        # Check if admin is required by default
        from ..utils.imports import get_platforms_constants
        constants = get_platforms_constants()
        require_admin_by_default = constants.REQUIRE_ADMIN_BY_DEFAULT
        
        if require_admin_by_default:
            try:
                logger.warning("Attempting to restart with elevated rights...")
                run_as_admin()
            except Exception as e:
                logger.warning(f"Elevation denied or failed ({e}); continuing without admin.")
            self._is_admin = _is_admin_windows()
            if not self._is_admin:
                logger.info("Continuing without admin privileges. Some operations will be disabled until elevated.")
        else:
            logger.info("Running without admin privileges by default. Some operations will be disabled until elevated.")
    
    def _check_linux_admin_status(self) -> None:
        """Check and handle Linux admin status."""
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
        if CURRENT_PLATFORM == "linux":
            if self._sudo_status is None:
                self._check_linux_admin_status()
            return self._sudo_status
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
            
        from ..qt_bindings import QMessageBox
        
        if CURRENT_PLATFORM == "windows":
            if self.is_admin():
                return True
            if parent_widget:
                QMessageBox.warning(
                    parent_widget,
                    "Admin Privileges Required",
                    f"{operation_description} requires administrator privileges.\n"
                    "Please restart the application as administrator.",
                )
            return False
        elif CURRENT_PLATFORM == "linux":
            # On Linux, check if daemon is available
            if self._daemon_service and self._daemon_service.is_available():
                return True
            if parent_widget:
                QMessageBox.warning(
                    parent_widget,
                    "Privileged Daemon Required",
                    f"{operation_description} requires administrator privileges.\n"
                    "The privileged daemon is not running.\n"
                    "Please start it from the Admin menu to use this feature.",
                )
            return False
        else:
            # Other platforms
            if self.is_admin():
                return True
            sudo_status = self.get_sudo_status()
            if sudo_status and not sudo_status.get("sudo_available", False):
                if parent_widget:
                    QMessageBox.warning(
                        parent_widget,
                        "Admin Privileges Required",
                        f"{operation_description} requires root privileges, but sudo is not available.\n"
                        "Please run the application as root or install sudo.",
                    )
                return False
            if parent_widget:
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
    
    def restart_as_admin(self) -> None:
        """Restart the application with administrator/root privileges.
        
        On Windows: Restarts the entire application as administrator.
        On Linux: Starts the privileged daemon (GUI continues running as normal user).
        """
        if CURRENT_PLATFORM == "windows":
            run_as_admin()
        elif CURRENT_PLATFORM == "linux":
            # Linux admin restart is handled by daemon service
            # This method is kept for API consistency but shouldn't be called directly
            # Use daemon_service.start() instead
            logger.warning("restart_as_admin() called on Linux - use daemon_service.start() instead")
        else:
            raise RuntimeError(f"Admin elevation not supported on {CURRENT_PLATFORM}")


__all__ = ['AdminService']

