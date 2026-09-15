"""Qt event dispatcher implementing IUIEventLoop."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from .bindings import QtCore

logger = logging.getLogger(__name__)


class QtEventDispatcher:
    """Routes background thread callbacks onto the Qt main thread."""

    _instance: Optional["QtEventDispatcher"] = None

    def __init__(self) -> None:
        class _DispatcherQObject(QtCore.QObject):
            dispatch_signal = QtCore.Signal(object, tuple, dict)

            def __init__(self) -> None:
                super().__init__()
                self.dispatch_signal.connect(self._execute)

            def _execute(self, func: Callable, args: tuple, kwargs: dict) -> None:
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    logging.getLogger(__name__).error(
                        f"Error executing dispatched callback on main thread: {e}",
                        exc_info=True,
                    )

        self._qobject = _DispatcherQObject()

    @classmethod
    def get_instance(cls) -> "QtEventDispatcher":
        """Get singleton; must be first called from the GUI main thread."""
        if cls._instance is None:
            app = QtCore.QCoreApplication.instance()
            if app is not None:
                try:
                    app_thread = app.thread()
                    this_thread = QtCore.QThread.currentThread()
                    if app_thread is not None and this_thread is not app_thread:
                        logger.error(
                            "QtEventDispatcher.get_instance() first called off the GUI "
                            "thread; callbacks may run on the wrong thread"
                        )
                except Exception as e:
                    logger.debug(f"Could not verify dispatcher thread affinity: {e}")
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for tests)."""
        cls._instance = None

    def invoke_on_main(self, callback: Callable[..., None], *args: Any, **kwargs: Any) -> None:
        """Post a callback to the Qt main thread."""
        self._qobject.dispatch_signal.emit(callback, args, kwargs)


__all__ = ['QtEventDispatcher']
