"""Offscreen Qt tests for the notification center popup."""

from __future__ import annotations

import os
from typing import Any, Optional

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from GUI.app.services.notification_service import NotificationService, NotificationType
from GUI.app.ui.qt.themes.theme_manager import ThemeManager
from GUI.app.ui.qt.widgets.notification_center import (
    NotificationCenterWidget,
    muted_notification_text_color,
)
from GUI.app.ui.qt.bindings import QLabel, QMainWindow, QShowEvent


def _ensure_qapp() -> Any:
    from GUI.app.ui.qt.bindings import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _theme() -> ThemeManager:
    _ensure_qapp()
    return ThemeManager(settings_service=None)


def _empty_label(widget: NotificationCenterWidget) -> Optional[QLabel]:
    for i in range(widget.scroll_layout.count()):
        child = widget.scroll_layout.itemAt(i).widget()
        if isinstance(child, QLabel) and child.objectName() == "emptyNotificationsLabel":
            return child
    return None


def test_muted_text_differs_from_window_text() -> None:
    assert muted_notification_text_color("#ffffff", True).lower() != "#ffffff"
    assert muted_notification_text_color("#000000", False).lower() != "#000000"


def test_empty_state_disables_clear_all() -> None:
    widget = NotificationCenterWidget(NotificationService(), _theme())
    assert widget.clear_btn.isEnabled() is False
    empty = _empty_label(widget)
    assert empty is not None
    assert "opacity" not in empty.styleSheet()


def test_show_marks_items_read_and_restyles() -> None:
    service = NotificationService()
    service.add_notification("hello", NotificationType.INFO)
    widget = NotificationCenterWidget(service, _theme())
    item = widget._item_widgets()[0]
    unread_style = item.msg_label.styleSheet()
    assert item.notification.read is False

    widget.showEvent(QShowEvent())
    item = widget._item_widgets()[0]
    assert service.get_unread_count() == 0
    assert item.notification.read is True
    assert item.msg_label.styleSheet() != unread_style
    assert item.time_label.text() == "just now"
    assert item.time_label.toolTip()


def test_dismiss_one_row() -> None:
    app = _ensure_qapp()
    service = NotificationService()
    service.add_notification("keep", NotificationType.INFO)
    service.add_notification("drop", NotificationType.ERROR)
    widget = NotificationCenterWidget(service, _theme())
    assert [n.message for n in service.get_notifications()] == ["drop", "keep"]

    widget._item_widgets()[0].dismiss_btn.click()
    app.processEvents()
    assert [n.message for n in service.get_notifications()] == ["keep"]
    assert [w.notification.message for w in widget._item_widgets()] == ["keep"]
    assert widget.clear_btn.isEnabled() is True
    assert _empty_label(widget) is None


def test_dismiss_last_row_shows_empty_state() -> None:
    app = _ensure_qapp()
    service = NotificationService()
    service.add_notification("only", NotificationType.INFO)
    widget = NotificationCenterWidget(service, _theme())
    widget._item_widgets()[0].dismiss_btn.click()
    app.processEvents()
    assert service.get_notifications() == []
    assert widget._item_widgets() == []
    assert _empty_label(widget) is not None
    assert widget.clear_btn.isEnabled() is False


def test_clear_all_restores_empty_state() -> None:
    service = NotificationService()
    service.add_notification("a", NotificationType.INFO)
    widget = NotificationCenterWidget(service, _theme())
    widget.clear_btn.click()
    assert service.get_notifications() == []
    assert _empty_label(widget) is not None
    assert widget.clear_btn.isEnabled() is False


def test_live_list_trims_to_history_cap(monkeypatch) -> None:
    monkeypatch.setattr(NotificationService, "MAX_HISTORY_SIZE", 3)
    service = NotificationService()
    for i in range(3):
        service.add_notification(str(i), NotificationType.INFO)
    widget = NotificationCenterWidget(service, _theme())
    widget.showEvent(QShowEvent())
    assert len(widget._item_widgets()) == 3

    service.add_notification("newest", NotificationType.SUCCESS)
    widget.showEvent(QShowEvent())
    assert [w.notification.message for w in widget._item_widgets()] == [
        "newest",
        "2",
        "1",
    ]
    assert len(service.get_notifications()) == 3


def test_reopen_after_close_shows_notifications_added_while_hidden() -> None:
    """Qt popups close() on click-outside but the widget is reused."""
    service = NotificationService()
    widget = NotificationCenterWidget(service, _theme())
    assert _empty_label(widget) is not None
    widget.close()
    service.add_notification("later", NotificationType.INFO)
    widget.showEvent(QShowEvent())
    assert [w.notification.message for w in widget._item_widgets()] == ["later"]
    assert _empty_label(widget) is None
    assert widget.clear_btn.isEnabled() is True


def test_bell_tooltip_is_plain_notifications() -> None:
    from GUI.app.ui.qt.controllers.status_bar_manager import StatusBarManager

    window = QMainWindow()
    manager = StatusBarManager(
        window.statusBar(),
        NotificationService(),
        _theme(),
        parent=window,
    )
    assert manager.notif_btn.toolTip() == "Notifications"
    assert manager.notif_btn.accessibleName() == "Notifications"
