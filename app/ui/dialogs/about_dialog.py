"""
About dialog widget for display of version, platform, and package information.
"""

from __future__ import annotations

import platform
from typing import Optional

from ...qt_bindings import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QFont,
    Qt,
    QApplication,
    QPalette
)

from ...utils.about_info import (
    _read_linux_pretty_name,
    _format_build_time,
)


class AboutDialog(QDialog):
    """Custom themed About dialog for the application."""
    
    def __init__(
        self,
        parent,
        *,
        app_name: str,
        app_version: Optional[str] = None,
        gui_api_version: str,
        platform_name: str,
    ) -> None:
        super().__init__(parent)
        self.app_name = app_name
        self.app_version = app_version
        self.gui_api_version = gui_api_version
        self.platform_name = platform_name
        
        self.setWindowTitle(f"About {app_name}")
        self.setMinimumWidth(380)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        self.setup_ui()
        self.apply_theme()
        
    def setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 20)
        main_layout.setSpacing(16)
        
        # App Title and Header
        self._title_label = QLabel(self.app_name)
        self._title_label.setObjectName("aboutTitle")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setWeight(QFont.Weight.Bold)
        self._title_label.setFont(title_font)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self._title_label)
        
        # Subtitle with version if available
        if self.app_version:
            self._version_label = QLabel(f"Version {self.app_version}")
            self._version_label.setObjectName("aboutVersion")
            version_font = QFont()
            version_font.setPointSize(10)
            version_font.setWeight(QFont.Weight.Medium)
            self._version_label.setFont(version_font)
            self._version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(self._version_label)
            
        # Grouped Fields Frame
        fields_frame = QFrame()
        fields_frame.setObjectName("aboutFieldsFrame")
        fields_layout = QVBoxLayout(fields_frame)
        fields_layout.setContentsMargins(16, 16, 16, 16)
        fields_layout.setSpacing(10)
        
        # Gather platform & build details
        details = []
        if self.app_version:
            details.append(("Version", self.app_version))
            
        details.append(("GUI API Version", self.gui_api_version))
        
        from ...utils.display_utils import _format_platform_name
        pretty_platform = _format_platform_name(self.platform_name)
        details.append(("Platform", pretty_platform))
        
        if str(self.platform_name).lower() == "linux":
            pretty = _read_linux_pretty_name()
            if pretty:
                details.append(("Distro", pretty))
                
        # Dev-only build details
        try:
            from ...utils.admin import is_dev_mode
            dev_mode = is_dev_mode()
        except Exception:
            dev_mode = False
            
        if dev_mode:
            try:
                from ...build_info import BUILD_DISTRO, BUILD_TIME_UTC, GIT_COMMIT
                
                # Distribution & Build Time
                if BUILD_DISTRO and BUILD_DISTRO != "unknown":
                    details.append(("Build Distro", BUILD_DISTRO))
                if BUILD_TIME_UTC and BUILD_TIME_UTC != "unknown":
                    details.append(("Build Time", _format_build_time(BUILD_TIME_UTC)))
                    
                # Git commit details
                if GIT_COMMIT and GIT_COMMIT != "unknown":
                    is_dirty = GIT_COMMIT.endswith("-dirty")
                    base_commit = GIT_COMMIT[:-6] if is_dirty else GIT_COMMIT
                    if len(base_commit) == 40:
                        base_commit = base_commit[:8]
                    commit_str = f"{base_commit}-dirty" if is_dirty else base_commit
                    details.append(("Git Commit", commit_str))
                    
                # Python details
                version = platform.python_version()
                impl = platform.python_implementation()
                arch = platform.machine() or "unknown"
                details.append(("Python", f"{impl} {version} ({arch})"))
            except Exception:
                pass
                
        # Qt bindings
        try:
            from ...qt_bindings import get_binding_name
            binding_name = get_binding_name()
        except Exception:
            binding_name = "pyside6"
        if binding_name != "pyside6":
            details.append(("Qt Binding", binding_name))
            
        self.plain_text_info = ""
        self.plain_text_info += f"{self.app_name}\n"
        
        # Add details to grid/layout
        for label, val in details:
            self.plain_text_info += f"{label}: {val}\n"
            
            row = QHBoxLayout()
            lbl_widget = QLabel(f"{label}:")
            lbl_widget.setObjectName("fieldLabel")
            lbl_font = QFont()
            lbl_font.setPointSize(9)
            lbl_font.setWeight(QFont.Weight.Bold)
            lbl_widget.setFont(lbl_font)
            
            val_widget = QLabel(val)
            val_widget.setObjectName("fieldValue")
            val_widget.setWordWrap(True)
            val_font = QFont()
            val_font.setPointSize(9)
            val_widget.setFont(val_font)
            
            row.addWidget(lbl_widget)
            row.addStretch()
            row.addWidget(val_widget)
            fields_layout.addLayout(row)
            
        main_layout.addWidget(fields_frame)
        
        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self._copy_btn = QPushButton("Copy Info")
        self._copy_btn.setObjectName("copyBtn")
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.clicked.connect(self.copy_info_to_clipboard)
        btn_layout.addWidget(self._copy_btn)
        
        btn_layout.addStretch()
        
        self._close_btn = QPushButton("Close")
        self._close_btn.setObjectName("closeBtn")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self._close_btn)
        
        main_layout.addLayout(btn_layout)
        
    def copy_info_to_clipboard(self) -> None:
        """Copy the formatted plain-text info to the clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.plain_text_info)
        self._copy_btn.setText("Copied!")
        from ...qt_bindings import QTimer
        QTimer.singleShot(2000, lambda: self._copy_btn.setText("Copy Info"))
        
    def apply_theme(self) -> None:
        """Apply theme-aware styling to the About dialog."""
        try:
            highlight = QApplication.palette().color(QPalette.ColorRole.Highlight).name()
            from ....themes.theme_manager import ThemeManager
            highlight_hover = ThemeManager.adjust_color(highlight, 1.15)
            highlight_pressed = ThemeManager.adjust_color(highlight, 0.85)
            highlighted_text = QApplication.palette().color(QPalette.ColorRole.HighlightedText).name()
            
            # Detect theme brightness to improve readability of secondary labels
            window_color = QApplication.palette().color(QPalette.ColorRole.Window)
            is_dark = window_color.lightnessF() < 0.5
        except Exception:
            highlight = "#3182ce"
            highlight_hover = "#4299e1"
            highlight_pressed = "#2b6cb0"
            highlighted_text = "#ffffff"
            is_dark = True
            
        # Use white in dark mode for subtitle and labels to maximize readability
        secondary_color = "#ffffff" if is_dark else "palette(mid)"
            
        self.setStyleSheet(f"""
            AboutDialog {{
                background-color: palette(window);
            }}
            QLabel#aboutTitle {{
                color: palette(text);
                margin-top: 10px;
            }}
            QLabel#aboutVersion {{
                color: {secondary_color};
            }}
            QFrame#aboutFieldsFrame {{
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 8px;
            }}
            QLabel#fieldLabel {{
                color: {secondary_color};
            }}
            QLabel#fieldValue {{
                color: palette(text);
            }}
            QPushButton#copyBtn, QPushButton#closeBtn {{
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: 500;
            }}
            QPushButton#copyBtn {{
                background-color: transparent;
                border: 1px solid palette(mid);
                color: palette(text);
            }}
            QPushButton#copyBtn:hover {{
                background-color: rgba(128, 128, 128, 0.15);
            }}
            QPushButton#closeBtn {{
                background-color: {highlight};
                color: {highlighted_text};
                border: none;
            }}
            QPushButton#closeBtn:hover {{
                background-color: {highlight_hover};
            }}
            QPushButton#closeBtn:pressed {{
                background-color: {highlight_pressed};
            }}
        """)


def create_about_dialog(
    parent,
    *,
    app_name: str,
    gui_api_version: str,
    platform_name: str,
    app_version: Optional[str] = None,
) -> AboutDialog:
    """Create a configured non-modal About QDialog.

    Kept here to keep `main_window.py` focused on UI wiring.
    """
    return AboutDialog(
        parent,
        app_name=app_name,
        app_version=app_version,
        gui_api_version=gui_api_version,
        platform_name=platform_name,
    )
