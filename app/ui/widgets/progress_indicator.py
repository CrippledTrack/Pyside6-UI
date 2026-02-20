"""
Reusable progress indicator widget for long-running operations.

This widget provides a progress bar with optional message display
for use in plugin widgets and other UI components.
"""

from __future__ import annotations

from typing import Optional

from ...qt_bindings import Qt, QLabel, QProgressBar, QVBoxLayout, QWidget


class ProgressIndicator(QWidget):
    """
    Progress indicator widget with progress bar and optional message.
    
    This widget can be used in plugin widgets to show progress
    for long-running operations. Supports both determinate and
    indeterminate progress modes.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the progress indicator.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Message label (optional, hidden by default)
        self.message_label = QLabel(self)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        layout.addWidget(self.message_label)
        
        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
    
    def set_progress(self, value: int, maximum: int = 100) -> None:
        """
        Set progress value.
        
        Args:
            value: Current progress value (0 to maximum)
            maximum: Maximum progress value (default: 100)
        """
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)
        if self.progress_bar.isTextVisible():
            self.progress_bar.setFormat(f"{value}/{maximum}")
    
    def set_message(self, text: str) -> None:
        """
        Set the message text to display above the progress bar.
        
        Args:
            text: Message text (empty string to hide)
        """
        if text:
            self.message_label.setText(text)
            self.message_label.show()
        else:
            self.message_label.hide()
    
    def set_indeterminate(self, indeterminate: bool) -> None:
        """
        Set whether the progress bar is in indeterminate mode.
        
        Args:
            indeterminate: True for indeterminate mode, False for determinate
        """
        if indeterminate:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(0)  # Indeterminate mode in Qt
        else:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)
    
    def reset(self) -> None:
        """Reset the progress indicator to initial state."""
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.message_label.hide()
        self.message_label.clear()
    
    def get_progress(self) -> int:
        """
        Get current progress value.
        
        Returns:
            Current progress value
        """
        return self.progress_bar.value()
    
    def get_maximum(self) -> int:
        """
        Get maximum progress value.
        
        Returns:
            Maximum progress value (0 if indeterminate)
        """
        return self.progress_bar.maximum()
    
    def is_indeterminate(self) -> bool:
        """
        Check if progress bar is in indeterminate mode.
        
        Returns:
            True if indeterminate, False otherwise
        """
        return self.progress_bar.maximum() == 0


__all__ = ['ProgressIndicator']

