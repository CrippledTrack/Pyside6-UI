"""Dialog presenter abstraction."""

from __future__ import annotations

from typing import Protocol


class IDialogPresenter(Protocol):
    """Protocol for showing toolkit-native dialogs from services."""

    def warning(self, title: str, message: str) -> None:
        """Show a warning dialog."""
        ...

    def confirm(self, title: str, message: str) -> bool:
        """Show a confirmation dialog; return True if accepted."""
        ...

    def error(self, title: str, message: str) -> None:
        """Show an error dialog."""
        ...


__all__ = ['IDialogPresenter']
