"""
Example plugin for Basic GUI Application.

This demonstrates how to create a simple tab plugin.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit
from GUI.plugins.base import BaseTabPlugin


class ExampleTabPlugin(BaseTabPlugin):
    """Example tab plugin demonstrating the plugin interface."""
    
    tab_name = "Example Plugin"
    tab_description = "A simple example plugin showing how to create custom tabs"
    supported_platforms = ["Windows", "Linux"]
    requires_admin = False
    plugin_version = "1.0.1"
    plugin_author = "Example Author"
    min_gui_version = "3.0.0"
    # Optional: set to True to have the plugin appear disabled by default
    disabled_by_default = True
    
    # required_gui_version: Advanced range specification (takes precedence over min_gui_version)
    # Examples:
    #   ">=3.0.0"           - At least version 3.0.0
    #   ">=3.0.0,<4.0.0"    - At least 3.0.0 but less than 4.0.0
    #   "==3.0.0"           - Exactly version 3.0.0
    #   ">2.0.0,<3.5.0"     - Greater than 2.0.0 but less than 3.5.0
    # required_gui_version = ">=3.0.0,<4.0.0"

    @classmethod
    def create_widget(cls, parent: Optional[QWidget] = None) -> QWidget:
        """Create the widget for this tab."""
        return ExampleWidget(parent)


class ExampleWidget(QWidget):
    """The actual widget displayed in the tab."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Title label
        title_label = QLabel("Example Plugin")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(
            "This is an example plugin that demonstrates how to create custom tabs "
            "for the Basic GUI Application. You can create your own plugins by:"
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Instructions
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setMaximumHeight(200)
        instructions.setPlainText("""
1. Create a new Python file in the plugins/ directory
2. Import BaseTabPlugin from plugins.base
3. Create a class that inherits from BaseTabPlugin
4. Set the required class attributes (tab_name, supported_platforms, etc.)
5. Implement the create_widget() classmethod
6. Create a QWidget subclass for your tab's UI
7. Restart the application to see your plugin

For entry point plugins (installable packages):
- Add an entry point in your setup.py or pyproject.toml
- Use the group name "basic_gui_tabs"
- Point to your plugin class
        """)
        layout.addWidget(instructions)
        
        # Interactive button
        self.test_button = QPushButton("Test Plugin Functionality")
        self.test_button.clicked.connect(self.on_test_clicked)
        layout.addWidget(self.test_button)
        
        # Output area
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setMaximumHeight(100)
        self.output_area.setPlainText("Click the button above to test the plugin...")
        layout.addWidget(self.output_area)
    
    def on_test_clicked(self):
        """Handle test button click."""
        self.output_area.setPlainText(
            f"Plugin test successful!\n"
            f"Tab name: {ExampleTabPlugin.tab_name}\n"
            f"Version: {ExampleTabPlugin.plugin_version}\n"
            f"Author: {ExampleTabPlugin.plugin_author}\n"
            f"Platform support: {', '.join(ExampleTabPlugin.supported_platforms)}"
        ) 