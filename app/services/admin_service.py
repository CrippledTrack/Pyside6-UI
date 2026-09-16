"""Admin/elevation service for managing privileged operations."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..constants import CURRENT_PLATFORM

if TYPE_CHECKING:
    from ..ui.abstractions.presenters import IDialogPresenter

logger = logging.getLogger(__name__)


class AdminService:
    """Base class and factory for managing admin/elevation status and operations."""

    def __new__(cls, daemon_service: Optional[Any] = None) -> AdminService:
        if cls is AdminService:
            if CURRENT_PLATFORM == "windows":
                return super().__new__(WindowsAdminService)
            elif CURRENT_PLATFORM in ("linux", "darwin"):
                return super().__new__(UnixAdminService)
            else:
                return super().__new__(FallbackAdminService)
        return super().__new__(cls)

    def __init__(self, daemon_service: Optional[Any] = None):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._daemon_service = daemon_service
        self._is_admin: Optional[bool] = None
        self._dialog_presenter: Optional["IDialogPresenter"] = None
        self._check_admin_status()
        self._initialized = True

    def set_dialog_presenter(self, presenter: "IDialogPresenter") -> None:
        """Register dialog presenter (lazy-injected by UI backend)."""
        self._dialog_presenter = presenter

    def _check_admin_status(self) -> None:
        raise NotImplementedError("Subclasses must implement _check_admin_status")

    def is_admin(self) -> bool:
        if self._is_admin is None:
            self._check_admin_status()
        return self._is_admin or False

    def get_sudo_status(self) -> Optional[Dict[str, Any]]:
        return None

    def prompt_for_admin_operation(self, operation_description: str) -> bool:
        if self.is_admin():
            return True
        return False

    def restart_as_admin(self) -> tuple[bool, Optional[str]]:
        return False, f"Admin elevation not supported on {CURRENT_PLATFORM}"

    def needs_admin_for_plugin(self, requires_admin: bool) -> bool:
        raise NotImplementedError("Subclasses must implement needs_admin_for_plugin")

    def _show_warning(self, title: str, message: str) -> None:
        if self._dialog_presenter:
            self._dialog_presenter.warning(title, message)
        else:
            logger.warning("%s: %s", title, message)

    def _show_confirm(self, title: str, message: str) -> bool:
        if self._dialog_presenter:
            return self._dialog_presenter.confirm(title, message)
        logger.warning("%s: %s (no dialog presenter — defaulting to False)", title, message)
        return False


class WindowsAdminService(AdminService):
    def _check_admin_status(self) -> None:
        from ..utils.elevation_windows import is_admin as _is_admin_windows
        self._is_admin = _is_admin_windows()
        if self._is_admin:
            logger.info("Application running with admin privileges")
            return

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

    def prompt_for_admin_operation(self, operation_description: str) -> bool:
        if self.is_admin():
            return True
        self._show_warning(
            "Admin Privileges Required",
            f"{operation_description} requires administrator privileges.\n"
            "Please restart the application as administrator.",
        )
        return False

    def restart_as_admin(self) -> tuple[bool, Optional[str]]:
        try:
            from ..utils.elevation_windows import run_as_admin
            run_as_admin()
            return True, None
        except Exception as e:
            return False, str(e)

    def needs_admin_for_plugin(self, requires_admin: bool) -> bool:
        from ..utils.admin import is_dev_mode
        if is_dev_mode():
            return False
        if not requires_admin:
            return False
        return not self.is_admin()


class UnixAdminService(AdminService):
    """Admin service for Linux/macOS: GUI stays unprivileged, pipe daemon is root."""

    def __init__(self, daemon_service: Optional[Any] = None):
        self._sudo_status: Optional[Dict[str, Any]] = None
        super().__init__(daemon_service)

    def _check_admin_status(self) -> None:
        from ..utils.elevation import get_sudo_status
        self._sudo_status = get_sudo_status() or {}
        self._is_admin = bool(self._sudo_status.get("is_admin"))
        if self._is_admin:
            logger.info("Application running with admin/root privileges")
        else:
            logger.info(
                "Application running as user '%s'",
                self._sudo_status.get("current_user", "unknown"),
            )
            if self._sudo_status.get("sudo_available"):
                logger.info("Sudo is available - operations requiring root will prompt for password")
            else:
                logger.warning("Sudo not available - some operations may not work")

    def get_sudo_status(self) -> Optional[Dict[str, Any]]:
        if self._sudo_status is None:
            self._check_admin_status()
        return self._sudo_status

    def prompt_for_admin_operation(self, operation_description: str) -> bool:
        if self.is_admin():
            return True
        if self._daemon_service and self._daemon_service.is_available():
            return True
        self._show_warning(
            "Privileged Daemon Required",
            f"{operation_description} requires administrator privileges.\n"
            "The privileged daemon is not running.\n"
            "Please start it from the Admin menu to use this feature.",
        )
        return False

    def restart_as_admin(self) -> tuple[bool, Optional[str]]:
        if self._daemon_service:
            return self._daemon_service.start()
        return False, "Daemon service not available"

    def needs_admin_for_plugin(self, requires_admin: bool) -> bool:
        from ..utils.admin import is_dev_mode
        if is_dev_mode():
            return False
        if not requires_admin:
            return False
        if self.is_admin():
            return False
        if self._daemon_service and self._daemon_service.is_available():
            return False
        try:
            from ..daemon import is_daemon_available
            return not is_daemon_available()
        except Exception:
            return True


class FallbackAdminService(AdminService):
    def _check_admin_status(self) -> None:
        logger.warning(f"Unsupported platform: {CURRENT_PLATFORM}")
        self._is_admin = False

    def prompt_for_admin_operation(self, operation_description: str) -> bool:
        if self.is_admin():
            return True
        return self._show_confirm(
            "Admin Privileges Required",
            f"{operation_description} requires root privileges.\n"
            "The application will prompt for your password when needed.\n\n"
            "Do you want to continue?",
        )

    def needs_admin_for_plugin(self, requires_admin: bool) -> bool:
        from ..utils.admin import is_dev_mode
        if is_dev_mode():
            return False
        if not requires_admin:
            return False
        return not self.is_admin()


LinuxAdminService = UnixAdminService


__all__ = [
    'AdminService',
    'WindowsAdminService',
    'UnixAdminService',
    'LinuxAdminService',
    'FallbackAdminService',
]
