"""
Error placeholder widget for tabs that failed to load.

This widget displays an error message when a tab fails to load or initialize.
"""

from __future__ import annotations

from typing import Optional

from ...qt_bindings import Qt, QFont, QSizePolicy, QLabel, QVBoxLayout, QWidget, QScrollArea, QFrame


class ErrorPlaceholder(QWidget):
    """Widget that displays an error message when a tab fails to load."""

    def __init__(self, tab_name: str, error_message: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ErrorPlaceholder")
        
        # Outer layout to hold the scroll area
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        
        # Scroll Area for overflow support
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("background-color: transparent; border: none;")
        
        # Container widget for scroll content
        container_widget = QWidget()
        container_widget.setStyleSheet("background-color: transparent;")
        
        # Layout inside container widget
        center_layout = QVBoxLayout(container_widget)
        center_layout.setContentsMargins(40, 40, 40, 40)
        center_layout.setSpacing(20)
        
        # Add top stretch for vertical centering
        center_layout.addStretch(1)
        
        # Error Title / Heading
        self._title_label = QLabel(f"Failed to load {tab_name}")
        self._title_label.setObjectName("errorTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setWeight(QFont.Weight.Medium)
        self._title_label.setFont(title_font)
        center_layout.addWidget(self._title_label)
        
        # Error Details
        self._details_label = QLabel(error_message)
        self._details_label.setObjectName("errorDetails")
        self._details_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._details_label.setWordWrap(True)
        self._details_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_font = QFont()
        details_font.setPointSize(10)
        self._details_label.setFont(details_font)
        center_layout.addWidget(self._details_label)
        
        # Add bottom stretch for vertical centering
        center_layout.addStretch(1)
        
        # Set container to scroll area, and scroll area to main layout
        scroll_area.setWidget(container_widget)
        outer_layout.addWidget(scroll_area)
        
        # Apply theme-aware styling
        self._apply_styling()
        
    def _apply_styling(self) -> None:
        """Apply theme-aware styling to the error widget."""
        try:
            from ....themes.theme_manager import ThemeManager
            from ...qt_bindings import QApplication, QPalette
            highlight_color = QApplication.palette().color(QPalette.ColorRole.Highlight).name()
            error_color = ThemeManager.adjust_notification_color(highlight_color, "error")
        except Exception:
            error_color = "#ef5350"  # Fallback soft red
            
        self.setStyleSheet(f"""
            ErrorPlaceholder {{
                background-color: transparent;
            }}
            QLabel#errorTitle {{
                color: {error_color};
                background-color: transparent;
            }}
            QLabel#errorDetails {{
                color: palette(text);
                background-color: transparent;
            }}
        """)


__all__ = ['ErrorPlaceholder']