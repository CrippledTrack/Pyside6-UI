"""Active UI backend id for the running application."""

from __future__ import annotations

_active_backend_id: str = "qt"


def set_active_ui_backend_id(backend_id: str) -> None:
    """Record the resolved UI backend for this process."""
    global _active_backend_id
    _active_backend_id = (backend_id or "qt").strip().lower()


def get_active_ui_backend_id() -> str:
    """Return the active UI backend id (e.g. ``"qt"``)."""
    return _active_backend_id


__all__ = ["set_active_ui_backend_id", "get_active_ui_backend_id"]
