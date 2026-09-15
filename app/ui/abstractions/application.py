"""Application lifecycle abstraction."""

from __future__ import annotations

from typing import Protocol


class IUIApplication(Protocol):
    """Protocol for UI application lifecycle."""

    def run(self) -> int:
        """Start the UI event loop and block until exit."""
        ...

    def quit(self) -> None:
        """Request application shutdown."""
        ...


__all__ = ['IUIApplication']
