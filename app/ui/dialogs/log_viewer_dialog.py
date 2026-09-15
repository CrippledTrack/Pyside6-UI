"""Definitions-backed log viewer with toolkit-neutral live log marshaling."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from .. import definitions as ui
from ..abstractions import IUIEventLoop
from ...services.logging_service import CustomFormatter, LOG_FORMAT
from ...utils.paths import logs_dir

logger = logging.getLogger(__name__)


class UIThreadLogHandler(logging.Handler):
    """Forward log records onto the UI main thread via :class:`IUIEventLoop`."""

    def __init__(
        self,
        event_loop: IUIEventLoop,
        callback: Callable[[str, int], None],
    ) -> None:
        super().__init__()
        self._event_loop = event_loop
        self._callback = callback
        self.setFormatter(CustomFormatter(LOG_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            level = record.levelno
            self._event_loop.invoke_on_main(self._callback, message, level)
        except Exception:
            self.handleError(record)


class LogViewerDialog:
    """Definitions-backed controller for browsing and tailing application logs."""

    def __init__(
        self,
        parent: Any = None,
        *,
        event_loop: IUIEventLoop,
    ) -> None:
        self._event_loop = event_loop
        self._auto_scroll = True
        self._min_level = logging.DEBUG
        self._paused = False
        self._pending_logs: list[tuple[str, int]] = []
        self._current_log_file: Optional[Path] = None
        self._is_viewing_current = True
        self._available_logs: list[Path] = []
        self._last_guessed_level = logging.INFO
        self._updating_files = False
        self._closed = False

        self.dialog = ui.create_dialog(
            "Log Viewer",
            parent=parent,
            modal=False,
            default_size=(1000, 700),
        )
        self._setup_ui()

        self._log_handler = UIThreadLogHandler(event_loop, self._on_new_log)
        logging.getLogger().addHandler(self._log_handler)
        self._refresh_log_files()
        logger.debug("Log viewer dialog opened")

    def _setup_ui(self) -> None:
        root = ui.create_column(parent=self.dialog, expand=True)

        file_toolbar = ui.create_row()
        ui.add(file_toolbar, ui.create_label("Log File:"))
        self._file_combo = ui.create_combo()
        ui.set_expand(self._file_combo)
        ui.on_change(self._file_combo, self._on_file_changed)
        ui.add(file_toolbar, self._file_combo)

        refresh_btn = ui.create_button(
            "Refresh",
            on_click=self._refresh_log_files,
        )
        ui.set_tooltip(refresh_btn, "Refresh the list of available log files")
        ui.add(file_toolbar, refresh_btn)

        self._live_label = ui.create_label(
            "● LIVE",
            role=ui.LabelRole.SUCCESS,
            wrap=False,
        )
        ui.set_tooltip(
            self._live_label,
            "Live updates enabled - viewing current session log",
        )
        ui.add(file_toolbar, self._live_label)
        ui.add_stretch(file_toolbar)
        ui.add(root, file_toolbar)

        controls = ui.create_row()
        ui.add(controls, ui.create_label("Filter Level:"))
        self._level_combo = ui.create_combo(
            [
                ("DEBUG", logging.DEBUG),
                ("INFO", logging.INFO),
                ("WARNING", logging.WARNING),
                ("ERROR", logging.ERROR),
                ("CRITICAL", logging.CRITICAL),
            ]
        )
        ui.on_change(self._level_combo, self._on_level_changed)
        ui.add(controls, self._level_combo)

        self._auto_scroll_cb = ui.create_checkbox(
            "Auto-scroll",
            checked=True,
        )
        ui.on_change(self._auto_scroll_cb, self._on_auto_scroll_changed)
        ui.add(controls, self._auto_scroll_cb)

        self._pause_btn = ui.create_button(
            "Pause",
            on_click=self._on_pause_clicked,
        )
        ui.add(controls, self._pause_btn)
        ui.add_stretch(controls)
        ui.add(
            controls,
            ui.create_button("Clear", on_click=self._on_clear_clicked),
        )
        ui.add(
            controls,
            ui.create_button("Export...", on_click=self._on_export_clicked),
        )
        ui.add(root, controls)

        self._log_display = ui.create_text_area(
            read_only=True,
            expand=True,
            wrap=False,
            monospace=True,
        )
        ui.add(root, self._log_display)

        status_row = ui.create_row()
        self._status_label = ui.create_label("Ready", wrap=False)
        ui.add(status_row, self._status_label)
        ui.add_stretch(status_row)
        ui.add(
            status_row,
            ui.create_button("Close", on_click=self.close),
        )
        ui.add(root, status_row)
        ui.set_dialog_content(self.dialog, root)

    def _refresh_log_files(self) -> None:
        """Refresh available log files, newest first."""
        try:
            log_path = logs_dir()
            if not log_path.exists():
                ui.set_text(self._status_label, "No logs directory found")
                ui.set_items(self._file_combo, [])
                return

            self._available_logs = sorted(
                [path for path in log_path.glob("app_*.log*") if path.is_file()],
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if not self._available_logs:
                ui.set_text(self._status_label, "No log files found")
                ui.set_items(self._file_combo, [])
                return

            current = ui.get_value(self._file_combo)
            items: list[ui.ComboItem] = [
                (
                    (
                        f"{log_file.name} (Current Session)"
                        if index == 0
                        else log_file.name
                    ),
                    log_file,
                )
                for index, log_file in enumerate(self._available_logs)
            ]

            self._updating_files = True
            try:
                ui.set_items(self._file_combo, items)
                selection = (
                    current
                    if current in self._available_logs
                    else self._available_logs[0]
                )
                ui.set_value(self._file_combo, selection)
            finally:
                self._updating_files = False
            self._load_selected_log()
        except Exception as exc:
            logger.error("Failed to refresh log files: %s", exc)
            ui.set_text(self._status_label, f"Error: {exc}")

    def _on_file_changed(self, _value: Any = None) -> None:
        if not self._updating_files:
            self._load_selected_log()

    def _load_selected_log(self) -> None:
        selected_file = ui.get_value(self._file_combo)
        if not isinstance(selected_file, Path) or not selected_file.exists():
            return

        self._current_log_file = selected_file
        self._is_viewing_current = bool(
            self._available_logs and selected_file == self._available_logs[0]
        )
        if self._is_viewing_current:
            ui.set_text(self._live_label, "● LIVE")
            ui.apply_label_role(self._live_label, ui.LabelRole.SUCCESS)
            ui.set_tooltip(
                self._live_label,
                "Live updates enabled - viewing current session log",
            )
            ui.set_enabled(self._pause_btn, True)
        else:
            ui.set_text(self._live_label, "● STATIC")
            ui.apply_label_role(self._live_label, ui.LabelRole.MUTED)
            ui.set_tooltip(
                self._live_label,
                "Viewing historical log - no live updates",
            )
            ui.set_enabled(self._pause_btn, False)
            self._paused = False
            ui.set_text(self._pause_btn, "Pause")

        ui.clear_text(self._log_display)
        self._pending_logs.clear()
        try:
            ui.set_text(self._status_label, f"Loading: {selected_file.name}")
            with selected_file.open(
                "r",
                encoding="utf-8",
                errors="replace",
            ) as log_file:
                for line in log_file:
                    self._append_log_line(
                        line.rstrip(),
                        self._guess_level(line),
                    )
            if self._auto_scroll:
                ui.scroll_to_end(self._log_display)
            ui.set_text(self._status_label, f"Viewing: {selected_file.name}")
        except Exception as exc:
            logger.error("Failed to load log file: %s", exc)
            ui.set_text(
                self._status_label,
                f"Error loading logs: {exc}",
            )

    def _guess_level(self, line: str) -> int:
        for marker, level in (
            (" - DEBUG - ", logging.DEBUG),
            (" - INFO - ", logging.INFO),
            (" - WARNING - ", logging.WARNING),
            (" - ERROR - ", logging.ERROR),
            (" - CRITICAL - ", logging.CRITICAL),
        ):
            if marker in line:
                self._last_guessed_level = level
                return level
        if line and not line[0].isdigit():
            return self._last_guessed_level
        return logging.INFO

    def _append_log_line(self, text: str, level: int) -> None:
        if level < self._min_level:
            return
        ui.append_log_text(self._log_display, text, level=level)
        if self._auto_scroll:
            ui.scroll_to_end(self._log_display)

    def _on_new_log(self, message: str, level: int) -> None:
        if self._closed:
            return
        if not self._is_viewing_current:
            return
        if self._paused:
            self._pending_logs.append((message, level))
            ui.set_text(
                self._status_label,
                f"Paused ({len(self._pending_logs)} pending)",
            )
        else:
            self._append_log_line(message, level)

    def _on_level_changed(self, _value: Any = None) -> None:
        value = ui.get_value(self._level_combo)
        self._min_level = int(value)
        self._load_selected_log()

    def _on_auto_scroll_changed(self, checked: Any) -> None:
        self._auto_scroll = bool(checked)
        if self._auto_scroll:
            ui.scroll_to_end(self._log_display)

    def _on_pause_clicked(self) -> None:
        self._paused = not self._paused
        ui.set_text(self._pause_btn, "Resume" if self._paused else "Pause")
        if not self._paused and self._pending_logs:
            for message, level in self._pending_logs:
                self._append_log_line(message, level)
            self._pending_logs.clear()
            if self._current_log_file:
                ui.set_text(
                    self._status_label,
                    f"Viewing: {self._current_log_file.name}",
                )

    def _on_clear_clicked(self) -> None:
        ui.clear_text(self._log_display)
        self._pending_logs.clear()

    def _on_export_clicked(self) -> None:
        file_path = ui.pick_save_file(
            "Export Logs",
            parent=self.dialog,
            default_name=str(Path.home() / "logs_export.txt"),
            name_filter="Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return
        try:
            Path(file_path).write_text(
                ui.get_text(self._log_display),
                encoding="utf-8",
            )
            ui.set_text(
                self._status_label,
                f"Exported to {Path(file_path).name}",
            )
        except Exception as exc:
            ui.set_text(self._status_label, f"Export failed: {exc}")

    def on_closed(self) -> None:
        """Remove the live logging handler exactly once."""
        if self._closed:
            return
        self._closed = True
        logging.getLogger().removeHandler(self._log_handler)
        logger.debug("Log viewer dialog closed")

    def close(self) -> None:
        ui.reject_dialog(self.dialog)


__all__ = ["LogViewerDialog", "UIThreadLogHandler"]
