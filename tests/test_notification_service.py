"""NotificationService history, unread state, and relative timestamps."""

from __future__ import annotations

from datetime import datetime, timedelta

from GUI.app.services.notification_service import (
    NotificationService,
    NotificationType,
    format_notification_age,
)


def test_add_notification_tracks_unread() -> None:
    service = NotificationService()
    seen: list[str] = []
    unread: list[int] = []
    service.subscribe_added(lambda n: seen.append(n.message))
    service.subscribe_unread_changed(lambda count: unread.append(count))

    service.add_notification("hello", NotificationType.INFO, details="more")
    notes = service.get_notifications()
    assert len(notes) == 1
    assert notes[0].message == "hello"
    assert notes[0].details == "more"
    assert notes[0].read is False
    assert service.get_unread_count() == 1
    assert seen == ["hello"]
    assert unread == [1]


def test_mark_all_as_read_clears_unread_count() -> None:
    service = NotificationService()
    service.add_notification("a", NotificationType.WARNING)
    service.add_notification("b", NotificationType.ERROR)
    assert service.get_unread_count() == 2

    unread: list[int] = []
    service.subscribe_unread_changed(lambda count: unread.append(count))
    service.mark_all_as_read()
    assert service.get_unread_count() == 0
    assert all(n.read for n in service.get_notifications())
    assert unread == [0]

    service.mark_all_as_read()
    assert unread == [0]


def test_history_caps_at_max_size() -> None:
    service = NotificationService()
    for i in range(NotificationService.MAX_HISTORY_SIZE + 5):
        service.add_notification(str(i), NotificationType.INFO)
    notes = service.get_notifications()
    assert len(notes) == NotificationService.MAX_HISTORY_SIZE
    assert notes[0].message == str(NotificationService.MAX_HISTORY_SIZE + 4)
    assert notes[-1].message == "5"


def test_remove_notification_drops_one_row() -> None:
    service = NotificationService()
    service.add_notification("keep", NotificationType.INFO)
    service.add_notification("drop", NotificationType.ERROR)
    drop = service.get_notifications()[0]
    service.remove_notification(drop)
    remaining = service.get_notifications()
    assert [n.message for n in remaining] == ["keep"]
    assert service.get_unread_count() == 1

    service.remove_notification(drop)
    assert [n.message for n in service.get_notifications()] == ["keep"]


def test_clear_all_empties_history() -> None:
    service = NotificationService()
    service.add_notification("a", NotificationType.SUCCESS)
    service.clear_all()
    assert service.get_notifications() == []
    assert service.get_unread_count() == 0


def test_format_notification_age_buckets() -> None:
    now = datetime(2026, 9, 19, 12, 0, 0)
    assert format_notification_age(now, now) == "just now"
    assert format_notification_age(now - timedelta(seconds=59), now) == "just now"
    assert format_notification_age(now - timedelta(minutes=1), now) == "1m ago"
    assert format_notification_age(now - timedelta(minutes=59), now) == "59m ago"
    assert format_notification_age(now - timedelta(hours=1), now) == "1h ago"
    assert format_notification_age(now - timedelta(hours=23), now) == "23h ago"
    yesterday = now - timedelta(hours=24)
    expected_yesterday = yesterday.strftime("%b %d").replace("  ", " ")
    assert format_notification_age(yesterday, now) == expected_yesterday
    older = datetime(2025, 9, 1, 8, 0, 0)
    expected_older = f"{older.strftime('%b %d').replace('  ', ' ')}, 2025"
    assert format_notification_age(older, now) == expected_older


def test_format_notification_age_future_is_just_now() -> None:
    now = datetime(2026, 9, 19, 12, 0, 0)
    assert format_notification_age(now + timedelta(minutes=5), now) == "just now"
