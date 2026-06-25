"""
Admin required placeholder widget for tabs that need administrator privileges.

This widget displays a message and button to restart the application with
administrator privileges when a tab requires elevated permissions.
"""

from __future__ import annotations

import platform
from typing import Optional

from ...qt_bindings import Qt, Signal, QLabel, QPushButton, QVBoxLayout, QWidget, QFont, QSizePolicy


class AdminRequiredPlaceholder(QWidget):
    """Widget that displays a message when admin privileges are required."""

    restartRequested = Signal()

    def __init__(self, tab_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("AdminRequiredPlaceholder")
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        
        # Center container
        center_widget = QWidget()
        center_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred
        )
        center_layout = QVBoxLayout(center_widget)
        center_layout.setSpacing(20)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Platform-specific messages
        is_linux = platform.system().lower() == "linux"
        
        # Title/Heading
        self._title_label = QLabel(f"{tab_name} Requires Administrator Privileges")
        self._title_label.setObjectName("adminTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setWeight(QFont.Weight.Medium)
        self._title_label.setFont(title_font)
        center_layout.addWidget(self._title_label)
        
        if is_linux:
            desc_text = (
                "The privileged daemon is not currently running.\n"
                "Some features requiring root access will be disabled.\n\n"
                "Click the button below to start the daemon and "
                "grant administrator privileges when prompted."
            )
            btn_text = "Start Privileged Daemon"
        else:
            desc_text = (
                "This tab requires administrator privileges to run.\n"
                "Please restart the application with elevated privileges."
            )
            btn_text = "Restart as Administrator"
            
        # Description
        self._desc_label = QLabel(desc_text)
        self._desc_label.setObjectName("adminDesc")
        self._desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc_label.setWordWrap(True)
        desc_font = QFont()
        desc_font.setPointSize(10)
        self._desc_label.setFont(desc_font)
        center_layout.addWidget(self._desc_label)
        
        # Action Button
        self._btn = QPushButton(btn_text)
        self._btn.setObjectName("adminBtn")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self.restartRequested.emit)
        center_layout.addWidget(self._btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Add stretch to center the content
        main_layout.addStretch()
        main_layout.addWidget(center_widget)
        main_layout.addStretch()
        
        # Apply theme-aware styling
        self._apply_styling()

    def _apply_styling(self) -> None:
        """Apply theme-aware styling to the widget and button."""
        try:
            from ...qt_bindings import QApplication, QPalette
            highlight = QApplication.palette().color(QPalette.ColorRole.Highlight).name()
            # Derive hover and pressed colors
            from ....themes.theme_manager import ThemeManager
            highlight_hover = ThemeManager.adjust_color(highlight, 1.15)
            highlight_pressed = ThemeManager.adjust_color(highlight, 0.85)
            
            # Text on highlight color is usually highlighted_text or white
            highlighted_text = QApplication.palette().color(QPalette.ColorRole.HighlightedText).name()
        except Exception:
            highlight = "#3182ce"
            highlight_hover = "#4299e1"
            highlight_pressed = "#2b6cb0"
            highlighted_text = "#ffffff"
            
        self.setStyleSheet(f"""
            AdminRequiredPlaceholder {{
                background-color: transparent;
            }}
            QLabel#adminTitle {{
                color: palette(text);
                background-color: transparent;
            }}
            QLabel#adminDesc {{
                color: palette(mid);
                background-color: transparent;
            }}
            QPushButton#adminBtn {{
                background-color: {highlight};
                color: {highlighted_text};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 500;
            }}
            QPushButton#adminBtn:hover {{
                background-color: {highlight_hover};
            }}
            QPushButton#adminBtn:pressed {{
                background-color: {highlight_pressed};
            }}
        """)


__all__ = ['AdminRequiredPlaceholder']