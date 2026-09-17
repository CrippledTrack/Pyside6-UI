"""Theme initialization for the Qt UI backend."""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


class ThemeInitService:
    """Initialize and register ThemeManager after QApplication is created."""

    def __init__(self) -> None:
        self._theme_manager: Any = None
        self._settings_service: Any = None

    def initialize(self, container: Any, settings_service: Any) -> Any:
        from .themes.theme_manager import ThemeManager

        theme_manager = ThemeManager(settings_service=settings_service)
        container.register_singleton(ThemeManager, theme_manager)
        logger.info("ThemeManager registered in container")

        self._theme_manager = theme_manager
        self._settings_service = settings_service

        saved_theme = settings_service.get_theme_preference()
        theme_manager.apply_auto_theme(saved_theme=saved_theme)
        self._follow_system_color_scheme()
        return theme_manager

    def _follow_system_color_scheme(self) -> None:
        """Re-resolve the theme when the OS switches between light and dark.

        Without this the auto theme is decided once at startup, so toggling the
        system appearance (routine on macOS, which can do it on a schedule)
        leaves the app on the old palette until it is restarted.
        """
        from .bindings import QApplication

        app = QApplication.instance()
        if app is None:
            return
        try:
            app.styleHints().colorSchemeChanged.connect(self._on_color_scheme_changed)
        except (AttributeError, RuntimeError) as e:
            # colorSchemeChanged arrived in Qt 6.5; older bindings just keep the
            # theme resolved at startup.
            logger.debug(f"Not following system color scheme changes: {e}")

    def _on_color_scheme_changed(self, *_args: Any) -> None:
        if self._theme_manager is None:
            return
        try:
            saved_theme = self._settings_service.get_theme_preference()
        except Exception:
            saved_theme = None
        if saved_theme:
            # An explicitly chosen theme is not supposed to track the system.
            return
        applied = self._theme_manager.apply_auto_theme(saved_theme=None)
        logger.info(f"System color scheme changed, reapplied theme: {applied}")


__all__ = ["ThemeInitService"]
