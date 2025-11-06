"""
Error placeholder widget for tabs that failed to load.

This widget displays an error message when a tab fails to load or initialize.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ErrorPlaceholder(QWidget):
    """Widget that displays an error message when a tab fails to load."""

    def __init__(self, tab_name: str, error_message: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(f"Error loading {tab_name}:\n{error_message}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: red;")
        layout.addWidget(label)


__all__ = ['ErrorPlaceholder']