"""
Decorators for plugin event subscribers.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable, Any


def ui_thread(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to mark an event subscriber callback to run on the Qt UI thread.

    When an event is published asynchronously, callbacks decorated with this
    will be marshaled back to the Qt main thread automatically. Otherwise,
    they run on the background executor thread.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)
    
    # Store flag on the wrapper function so event dispatcher can check it
    wrapper._run_on_ui_thread = True
    return wrapper


__all__ = [
    "ui_thread",
]
