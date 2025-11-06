"""
Loading placeholder widget for tabs that are being loaded.

This widget displays a loading message while a tab's content is being initialized.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LoadingPlaceholder(QWidget):
    """Widget that displays a loading message for a tab."""

    def __init__(self, tab_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(f"Loading {tab_name}...")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)


__all__ = ['LoadingPlaceholder']