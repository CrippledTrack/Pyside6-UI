"""
Admin required placeholder widget for tabs that need administrator privileges.

This widget displays a message and button to restart the application with
administrator privileges when a tab requires elevated permissions.
"""

from __future__ import annotations

import platform
from typing import Optional

from ...qt_bindings import Qt, Signal, QLabel, QPushButton, QVBoxLayout, QWidget


class AdminRequiredPlaceholder(QWidget):
    """Widget that displays a message when admin privileges are required."""

    restartRequested = Signal()

    def __init__(self, tab_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # Platform-specific messages
        is_linux = platform.system().lower() == "linux"
        
        if is_linux:
            msg_text = (
                f"{tab_name} requires administrator privileges to run.\n\n"
                "The privileged daemon is not currently running.\n"
                "Some features requiring root access will be disabled.\n\n"
                "Click the button below to start the daemon and\n"
                "grant administrator privileges when prompted."
            )
            btn_text = "Start Privileged Daemon"
        else:
            msg_text = (
                f"{tab_name} requires administrator privileges to run.\n"
                "Please restart the application as Administrator."
            )
            btn_text = "Restart as Administrator"
        
        msg = QLabel(msg_text)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn = QPushButton(btn_text)
        btn.clicked.connect(self.restartRequested.emit)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)


__all__ = ['AdminRequiredPlaceholder']