"""
Loading placeholder widget for tabs that are being loaded.

This widget displays an animated loading indicator while a tab's content
is being initialized, providing visual feedback to the user.
"""

from __future__ import annotations

from typing import Optional

from ...qt_bindings import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
    QTimer,
    QFont,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class PulsingDot(QFrame):
    """A single pulsing dot for the loading indicator."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self._opacity = 0.3
        self._update_style()
    
    def _get_opacity(self) -> float:
        return self._opacity
    
    def _set_opacity(self, value: float) -> None:
        self._opacity = value
        self._update_style()
    
    opacity = Property(float, _get_opacity, _set_opacity)
    
    def _update_style(self) -> None:
        """Update the dot's visual style based on current opacity."""
        try:
            from ...qt_bindings import QApplication, QPalette
            highlight = QApplication.palette().color(QPalette.ColorRole.Highlight)
            r, g, b = highlight.red(), highlight.green(), highlight.blue()
        except Exception:
            r, g, b = 100, 150, 200
            
        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba({r}, {g}, {b}, {self._opacity});
                border-radius: 5px;
                border: none;
            }}
        """)


class LoadingDots(QWidget):
    """Animated loading dots indicator."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create three dots
        self._dots: list[PulsingDot] = []
        self._animations: list[QPropertyAnimation] = []
        
        for i in range(3):
            dot = PulsingDot(self)
            self._dots.append(dot)
            layout.addWidget(dot)
            
            # Create animation for this dot, making the dot the parent so the animation
            # is cleanly destroyed before the target widget is torn down.
            anim = QPropertyAnimation(dot, b"opacity", dot)
            anim.setDuration(600)
            anim.setStartValue(0.3)
            anim.setKeyValueAt(0.5, 1.0)
            anim.setEndValue(0.3)
            anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            anim.setLoopCount(-1)  # Infinite loop
            self._animations.append(anim)
        
        # Start animations with staggered delays
        self._start_animations()
    
    def _start_animations(self) -> None:
        """Start the dot animations with staggered timing."""
        for i, anim in enumerate(self._animations):
            # Use QTimer to stagger the start of each animation
            QTimer.singleShot(i * 150, anim.start)
    
    def stop(self) -> None:
        """Stop all animations."""
        for anim in self._animations:
            try:
                anim.stop()
            except RuntimeError:
                pass


class LoadingPlaceholder(QWidget):
    """Widget that displays an animated loading indicator for a tab.
    
    Features:
    - Animated pulsing dots
    - Centered layout with loading message
    - Theme-aware styling
    - Optional subtitle text
    """

    def __init__(
        self,
        tab_name: str,
        parent: Optional[QWidget] = None,
        subtitle: Optional[str] = None
    ) -> None:
        """Initialize the loading placeholder.
        
        Args:
            tab_name: Name of the tab being loaded
            parent: Parent widget
            subtitle: Optional subtitle text to display below the main message
        """
        super().__init__(parent)
        self._tab_name = tab_name
        
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
        
        # Loading dots
        self._loading_dots = LoadingDots(self)
        center_layout.addWidget(self._loading_dots, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Main loading text
        self._title_label = QLabel(f"Loading {tab_name}...")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setObjectName("loadingTitle")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setWeight(QFont.Weight.Medium)
        self._title_label.setFont(title_font)
        center_layout.addWidget(self._title_label)
        
        # Optional subtitle
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            subtitle_label.setObjectName("loadingSubtitle")
            subtitle_label.setStyleSheet("color: rgba(128, 128, 128, 0.8);")
            subtitle_font = QFont()
            subtitle_font.setPointSize(9)
            subtitle_label.setFont(subtitle_font)
            center_layout.addWidget(subtitle_label)
        
        # Add stretch to center the content
        main_layout.addStretch()
        main_layout.addWidget(center_widget)
        main_layout.addStretch()
        
        # Apply styling
        self._apply_styling()
    
    def _apply_styling(self) -> None:
        """Apply theme-aware styling to the widget."""
        self.setStyleSheet("""
            LoadingPlaceholder {
                background-color: transparent;
            }
            QLabel#loadingTitle {
                color: palette(text);
                background-color: transparent;
            }
            QLabel#loadingSubtitle {
                color: palette(mid);
                background-color: transparent;
            }
        """)
    
    def set_message(self, message: str) -> None:
        """Update the loading message.
        
        Args:
            message: New message to display
        """
        self._title_label.setText(message)
    
    def hideEvent(self, event) -> None:
        """Stop animations when widget is hidden."""
        self._loading_dots.stop()
        super().hideEvent(event)


class LoadingOverlay(QFrame):
    """A loading overlay that can be placed over other content.
    
    Use this when you need to show loading state while keeping
    the underlying content visible but disabled.
    """
    
    def __init__(
        self,
        message: str = "Loading...",
        parent: Optional[QWidget] = None
    ) -> None:
        """Initialize the loading overlay.
        
        Args:
            message: Loading message to display
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Detect theme brightness dynamically
        try:
            from ...qt_bindings import QApplication, QPalette
            window_color = QApplication.palette().color(QPalette.ColorRole.Window)
            is_dark = window_color.lightnessF() < 0.5
        except Exception:
            is_dark = True
            
        bg_color = "rgba(0, 0, 0, 0.5)" if is_dark else "rgba(240, 240, 240, 0.6)"
        
        # Semi-transparent background
        self.setStyleSheet(f"""
            LoadingOverlay {{
                background-color: {bg_color};
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Container for loading content
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: palette(base);
                border-radius: 12px;
                padding: 24px;
            }
        """)
        container.setFixedSize(200, 120)
        
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(16)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Loading dots
        self._loading_dots = LoadingDots(self)
        container_layout.addWidget(
            self._loading_dots,
            alignment=Qt.AlignmentFlag.AlignCenter
        )
        
        # Message
        message_label = QLabel(message)
        message_label.setStyleSheet("color: palette(text); background-color: transparent;")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_font = QFont()
        message_font.setPointSize(10)
        message_label.setFont(message_font)
        container_layout.addWidget(message_label)

        layout.addWidget(container)
    
    def hideEvent(self, event) -> None:
        """Stop animations when overlay is hidden."""
        self._loading_dots.stop()
        super().hideEvent(event)


__all__ = ['LoadingPlaceholder', 'LoadingOverlay', 'LoadingDots']
