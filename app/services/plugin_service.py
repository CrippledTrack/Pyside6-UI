"""
Plugin discovery and registration service.

This module provides functionality for discovering plugins from multiple sources
(core plugins from app_plugins/core_plugins.py and GUI/plugins/core_plugins.py,
entry point plugins, and local plugin files) and registering them with the
plugin registry.

Legacy support: This module maintains backwards compatibility with the old
'platforms/' folder name (deprecated, 3.0.0 compatibility) but prefers the
new 'app_plugins/' name.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Tuple, Type

from ...plugins import plugin_registry

logger = logging.getLogger(__name__)


@contextmanager
def _with_sys_path(path: Path):
    """Context manager for temporarily adding a path to sys.path."""
    path_str = str(path)
    was_in_path = path_str in sys.path
    if not was_in_path:
        sys.path.insert(0, path_str)
    try:
        yield
    finally:
        if not was_in_path and path_str in sys.path:
            sys.path.remove(path_str)


def _load_core_plugins_from_source(source: str) -> List[Type[Any]]:
    """Load core plugins from a specific source.
    
    Args:
        source: Either 'platforms' (for app_plugins/, with legacy fallback) or 'gui'
        
    Returns:
        List of plugin classes, empty list on error
    """
    try:
        if source == "platforms":
            parent_dir = Path(__file__).parent.parent.parent
            with _with_sys_path(parent_dir):
                # Try new name first (app_plugins)
                try:
                    from app_plugins.core_plugins import get_core_plugins  # type: ignore
                    plugins = get_core_plugins()
                    logger.info("App plugins core plugins retrieved: %d plugins", len(plugins))
                    return plugins
                except ImportError:
                    # LEGACY: Support for old 'platforms/' folder name (deprecated, 3.0.0 compatibility)
                    from platforms.core_plugins import get_core_plugins  # type: ignore
                    plugins = get_core_plugins()
                    logger.warning("Using legacy 'platforms/' folder for core plugins (deprecated, 3.0.0 compatibility). Consider migrating to 'app_plugins/'")
                    logger.info("Platforms core plugins retrieved: %d plugins", len(plugins))
                    return plugins
        elif source == "gui":
            from ...plugins.core_plugins import get_core_plugins
            plugins = get_core_plugins()
            logger.info("GUI core plugins retrieved: %d plugins", len(plugins))
            return plugins
        else:
            logger.warning(f"Unknown core plugin source: {source}")
            return []
    except Exception as e:
        logger.info("Failed to load %s core plugins: %s", source, e)
        return []


def _register_core_plugins(plugin_classes: List[Type[Any]]) -> List[Type[Any]]:
    """Register a list of core plugin classes.
    
    Args:
        plugin_classes: List of plugin classes to register
        
    Returns:
        List of successfully registered plugin classes
    """
    registered: List[Type[Any]] = []
    for plugin_class in plugin_classes:
        try:
            plugin_registry.register_plugin(plugin_class, is_core=True)
            registered.append(plugin_class)
            logger.info("Registered core plugin: %s", getattr(plugin_class, "tab_name", plugin_class.__name__))
        except Exception as e:
            logger.error("Failed to register core plugin %s: %s", plugin_class.__name__, e)
    return registered


def discover_and_register_all_plugins() -> Tuple[List[Type[Any]], Dict[str, Any]]:
    """Discover and register core and external plugins.

    Returns (registered_core_plugins, summary) where summary may contain counts/metadata.
    """
    registered_core: List[Type[Any]] = []
    summary: Dict[str, Any] = {"total_discovered": 0}

    try:
        # Register core plugins from both sources
        logger.info("Attempting to load core plugins...")
        platforms_plugins = _load_core_plugins_from_source("platforms")
        gui_plugins = _load_core_plugins_from_source("gui")
        
        all_core_plugins = platforms_plugins + gui_plugins
        logger.info("Total core plugins to register: %d plugins", len(all_core_plugins))
        registered_core = _register_core_plugins(all_core_plugins)

        # Discover plugins from both external and built-in locations
        try:
            from ...plugins.discovery import discover_and_register_plugins as discover
            from ..utils.paths import get_plugins_dir

            # Discover external plugins (in parent project's plugins directory)
            external_plugins_dir = str(get_plugins_dir())
            external_results, external_summary = discover(external_plugins_dir)
            if isinstance(external_summary, dict):
                summary.update(external_summary)
            logger.info("External plugin discovery complete: %s plugins found", external_summary.get("total_discovered", 0))

            # Discover built-in plugins (in GUI/plugins directory)
            gui_plugins_dir = str(Path(__file__).parent.parent.parent / "plugins")
            builtin_results, builtin_summary = discover(gui_plugins_dir)
            if isinstance(builtin_summary, dict):
                # Merge the summaries
                summary["total_discovered"] = summary.get("total_discovered", 0) + builtin_summary.get("total_discovered", 0)
                if "local_plugins" in summary and "local_plugins" in builtin_summary:
                    summary["local_plugins"] = summary["local_plugins"] + builtin_summary["local_plugins"]
                else:
                    summary["builtin_plugins"] = builtin_summary.get("local_plugins", 0)
            logger.info("Built-in plugin discovery complete: %s plugins found", builtin_summary.get("total_discovered", 0))
        except Exception as e:  # pragma: no cover - optional discovery
            logger.warning("Plugin discovery failed: %s", e)
    except Exception as e:
        logger.error("Error during plugin discovery: %s", e)
        raise

    return registered_core, summary


__all__ = ['discover_and_register_all_plugins']
