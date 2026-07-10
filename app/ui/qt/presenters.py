"""Qt dialog presenter implementing IDialogPresenter."""

from __future__ import annotations

from typing import Optional

from ..abstractions.presenters import IDialogPresenter
from .bindings import QMessageBox, QWidget


class QtDialogPresenter:
    """Shows QMessageBox dialogs for service-layer prompts."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        self._parent = parent

    def set_parent(self, parent: Optional[QWidget]) -> None:
        """Update parent widget for modal dialogs."""
        self._parent = parent

    def warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self._parent, title, message)

    def confirm(self, title: str, message: str) -> bool:
        reply = QMessageBox.question(
            self._parent,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return reply == QMessageBox.StandardButton.Yes

    def error(self, title: str, message: str) -> None:
        QMessageBox.critical(self._parent, title, message)


__all__ = ['QtDialogPresenter']
