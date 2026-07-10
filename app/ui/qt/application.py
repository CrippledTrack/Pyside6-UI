"""Qt application backend implementing IUIApplication."""

from __future__ import annotations

import logging
import sys
from typing import Any, List, Optional

from ...constants import GUI_API_VERSION
from ...services.container import ServiceContainer
from ...services.interfaces import IAdminService, ISettingsService
from ...services.notification_service import NotificationService
from ...services.theme_init_service import ThemeInitService
from ...services.daemon_lifecycle_service import DaemonLifecycleService
from ...services.app_lifecycle_service import AppLifecycleService
from ..abstractions.event_loop import IUIEventLoop
from ..abstractions.presenters import IDialogPresenter
from .bindings import QApplication
from .event_dispatcher import QtEventDispatcher
from .main_window import MainWindow
from .notification_bridge import NotificationShellBridge
from .presenters import QtDialogPresenter

logger = logging.getLogger(__name__)


def get_ui_backend(name: str):
    """Return a UI backend factory by name."""
    backends = {
        "qt": QtApplicationBackend,
    }
    if name not in backends:
        raise ValueError(f"Unknown UI backend: {name!r}. Available: {list(backends)}")
    return backends[name]


class QtApplicationBackend:
    """Qt-specific UI application backend."""

    def __init__(self, container: ServiceContainer, argv: List[str], version_name: str) -> None:
        self._container = container
        self._argv = argv
        self._version_name = version_name
        self._app: Optional[QApplication] = None
        self._daemon_lifecycle: Optional[DaemonLifecycleService] = None
        self._daemon_client: Any = None
        self._notification_bridge: Optional[NotificationShellBridge] = None

    def run(self) -> int:
        from ...services.qt_deps_service import QtDepsService

        qt_deps = QtDepsService()
        deps_ok, deps_message = qt_deps.ensure_dependencies()
        if not deps_ok:
            logger.error("Required Qt xcb dependencies are missing.")
            if deps_message:
                print(deps_message, file=sys.stderr)
            return 1

        settings_service = self._container.get(ISettingsService)
        settings_service.save_gui_version(GUI_API_VERSION)

        self._app = QApplication(self._argv)

        dispatcher = QtEventDispatcher.get_instance()
        self._container.register_singleton(IUIEventLoop, dispatcher)

        app_lifecycle = AppLifecycleService()
        app_lifecycle.configure_qt_application(self._app, self._version_name, GUI_API_VERSION)

        theme_init = ThemeInitService()
        theme_manager = theme_init.initialize(self._container, settings_service)

        self._daemon_lifecycle = DaemonLifecycleService()
        self._daemon_client = self._daemon_lifecycle.start_if_required(self._container)

        window = MainWindow(
            theme_manager=theme_manager,
            settings_service=settings_service,
            container=self._container,
        )

        dialog_presenter = QtDialogPresenter(parent=window)
        self._container.register_singleton(IDialogPresenter, dialog_presenter)
        admin_service = self._container.get(IAdminService)
        if hasattr(admin_service, "set_dialog_presenter"):
            admin_service.set_dialog_presenter(dialog_presenter)

        self._notification_bridge = NotificationShellBridge(
            self._container.get(NotificationService),
            window,
        )

        window.show()
        exit_code = self._app.exec()

        if self._daemon_lifecycle:
            self._daemon_lifecycle.shutdown(self._daemon_client)

        logger.info(f"Application closed with code {exit_code}")
        return exit_code

    def quit(self) -> None:
        if self._app:
            self._app.quit()


__all__ = ['QtApplicationBackend', 'get_ui_backend']
