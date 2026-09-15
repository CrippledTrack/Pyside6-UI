"""Document the current synchronous dialog/file-picker contracts.

Changing ``IDialogPresenter.confirm`` or ``pick_save_file`` to callback-based
APIs waits until a second UI backend is an actual milestone. These tests lock
today's sync signatures so a later break is deliberate.
"""

from __future__ import annotations

import inspect

from GUI.app.ui.abstractions.presenters import IDialogPresenter
from GUI.app.ui import definitions


class _SyncPresenter:
    """Minimal non-Qt adapter that satisfies the current presenter contract."""

    def warning(self, title: str, message: str) -> None:
        return None

    def confirm(self, title: str, message: str) -> bool:
        return title == "ok"

    def error(self, title: str, message: str) -> None:
        return None

    def info(self, title: str, message: str) -> None:
        return None


def test_confirm_is_synchronous_bool() -> None:
    presenter: IDialogPresenter = _SyncPresenter()
    assert presenter.confirm("ok", "msg") is True
    assert presenter.confirm("no", "msg") is False
    sig = inspect.signature(IDialogPresenter.confirm)
    assert list(sig.parameters) == ["self", "title", "message"]
    assert "bool" in str(sig.return_annotation).lower()


def test_pick_save_file_is_synchronous_optional_str() -> None:
    sig = inspect.signature(definitions.pick_save_file)
    assert "title" in sig.parameters
    ann = str(sig.return_annotation)
    assert "str" in ann
