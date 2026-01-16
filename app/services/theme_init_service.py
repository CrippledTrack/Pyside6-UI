"""
Theme initialization service.
"""
from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


class ThemeInitService:
    """Initialize and register ThemeManager after QApplication is created."""

    def initialize(self, container: Any, settings_service: Any) -> Any:
        from ...themes.theme_manager import ThemeManager

        theme_manager = ThemeManager(settings_service=settings_service)
        container.register_singleton(ThemeManager, theme_manager)
        logger.info("ThemeManager registered in container")

        saved_theme = settings_service.get_theme_preference()
        theme_manager.apply_auto_theme(saved_theme=saved_theme)
        return theme_manager


__all__ = ["ThemeInitService"]
