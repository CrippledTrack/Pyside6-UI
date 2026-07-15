"""Reusable panel for streaming privileged command output with cancel."""

from __future__ import annotations

import logging
from typing import Callable, List, Optional, Union

from ..bindings import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget, Signal
from ....utils.privileged import (
    cancel_privileged_request,
    run_privileged_command_stream,
)
from ....daemon.client import StreamRequestHandle

logger = logging.getLogger(__name__)


class StreamOutputPanel(QWidget):
    """Log view + Cancel for :func:`run_privileged_command_stream`.

    Runs the privileged stream on a background thread and appends chunks on
    the GUI thread via :attr:`chunk_received`.
    """

    chunk_received = Signal(str)
    finished = Signal(object)  # PrivilegedStreamResult | Exception
    started = Signal(str)  # request_id

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._request_id: Optional[str] = None
        self._worker: Optional[object] = None
        self._setup_ui()
        self.chunk_received.connect(self._append_chunk)
        self.finished.connect(self._on_finished)
        self.started.connect(self._on_started)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.output = QTextEdit(self)
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel", self)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel)
        row.addStretch(1)
        row.addWidget(self.cancel_btn)
        layout.addLayout(row)

    def clear(self) -> None:
        """Clear the log view."""
        self.output.clear()

    def run(
        self,
        command: Union[str, List[str]],
        timeout: int = 300,
        on_done: Optional[Callable[[object], None]] = None,
    ) -> None:
        """Start a streaming privileged command in a background thread."""
        if self.cancel_btn.isEnabled():
            logger.warning("StreamOutputPanel already running")
            return

        self.clear()
        self._request_id = None
        self.cancel_btn.setEnabled(True)
        self._on_done = on_done

        from ..bindings import QThread, QObject, Slot

        panel = self

        class _Worker(QObject):
            def __init__(self) -> None:
                super().__init__()

            @Slot()
            def run(self) -> None:
                try:
                    def on_chunk(line: str) -> None:
                        panel.chunk_received.emit(line)

                    def on_started(handle: StreamRequestHandle) -> None:
                        panel.started.emit(handle.request_id)

                    result = run_privileged_command_stream(
                        command,
                        on_chunk=on_chunk,
                        timeout=timeout,
                        on_started=on_started,
                    )
                    panel.finished.emit(result)
                except Exception as e:
                    panel.finished.emit(e)

        thread = QThread(self)
        worker = _Worker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        self.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._thread = thread
        thread.start()

    def cancel(self) -> None:
        """Cancel the in-flight privileged request, if any."""
        if self._request_id:
            cancel_privileged_request(self._request_id)

    def _append_chunk(self, line: str) -> None:
        self.output.append(line)

    def _on_started(self, request_id: str) -> None:
        self._request_id = request_id

    def _on_finished(self, result: object) -> None:
        self.cancel_btn.setEnabled(False)
        self._request_id = None
        on_done = getattr(self, '_on_done', None)
        if on_done is not None:
            try:
                on_done(result)
            except Exception as e:
                logger.error(f"StreamOutputPanel on_done error: {e}", exc_info=True)


__all__ = ['StreamOutputPanel']
