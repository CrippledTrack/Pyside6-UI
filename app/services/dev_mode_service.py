"""Dev mode service for managing development flags.

This service centralizes dev mode state (dev_mode, show_all_platforms)
that was previously scattered across module-level globals in admin.py.
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .settings_service import SettingsService

logger = logging.getLogger(__name__)


class DevModeService:
    """Service for managing dev mode flags and persistence.
    
    Replaces the module-level globals in admin.py with an injectable
    service that the ServiceContainer owns.
    """

    def __init__(self) -> None:
        """Initialize with defaults (both flags off)."""
        self._dev_mode: bool = False
        self._show_all_platforms: bool = False
        self._settings_service: Optional["SettingsService"] = None

    # -----------------------------------------------------------------
    # Settings integration
    # -----------------------------------------------------------------

    def configure_settings_service(self, settings_service: "SettingsService") -> None:
        """Attach settings service for persisting dev/admin flags.
        
        Args:
            settings_service: The application settings service
        """
        self._settings_service = settings_service
        try:
            if not self._dev_mode:
                self._dev_mode = settings_service.get_dev_mode()
            if not self._show_all_platforms:
                self._show_all_platforms = settings_service.get_show_all_platforms()
            self._persist_flags()
        except Exception as e:
            logger.debug(f"Failed to sync dev flags from settings: {e}")

    def _persist_flags(self) -> None:
        """Persist current flag values to settings."""
        if not self._settings_service:
            return
        self._settings_service.save_dev_mode(self._dev_mode)
        self._settings_service.save_show_all_platforms(self._show_all_platforms)

    # -----------------------------------------------------------------
    # Dev mode
    # -----------------------------------------------------------------

    def set_dev_mode(self, enabled: bool) -> None:
        """Set the dev mode flag.
        
        When dev mode is enabled, admin requirements for tab loading are bypassed.
        This allows testing the UI without elevated privileges.
        
        Args:
            enabled: True to enable dev mode, False to disable
        """
        self._dev_mode = enabled
        if not enabled:
            self._show_all_platforms = False
        self._persist_flags()
        if enabled:
            logger.warning("Dev mode enabled - admin requirements bypassed for tab loading")

    def is_dev_mode(self) -> bool:
        """Check if dev mode is enabled.
        
        Returns:
            True if dev mode is enabled, False otherwise
        """
        return self._dev_mode

    # -----------------------------------------------------------------
    # Show all platforms
    # -----------------------------------------------------------------

    def set_show_all_platforms(self, enabled: bool) -> None:
        """Set the show all platforms flag (only effective in dev mode).
        
        When enabled, tabs from all platforms (Windows and Linux) are shown
        regardless of the current platform. This is useful for UI testing.
        
        Args:
            enabled: True to show all platform tabs, False to filter by current platform
        """
        if enabled and not self._dev_mode:
            logger.info("Show all platforms ignored because dev mode is disabled")
            return
        self._show_all_platforms = enabled
        self._persist_flags()

        logger.debug(f"set_show_all_platforms({enabled}) called - dev_mode={self._dev_mode}")

        if enabled:
            logger.warning("Show all platforms enabled - Windows and Linux tabs will be shown")
        else:
            logger.info("Show all platforms disabled - filtering by current platform")

    def is_show_all_platforms(self) -> bool:
        """Check if show all platforms is enabled.
        
        Note: This only returns True if both dev mode AND show_all_platforms are enabled.
        
        Returns:
            True if showing all platform tabs, False otherwise
        """
        result = self._dev_mode and self._show_all_platforms
        logger.debug(
            f"is_show_all_platforms() called: dev_mode={self._dev_mode}, "
            f"show_all={self._show_all_platforms}, result={result}"
        )
        return result


__all__ = ['DevModeService']
