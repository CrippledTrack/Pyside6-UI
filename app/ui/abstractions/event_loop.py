"""UI event loop abstraction for main-thread marshaling."""

from __future__ import annotations

from typing import Any, Callable, Protocol


class IUIEventLoop(Protocol):
    """Protocol for marshaling callbacks to the UI main thread."""

    def invoke_on_main(self, callback: Callable[..., None], *args: Any, **kwargs: Any) -> None:
        """Schedule callback execution on the UI main thread."""
        ...


__all__ = ['IUIEventLoop']
