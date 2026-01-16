"""
App lifecycle helpers for startup/shutdown and Qt configuration.
"""
from __future__ import annotations

import logging
import os
import platform
import sys
from typing import Optional, IO


logger = logging.getLogger(__name__)


class AppLifecycleService:
    """Encapsulate app lifecycle concerns like single-instance locking."""

    def __init__(self) -> None:
        self._lock_file: Optional[IO[str]] = None
        self._lock_file_path: Optional[str] = None

    def acquire_single_instance_lock(self) -> bool:
        """Acquire single-instance lock (Linux only)."""
        if platform.system().lower() != "linux":
            return True

        import fcntl

        self._lock_file_path = "/tmp/basic-ui.lock"
        try:
            self._lock_file = open(self._lock_file_path, "w", encoding="utf-8")
            fcntl.lockf(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_file.write(str(os.getpid()))
            self._lock_file.flush()
            return True
        except (IOError, OSError):
            return False

    def release_single_instance_lock(self) -> None:
        """Release single-instance lock (Linux only)."""
        if not self._lock_file:
            return

        try:
            import fcntl

            fcntl.lockf(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()
            if self._lock_file_path and os.path.exists(self._lock_file_path):
                os.unlink(self._lock_file_path)
        except Exception:
            # Ignore errors during cleanup - file may already be released
            pass

    def configure_qt_application(self, app, version_name: str, gui_api_version: str) -> None:
        """Configure Qt application style, fonts, and Windows AppUserModelID."""
        from PySide6.QtGui import QFont

        if platform.system().lower() == "windows":
            app.setStyle("Fusion")
            try:
                import ctypes

                myappid = f"{version_name}.Scripts.GUI.{gui_api_version}"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception as e:
                print(f"Failed to set AppUserModelID: {e}", file=sys.stderr)  # type: ignore[name-defined]

        app.setFont(QFont("Segoe UI", 10))


__all__ = ["AppLifecycleService"]
