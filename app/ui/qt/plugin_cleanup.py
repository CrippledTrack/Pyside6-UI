"""Qt-specific cleanup for plugin-owned timers, threads, and widgets."""

from __future__ import annotations

import logging
from typing import Any

from .bindings import QTimer, QThread, QWidget, is_valid

logger = logging.getLogger(__name__)


class QtPluginResourceCleanup:
    """Implements IPluginResourceCleanup for Qt-hosted plugins."""

    def cleanup(self, plugin: Any) -> None:
        """Stop QTimers/QThreads and dispose the plugin's tab widget."""
        plugin_name = getattr(plugin, "plugin_name", type(plugin).__name__)
        try:
            targets = [plugin]
            widget = getattr(plugin, "_widget", None)
            if widget is not None:
                try:
                    if is_valid(widget):
                        targets.append(widget)
                except Exception:
                    pass

            for target in targets:
                target_label = target.__class__.__name__
                try:
                    attr_names = list(target.__dict__.keys())
                except RuntimeError:
                    continue
                for attr_name in attr_names:
                    try:
                        attr = getattr(target, attr_name, None)
                    except Exception:
                        continue
                    if attr is None:
                        continue

                    if isinstance(attr, QTimer):
                        try:
                            if is_valid(attr) and attr.isActive():
                                attr.stop()
                                logger.debug(
                                    "Automatically stopped active QTimer '%s' on %s "
                                    "for plugin '%s'",
                                    attr_name,
                                    target_label,
                                    plugin_name,
                                )
                        except RuntimeError:
                            pass
                        except Exception as e:
                            logger.warning(f"Error stopping QTimer '{attr_name}': {e}")

                    elif isinstance(attr, QThread):
                        try:
                            if is_valid(attr) and attr.isRunning():
                                attr.quit()
                                if not attr.wait(1000):
                                    logger.warning(
                                        "QThread '%s' on %s for plugin '%s' "
                                        "failed to exit gracefully within timeout",
                                        attr_name,
                                        target_label,
                                        plugin_name,
                                    )
                                else:
                                    logger.debug(
                                        "Automatically stopped active QThread '%s' on %s "
                                        "for plugin '%s'",
                                        attr_name,
                                        target_label,
                                        plugin_name,
                                    )
                        except RuntimeError:
                            pass
                        except Exception as e:
                            logger.warning(f"Error stopping QThread '{attr_name}': {e}")

                    elif isinstance(attr, QWidget) and attr is not widget:
                        # Nested widgets are owned by the tab layout.
                        continue

            if widget is not None:
                try:
                    if is_valid(widget):
                        widget.setParent(None)
                        widget.close()
                        widget.deleteLater()
                except RuntimeError:
                    pass
                except Exception as e:
                    logger.warning(
                        f"Error closing/deleting plugin widget for '{plugin_name}': {e}"
                    )

            if hasattr(plugin, "_widget"):
                plugin._widget = None
        except Exception as e:
            logger.error(f"Error during Qt cleanup of '{plugin_name}': {e}")


__all__ = ["QtPluginResourceCleanup"]
