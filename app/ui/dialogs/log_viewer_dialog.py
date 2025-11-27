"""
Log viewer dialog with live tail functionality.

This module provides a dialog for viewing application logs in real-time,
with filtering by log level and auto-scroll support.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QComboBox,
    QPushButton,
    QLabel,
    QCheckBox,
    QWidget,
    QFileDialog,
)

from ...utils.paths import logs_dir

logger = logging.getLogger(__name__)


class SignalHandler(QObject, logging.Handler):
    """Logging handler that emits Qt signals for new log entries."""
    
    new_log = Signal(str, int)  # message, level
    
    def __init__(self):
        QObject.__init__(self)
        logging.Handler.__init__(self)
        self.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(threadName)s] - %(name)s - %(message)s"
        ))
    
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.new_log.emit(msg, record.levelno)
        except Exception:
            self.handleError(record)


class LogViewerDialog(QDialog):
    """Dialog for viewing application logs with live tail functionality."""
    
    # Log level colors
    LEVEL_COLORS = {
        logging.DEBUG: "#6c757d",     # Gray
        logging.INFO: "#28a745",      # Green
        logging.WARNING: "#ffc107",   # Yellow/Orange
        logging.ERROR: "#dc3545",     # Red
        logging.CRITICAL: "#9c27b0",  # Purple
    }
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Log Viewer")
        self.setMinimumSize(900, 600)
        self.resize(1000, 700)
        
        # Make non-modal so main window is still usable
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        # State
        self._auto_scroll = True
        self._min_level = logging.DEBUG
        self._paused = False
        self._pending_logs: List[tuple] = []  # Buffer for when paused
        self._current_log_file: Optional[Path] = None
        self._is_viewing_current = True  # True if viewing the most recent log
        self._available_logs: List[Path] = []
        
        # Setup UI
        self._setup_ui()
        
        # Setup signal handler for live logs
        self._signal_handler = SignalHandler()
        self._signal_handler.new_log.connect(self._on_new_log)
        logging.getLogger().addHandler(self._signal_handler)
        
        # Populate log file selector and load current log
        self._refresh_log_files()
        
        logger.debug("Log viewer dialog opened")
    
    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Top toolbar - Row 1: File selection
        file_toolbar = QHBoxLayout()
        file_toolbar.setSpacing(10)
        
        file_toolbar.addWidget(QLabel("Log File:"))
        self._file_combo = QComboBox()
        self._file_combo.setMinimumWidth(250)
        self._file_combo.currentIndexChanged.connect(self._on_file_changed)
        file_toolbar.addWidget(self._file_combo)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setToolTip("Refresh the list of available log files")
        refresh_btn.clicked.connect(self._refresh_log_files)
        file_toolbar.addWidget(refresh_btn)
        
        # Live indicator
        self._live_label = QLabel("● LIVE")
        self._live_label.setStyleSheet("color: #28a745; font-weight: bold;")
        self._live_label.setToolTip("Live updates enabled - viewing current session log")
        file_toolbar.addWidget(self._live_label)
        
        file_toolbar.addStretch()
        layout.addLayout(file_toolbar)
        
        # Top toolbar - Row 2: Filters and controls
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        
        # Level filter
        toolbar.addWidget(QLabel("Filter Level:"))
        self._level_combo = QComboBox()
        self._level_combo.addItem("DEBUG", logging.DEBUG)
        self._level_combo.addItem("INFO", logging.INFO)
        self._level_combo.addItem("WARNING", logging.WARNING)
        self._level_combo.addItem("ERROR", logging.ERROR)
        self._level_combo.addItem("CRITICAL", logging.CRITICAL)
        self._level_combo.setCurrentIndex(0)  # DEBUG by default
        self._level_combo.currentIndexChanged.connect(self._on_level_changed)
        toolbar.addWidget(self._level_combo)
        
        toolbar.addSpacing(20)
        
        # Auto-scroll checkbox
        self._auto_scroll_cb = QCheckBox("Auto-scroll")
        self._auto_scroll_cb.setChecked(True)
        self._auto_scroll_cb.stateChanged.connect(self._on_auto_scroll_changed)
        toolbar.addWidget(self._auto_scroll_cb)
        
        # Pause button
        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setCheckable(True)
        self._pause_btn.clicked.connect(self._on_pause_clicked)
        toolbar.addWidget(self._pause_btn)
        
        toolbar.addStretch()
        
        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._on_clear_clicked)
        toolbar.addWidget(clear_btn)
        
        # Export button
        export_btn = QPushButton("Export...")
        export_btn.clicked.connect(self._on_export_clicked)
        toolbar.addWidget(export_btn)
        
        layout.addLayout(toolbar)
        
        # Log display
        self._log_display = QPlainTextEdit()
        self._log_display.setReadOnly(True)
        self._log_display.setFont(QFont("Consolas", 9) if self._font_exists("Consolas") 
                                   else QFont("Monospace", 9))
        self._log_display.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._log_display.setMaximumBlockCount(10000)  # Limit memory usage
        layout.addWidget(self._log_display)
        
        # Bottom status bar
        status_layout = QHBoxLayout()
        self._status_label = QLabel("Ready")
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        status_layout.addWidget(close_btn)
        
        layout.addLayout(status_layout)
    
    def _font_exists(self, font_name: str) -> bool:
        """Check if a font exists on the system."""
        from PySide6.QtGui import QFontDatabase
        return font_name in QFontDatabase.families()
    
    def _refresh_log_files(self) -> None:
        """Refresh the list of available log files."""
        try:
            log_path = logs_dir()
            if not log_path.exists():
                self._status_label.setText("No logs directory found")
                return
            
            # Find all log files, sorted by modification time (newest first)
            self._available_logs = sorted(
                log_path.glob("app_*.log"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            if not self._available_logs:
                self._status_label.setText("No log files found")
                return
            
            # Remember current selection
            current_selection = self._file_combo.currentData()
            
            # Update combo box
            self._file_combo.blockSignals(True)
            self._file_combo.clear()
            
            for i, log_file in enumerate(self._available_logs):
                # Mark the most recent as "(Current Session)"
                if i == 0:
                    display_name = f"{log_file.name} (Current Session)"
                else:
                    display_name = log_file.name
                self._file_combo.addItem(display_name, log_file)
            
            # Restore selection or select first
            if current_selection:
                for i in range(self._file_combo.count()):
                    if self._file_combo.itemData(i) == current_selection:
                        self._file_combo.setCurrentIndex(i)
                        break
            else:
                self._file_combo.setCurrentIndex(0)
            
            self._file_combo.blockSignals(False)
            
            # Load the selected file
            self._load_selected_log()
            
        except Exception as e:
            logger.error(f"Failed to refresh log files: {e}")
            self._status_label.setText(f"Error: {e}")
    
    def _on_file_changed(self, index: int) -> None:
        """Handle log file selection change."""
        self._load_selected_log()
    
    def _load_selected_log(self) -> None:
        """Load the currently selected log file."""
        if self._file_combo.count() == 0:
            return
        
        selected_file = self._file_combo.currentData()
        if not selected_file or not selected_file.exists():
            return
        
        self._current_log_file = selected_file
        
        # Check if this is the current session log (first in list)
        self._is_viewing_current = (self._file_combo.currentIndex() == 0)
        
        # Update live indicator
        if self._is_viewing_current:
            self._live_label.setText("● LIVE")
            self._live_label.setStyleSheet("color: #28a745; font-weight: bold;")
            self._live_label.setToolTip("Live updates enabled - viewing current session log")
            self._pause_btn.setEnabled(True)
        else:
            self._live_label.setText("● STATIC")
            self._live_label.setStyleSheet("color: #6c757d; font-weight: bold;")
            self._live_label.setToolTip("Viewing historical log - no live updates")
            self._pause_btn.setEnabled(False)
            self._pause_btn.setChecked(False)
            self._paused = False
        
        # Clear and reload
        self._log_display.clear()
        self._pending_logs.clear()
        
        try:
            self._status_label.setText(f"Loading: {selected_file.name}")
            
            # Read and display content
            with open(selected_file, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    self._append_log_line(line.rstrip(), self._guess_level(line))
            
            # Scroll to bottom
            if self._auto_scroll:
                self._scroll_to_bottom()
            
            self._status_label.setText(f"Viewing: {selected_file.name}")
            
        except Exception as e:
            logger.error(f"Failed to load log file: {e}")
            self._status_label.setText(f"Error loading logs: {e}")
    
    def _guess_level(self, line: str) -> int:
        """Guess the log level from a log line."""
        if " - DEBUG - " in line:
            return logging.DEBUG
        elif " - INFO - " in line:
            return logging.INFO
        elif " - WARNING - " in line:
            return logging.WARNING
        elif " - ERROR - " in line:
            return logging.ERROR
        elif " - CRITICAL - " in line:
            return logging.CRITICAL
        return logging.INFO
    
    def _append_log_line(self, text: str, level: int) -> None:
        """Append a log line with appropriate coloring."""
        if level < self._min_level:
            return
        
        # Get color for level
        color = self.LEVEL_COLORS.get(level, "#000000")
        
        # Create formatted text
        cursor = self._log_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Set format
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        
        cursor.insertText(text + "\n", fmt)
        
        if self._auto_scroll:
            self._scroll_to_bottom()
    
    def _scroll_to_bottom(self) -> None:
        """Scroll the log display to the bottom."""
        scrollbar = self._log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _on_new_log(self, message: str, level: int) -> None:
        """Handle new log entry from signal handler."""
        # Only show live updates when viewing current session log
        if not self._is_viewing_current:
            return
        
        if self._paused:
            self._pending_logs.append((message, level))
            self._status_label.setText(f"Paused ({len(self._pending_logs)} pending)")
        else:
            self._append_log_line(message, level)
    
    def _on_level_changed(self, index: int) -> None:
        """Handle log level filter change."""
        self._min_level = self._level_combo.currentData()
        # Reload to apply filter
        self._load_selected_log()
    
    def _on_auto_scroll_changed(self, state: int) -> None:
        """Handle auto-scroll checkbox change."""
        self._auto_scroll = state == Qt.CheckState.Checked.value
        if self._auto_scroll:
            self._scroll_to_bottom()
    
    def _on_pause_clicked(self, checked: bool) -> None:
        """Handle pause button click."""
        self._paused = checked
        self._pause_btn.setText("Resume" if checked else "Pause")
        
        if not checked and self._pending_logs:
            # Flush pending logs
            for message, level in self._pending_logs:
                self._append_log_line(message, level)
            self._pending_logs.clear()
            if self._current_log_file:
                self._status_label.setText(f"Viewing: {self._current_log_file.name}")
    
    def _on_clear_clicked(self) -> None:
        """Handle clear button click."""
        self._log_display.clear()
        self._pending_logs.clear()
    
    def _on_export_clicked(self) -> None:
        """Handle export button click."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Logs",
            str(Path.home() / "logs_export.txt"),
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self._log_display.toPlainText())
                self._status_label.setText(f"Exported to {Path(file_path).name}")
            except Exception as e:
                self._status_label.setText(f"Export failed: {e}")
    
    def closeEvent(self, event) -> None:
        """Clean up when dialog is closed."""
        # Remove our handler from the root logger
        logging.getLogger().removeHandler(self._signal_handler)
        logger.debug("Log viewer dialog closed")
        super().closeEvent(event)


__all__ = ['LogViewerDialog']
