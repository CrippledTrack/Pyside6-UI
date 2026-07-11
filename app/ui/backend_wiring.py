"""Shared UI backend wiring helpers (toolkit-neutral)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..constants import GUI_API_VERSION
from ..services.container import ServiceContainer
from ..services.daemon_lifecycle_service import DaemonLifecycleService
from ..services.interfaces import IAdminService, ISettingsService
from ..services.notification_service import NotificationService
from .abstractions.event_loop import IUIEventLoop
from .abstractions.presenters import IDialogPresenter
from .abstractions.shell import IMainWindowShell
from .notification_bridge import NotificationShellBridge

logger = logging.getLogger(__name__)


def save_gui_version(container: ServiceContainer) -> None:
    """Persist the current GUI API version via settings."""
    settings_service = container.get(ISettingsService)
    settings_service.save_gui_version(GUI_API_VERSION)


def register_event_loop(container: ServiceContainer, loop: IUIEventLoop) -> None:
    """Register the UI event loop on the service container."""
    container.register_singleton(IUIEventLoop, loop)


def start_daemon_if_required(container: ServiceContainer) -> tuple[DaemonLifecycleService, Any]:
    """Start the privileged daemon when required; return (lifecycle, client)."""
    lifecycle = DaemonLifecycleService()
    client = lifecycle.start_if_required(container)
    return lifecycle, client


def shutdown_daemon(
    lifecycle: Optional[DaemonLifecycleService],
    daemon_client: Any = None,
) -> None:
    """Shut down the privileged daemon if a lifecycle manager exists."""
    if lifecycle is not None:
        lifecycle.shutdown(daemon_client)


def install_dialog_presenter(
    container: ServiceContainer,
    presenter: IDialogPresenter,
) -> None:
    """Register dialog presenter and inject into AdminService."""
    container.register_singleton(IDialogPresenter, presenter)
    admin_service = container.get(IAdminService)
    if hasattr(admin_service, "set_dialog_presenter"):
        admin_service.set_dialog_presenter(presenter)


def wire_notifications(
    container: ServiceContainer,
    shell: IMainWindowShell,
) -> NotificationShellBridge:
    """Subscribe NotificationService to the main window shell."""
    return NotificationShellBridge(
        container.get(NotificationService),
        shell,
    )


__all__ = [
    'save_gui_version',
    'register_event_loop',
    'start_daemon_if_required',
    'shutdown_daemon',
    'install_dialog_presenter',
    'wire_notifications',
]
