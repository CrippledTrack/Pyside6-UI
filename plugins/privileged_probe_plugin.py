"""Sample plugin that exercises the privileged pipe daemon.

Loaded only in runtime dev mode (non-frozen). Clicking the button runs
``id`` via ``run_privileged_command`` so hosts can verify elevation
without adding product tabs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..app.ui.definitions import (
    LabelRole,
    add,
    create_button,
    create_label,
    create_text_area,
    set_text,
    tab_root,
)
from ..plugin_system.base import BaseTabPlugin
from ..plugin_system.types import TabContent, TabCreateContext

if TYPE_CHECKING:
    from ..app.services.container import ServiceContainer

logger = logging.getLogger(__name__)


class PrivilegedProbePlugin(BaseTabPlugin):
    """Runs ``id`` through the privileged daemon."""

    plugin_name = "Privileged Probe"
    plugin_id = "gui.example.privileged"
    tab_title = "Privileged Probe"
    plugin_description = (
        "Sample tab that runs `id` via the privileged pipe daemon. "
        "Start the daemon from the Admin menu first."
    )
    supported_platforms = ["Windows", "Linux", "macOS"]
    requires_admin = True
    plugin_version = "1.0.0"
    plugin_author = "GUI"
    min_gui_version = "6.0.0"
    required_gui_version = ">=6.0.0"
    disabled_by_default = False

    def __init__(self, container: "ServiceContainer") -> None:
        super().__init__(container)
        self._output = None

    def create_tab_content(self, context: TabCreateContext) -> TabContent:
        root = tab_root(context)
        add(
            root,
            create_label("Privileged Probe", role=LabelRole.HEADING),
        )
        add(
            root,
            create_label(
                "Start the privileged daemon from the Admin menu, then run "
                "`id` as root. Output should include uid=0(root).",
                role=LabelRole.BODY,
            ),
        )
        add(
            root,
            create_button("Run id as root", on_click=self._run_id),
        )
        self._output = create_text_area(read_only=True, expand=True)
        add(root, self._output)
        return root

    def _run_id(self) -> None:
        if self._output is None:
            return
        try:
            from ..app.utils.privileged import run_privileged_command

            result = run_privileged_command(["id"], timeout=30)
            text = (result.stdout or "").strip() or (result.stderr or "").strip()
            if not text:
                text = f"(no output) returncode={result.returncode}"
            set_text(self._output, text)
        except Exception as e:
            logger.error("Privileged id failed: %s", e, exc_info=True)
            set_text(self._output, str(e))


__all__ = ["PrivilegedProbePlugin"]
