"""ServiceContainer DI smoke tests."""

from __future__ import annotations

from GUI.app.services.container import ServiceContainer
from GUI.app.services.interfaces import (
    ISettingsService,
    IDaemonService,
    IAdminService,
    INotificationService,
)
from GUI.plugin_system.interfaces import ISettingsService as IPluginSettingsService
from GUI.app.services.plugin_service import PluginService


def _make_container() -> ServiceContainer:
    c = ServiceContainer()
    c.initialize_services()
    return c


def test_interface_gets_succeed() -> None:
    container = _make_container()
    assert container.get(ISettingsService) is not None
    assert container.get(IDaemonService) is not None
    assert container.get(IAdminService) is not None
    assert container.get(INotificationService) is not None
    assert container.get(IPluginSettingsService) is container.get(ISettingsService)
    assert container.get(PluginService) is not None


def test_plugin_registry_not_registered_for_ui() -> None:
    """UI consumers use PluginService only; raw PluginRegistry is internal."""
    from GUI.plugin_system.registry import PluginRegistry

    container = _make_container()
    try:
        container.get(PluginRegistry)
        raise AssertionError("PluginRegistry should not be registered")
    except ValueError:
        pass


def test_services_modules_have_no_ui_qt_imports() -> None:
    from pathlib import Path

    services_root = Path(__file__).resolve().parents[1] / "app" / "services"
    bad = []
    for path in services_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "ui.qt" in text or "ui/qt" in text:
            bad.append(str(path))
    assert not bad, f"services must not import ui.qt: {bad}"
