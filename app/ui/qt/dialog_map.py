"""Qt implementation of toolkit-neutral content dialog windows.

Plugins and host code should use :mod:`GUI.app.ui.definitions` rather than
importing this module directly.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from .bindings import QDialog, QFileDialog, QVBoxLayout, Qt

logger = logging.getLogger(__name__)


class _DefinitionsDialog(QDialog):
    """QDialog shell carrying neutral lifecycle state."""

    def __init__(
        self,
        title: str,
        parent: Any,
        modal: bool,
        default_size: Optional[tuple[int, int]],
    ) -> None:
        super().__init__(parent)
        self.closed_callbacks: list[Callable[[bool], None]] = []
        self.requested_modal = bool(modal)
        self.setWindowTitle(str(title))
        self.setModal(self.requested_modal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if default_size is not None:
            self.resize(*default_size)
        self.finished.connect(self._dispatch_closed)

    def _dispatch_closed(self, result: int) -> None:
        accepted = result == QDialog.DialogCode.Accepted.value
        pending = list(self.closed_callbacks)
        self.closed_callbacks.clear()
        if self in _OPEN_DIALOGS:
            _OPEN_DIALOGS.remove(self)
        for callback in pending:
            try:
                callback(accepted)
            except Exception:
                logger.exception("Dialog close callback failed")


_OPEN_DIALOGS: list[_DefinitionsDialog] = []


def create_dialog(
    title: str,
    *,
    parent: Any = None,
    modal: bool = True,
    default_size: Optional[tuple[int, int]] = None,
) -> _DefinitionsDialog:
    """Create a themed QDialog shell with callback storage."""
    return _DefinitionsDialog(title, parent, modal, default_size)


def set_dialog_content(dialog: QDialog, content: Any) -> None:
    """Replace the content hosted by a QDialog shell."""
    layout = dialog.layout()
    if layout is None:
        raise ValueError("Dialog has no content layout")
    while layout.count():
        item = layout.takeAt(0)
        old_widget = item.widget()
        if old_widget is not None and old_widget is not content:
            old_widget.setParent(None)
    layout.addWidget(content)


def open_dialog(
    dialog: _DefinitionsDialog,
    *,
    on_closed: Optional[Callable[[bool], None]] = None,
) -> None:
    """Open a QDialog without returning a blocking result."""
    if on_closed is not None:
        dialog.closed_callbacks.append(on_closed)

    if dialog.isVisible():
        dialog.raise_()
        dialog.activateWindow()
        return

    if dialog not in _OPEN_DIALOGS:
        _OPEN_DIALOGS.append(dialog)
    if dialog.requested_modal:
        dialog.open()
    else:
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()


def close_dialog(dialog: QDialog, *, accepted: bool = False) -> None:
    """Close a dialog with the requested semantic result."""
    if accepted:
        dialog.accept()
    else:
        dialog.reject()


def accept_dialog(dialog: QDialog) -> None:
    """Accept a QDialog."""
    dialog.accept()


def reject_dialog(dialog: QDialog) -> None:
    """Reject a QDialog."""
    dialog.reject()


def pick_save_file(
    title: str,
    *,
    parent: Any = None,
    name_filter: str = "",
    default_name: str = "",
) -> Optional[str]:
    """Show a native Qt save-file picker."""
    file_path, _selected_filter = QFileDialog.getSaveFileName(
        parent,
        str(title),
        str(default_name),
        str(name_filter),
    )
    return file_path or None


__all__ = [
    "create_dialog",
    "set_dialog_content",
    "open_dialog",
    "close_dialog",
    "accept_dialog",
    "reject_dialog",
    "pick_save_file",
]
