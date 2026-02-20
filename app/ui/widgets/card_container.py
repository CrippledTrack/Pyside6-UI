"""
Card container widget for creating visually distinct content sections.

This module provides reusable card-style containers that can be used
by plugin tabs to group related content with consistent styling.
"""

from __future__ import annotations

from typing import Optional

from ...qt_bindings import (
    Qt,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class CardContainer(QFrame):
    """A card-style container widget with optional title and consistent styling.
    
    This widget wraps content in a visually distinct card with:
    - Subtle background differentiation from main window
    - Soft border styling (via theme stylesheet)
    - Consistent padding and spacing
    - Optional title header
    
    The visual appearance is controlled by the theme's QFrame#card selector.
    
    Example usage:
        card = CardContainer("Settings", parent=self)
        card.add_widget(QLabel("Some setting"))
        card.add_widget(QPushButton("Apply"))
        layout.addWidget(card)
    """
    
    def __init__(
        self,
        title: Optional[str] = None,
        parent: Optional[QWidget] = None,
        elevated: bool = False,
    ) -> None:
        """Initialize the card container.
        
        Args:
            title: Optional title to display at the top of the card
            parent: Parent widget
            elevated: If True, uses elevated card style with more prominence
        """
        super().__init__(parent)
        
        # Set object name for theme styling
        if elevated:
            self.setObjectName("cardElevated")
        else:
            self.setObjectName("card")
            self.setProperty("card", True)
        
        # Main layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(16, 16, 16, 16)
        self._main_layout.setSpacing(12)
        
        # Title label (if provided)
        self._title_label: Optional[QLabel] = None
        if title:
            self._create_title(title)
        
        # Content layout for child widgets
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(8)
        self._main_layout.addLayout(self._content_layout)
    
    def _create_title(self, title: str) -> None:
        """Create the title label.
        
        Args:
            title: Title text to display
        """
        self._title_label = QLabel(title)
        self._title_label.setObjectName("heading")
        self._title_label.setProperty("heading", True)
        self._main_layout.addWidget(self._title_label)
    
    def set_title(self, title: str) -> None:
        """Set or update the card title.
        
        Args:
            title: New title text
        """
        if self._title_label:
            self._title_label.setText(title)
        else:
            self._create_title(title)
    
    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        """Add a widget to the card content area.
        
        Args:
            widget: Widget to add
            stretch: Stretch factor for the widget
        """
        self._content_layout.addWidget(widget, stretch)
    
    def add_layout(self, layout: QVBoxLayout | QHBoxLayout) -> None:
        """Add a layout to the card content area.
        
        Args:
            layout: Layout to add
        """
        self._content_layout.addLayout(layout)
    
    def add_spacing(self, size: int) -> None:
        """Add fixed spacing to the content area.
        
        Args:
            size: Size of spacing in pixels
        """
        self._content_layout.addSpacing(size)
    
    def add_stretch(self, stretch: int = 1) -> None:
        """Add stretch to the content area.
        
        Args:
            stretch: Stretch factor
        """
        self._content_layout.addStretch(stretch)
    
    def content_layout(self) -> QVBoxLayout:
        """Get the content layout for direct manipulation.
        
        Returns:
            The content layout
        """
        return self._content_layout
    
    def set_content_spacing(self, spacing: int) -> None:
        """Set the spacing between content items.
        
        Args:
            spacing: Spacing in pixels
        """
        self._content_layout.setSpacing(spacing)
    
    def set_content_margins(
        self,
        left: int,
        top: int,
        right: int,
        bottom: int
    ) -> None:
        """Set the content area margins.
        
        Args:
            left: Left margin
            top: Top margin
            right: Right margin
            bottom: Bottom margin
        """
        self._content_layout.setContentsMargins(left, top, right, bottom)


class CardSection(QFrame):
    """A lightweight section divider within a card.
    
    Use this to create visual separation between groups of related
    content within a CardContainer.
    """
    
    def __init__(
        self,
        title: Optional[str] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        """Initialize the card section.
        
        Args:
            title: Optional section title
            parent: Parent widget
        """
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)
        
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("subheading")
            title_label.setProperty("subheading", True)
            layout.addWidget(title_label)
        
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(6)
        layout.addLayout(self._content_layout)
    
    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        """Add a widget to the section.
        
        Args:
            widget: Widget to add
            stretch: Stretch factor
        """
        self._content_layout.addWidget(widget, stretch)
    
    def add_layout(self, layout: QVBoxLayout | QHBoxLayout) -> None:
        """Add a layout to the section.
        
        Args:
            layout: Layout to add
        """
        self._content_layout.addLayout(layout)


class HorizontalCard(QFrame):
    """A horizontal card container for side-by-side content.
    
    Useful for displaying key-value pairs, settings with controls,
    or any content that benefits from horizontal layout.
    """
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        elevated: bool = False,
    ) -> None:
        """Initialize the horizontal card.
        
        Args:
            parent: Parent widget
            elevated: If True, uses elevated styling
        """
        super().__init__(parent)
        
        if elevated:
            self.setObjectName("cardElevated")
        else:
            self.setObjectName("card")
            self.setProperty("card", True)
        
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 12, 16, 12)
        self._layout.setSpacing(12)
    
    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        """Add a widget to the horizontal card.
        
        Args:
            widget: Widget to add
            stretch: Stretch factor
        """
        self._layout.addWidget(widget, stretch)
    
    def add_stretch(self, stretch: int = 1) -> None:
        """Add stretch between widgets.
        
        Args:
            stretch: Stretch factor
        """
        self._layout.addStretch(stretch)
    
    def add_spacing(self, size: int) -> None:
        """Add fixed spacing between widgets.
        
        Args:
            size: Spacing in pixels
        """
        self._layout.addSpacing(size)


class InfoCard(CardContainer):
    """A pre-styled card for displaying information with icon and text.
    
    Provides a consistent way to show informational messages,
    warnings, or status information.
    """
    
    def __init__(
        self,
        title: str,
        message: str,
        info_type: str = "info",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the info card.
        
        Args:
            title: Card title
            message: Main message text
            info_type: Type of info ("info", "success", "warning", "error")
            parent: Parent widget
        """
        super().__init__(title=title, parent=parent)
        
        # Store info type for potential custom styling
        self._info_type = info_type
        self.setProperty("infoType", info_type)
        
        # Message label
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setObjectName("infoMessage")
        self.add_widget(message_label)
    
    def set_message(self, message: str) -> None:
        """Update the message text.
        
        Args:
            message: New message text
        """
        # Find and update the message label
        for i in range(self._content_layout.count()):
            item = self._content_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if widget.objectName() == "infoMessage":
                    widget.setText(message)
                    break


__all__ = [
    'CardContainer',
    'CardSection',
    'HorizontalCard',
    'InfoCard',
]

