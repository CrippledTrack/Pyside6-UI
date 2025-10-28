from __future__ import annotations
import platform

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal


class AdminRequiredPlaceholder(QWidget):
    restartRequested = Signal()

    def __init__(self, tab_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # Platform-specific messages
        is_linux = platform.system().lower() == "linux"
        
        if is_linux:
            msg_text = (
                f"{tab_name} requires administrator privileges to run.\n\n"
                "The privileged daemon could not be started.\n"
                "Some features requiring root access will be disabled.\n\n"
                "To enable this tab, restart the application and\n"
                "grant administrator privileges when prompted."
            )
            btn_text = "Restart with Privileges"
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


