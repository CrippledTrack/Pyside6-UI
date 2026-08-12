"""Toolkit-neutral About dialog content and controller."""

from __future__ import annotations

import platform
from typing import Any, Optional

from .. import definitions as ui
from ...utils.about_info import _format_build_time, _read_linux_pretty_name


class AboutDialog:
    """Definitions-backed About dialog controller."""

    def __init__(
        self,
        parent: Any,
        *,
        app_name: str,
        app_version: Optional[str] = None,
        gui_api_version: str,
        platform_name: str,
    ) -> None:
        self.app_name = app_name
        self.app_version = app_version
        self.gui_api_version = gui_api_version
        self.platform_name = platform_name
        self._copy_reset_timer: Any = None
        self.dialog = ui.create_dialog(
            f"About {app_name}",
            parent=parent,
            modal=False,
            default_size=(400, 420),
        )
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = ui.create_column(parent=self.dialog)
        ui.add(
            root,
            ui.create_label(
                self.app_name,
                role=ui.LabelRole.HEADING,
                align="center",
            ),
        )
        if self.app_version:
            ui.add(
                root,
                ui.create_label(
                    f"Version {self.app_version}",
                    role=ui.LabelRole.MUTED,
                    align="center",
                ),
            )

        details = self._collect_details()
        self.plain_text_info = "\n".join(
            [self.app_name, *(f"{label}: {value}" for label, value in details)]
        )

        card = ui.create_card()
        for label, value in details:
            row = ui.create_row()
            ui.add(
                row,
                ui.create_label(
                    f"{label}:",
                    role=ui.LabelRole.FIELD,
                    wrap=False,
                ),
            )
            ui.add_stretch(row)
            ui.add(
                row,
                ui.create_label(value, align="end"),
            )
            ui.add(card, row)
        ui.add(root, card)

        buttons = ui.create_row()
        self._copy_btn = ui.create_button(
            "Copy Info",
            role=ui.ButtonRole.SECONDARY,
            on_click=self.copy_info_to_clipboard,
        )
        ui.add(buttons, self._copy_btn)
        ui.add_stretch(buttons)
        ui.add(
            buttons,
            ui.create_button(
                "Close",
                role=ui.ButtonRole.PRIMARY,
                on_click=lambda: ui.accept_dialog(self.dialog),
            ),
        )
        ui.add(root, buttons)
        ui.set_dialog_content(self.dialog, root)

    def _collect_details(self) -> list[tuple[str, str]]:
        """Gather platform and build details without toolkit widgets."""
        details: list[tuple[str, str]] = []
        if self.app_version:
            details.append(("Version", self.app_version))

        details.append(("GUI API Version", self.gui_api_version))

        from ...utils.display_utils import _format_platform_name

        details.append(("Platform", _format_platform_name(self.platform_name)))

        if str(self.platform_name).lower() == "linux":
            pretty = _read_linux_pretty_name()
            if pretty:
                details.append(("Distro", pretty))

        try:
            from ...utils.admin import is_dev_mode

            dev_mode = is_dev_mode()
        except Exception:
            dev_mode = False

        if dev_mode:
            try:
                from ...build_info import BUILD_DISTRO, BUILD_TIME_UTC, GIT_COMMIT

                if BUILD_DISTRO and BUILD_DISTRO != "unknown":
                    details.append(("Build Distro", BUILD_DISTRO))
                if BUILD_TIME_UTC and BUILD_TIME_UTC != "unknown":
                    details.append(
                        ("Build Time", _format_build_time(BUILD_TIME_UTC))
                    )
                if GIT_COMMIT and GIT_COMMIT != "unknown":
                    is_dirty = GIT_COMMIT.endswith("-dirty")
                    base_commit = GIT_COMMIT[:-6] if is_dirty else GIT_COMMIT
                    if len(base_commit) == 40:
                        base_commit = base_commit[:8]
                    commit = (
                        f"{base_commit}-dirty" if is_dirty else base_commit
                    )
                    details.append(("Git Commit", commit))

                version = platform.python_version()
                implementation = platform.python_implementation()
                architecture = platform.machine() or "unknown"
                details.append(
                    (
                        "Python",
                        f"{implementation} {version} ({architecture})",
                    )
                )
            except Exception:
                pass

        try:
            from ..qt.bindings import get_binding_name

            binding_name = get_binding_name()
        except Exception:
            binding_name = "pyside6"
        if binding_name != "pyside6":
            details.append(("Qt Binding", binding_name))

        return details

    def copy_info_to_clipboard(self) -> None:
        """Copy the formatted plain-text details and briefly confirm."""
        ui.copy_to_clipboard(self.plain_text_info)
        ui.set_text(self._copy_btn, "Copied!")
        if self._copy_reset_timer is not None:
            ui.stop_interval(self._copy_reset_timer)

        def reset_copy_label() -> None:
            ui.set_text(self._copy_btn, "Copy Info")
            ui.stop_interval(self._copy_reset_timer)
            self._copy_reset_timer = None

        self._copy_reset_timer = ui.on_interval(
            reset_copy_label,
            2000,
            parent=self.dialog,
        )

    def close(self) -> None:
        """Close the About dialog."""
        ui.reject_dialog(self.dialog)


def create_about_dialog(
    parent: Any,
    *,
    app_name: str,
    gui_api_version: str,
    platform_name: str,
    app_version: Optional[str] = None,
) -> AboutDialog:
    """Create a configured non-modal definitions-backed About dialog."""
    return AboutDialog(
        parent,
        app_name=app_name,
        app_version=app_version,
        gui_api_version=gui_api_version,
        platform_name=platform_name,
    )


__all__ = ["AboutDialog", "create_about_dialog"]
