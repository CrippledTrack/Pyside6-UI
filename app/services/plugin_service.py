"""
Plugin discovery and registration service.

This module provides functionality for discovering plugins from multiple sources
(core plugins from platforms/core_plugins.py and GUI/plugins/core_plugins.py,
entry point plugins, and local plugin files) and registering them with the
plugin registry.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Type

from ...plugins import plugin_registry

logger = logging.getLogger(__name__)


def discover_and_register_all_plugins() -> Tuple[List[Type[Any]], Dict[str, Any]]:
    """Discover and register core and external plugins.

    Returns (registered_core_plugins, summary) where summary may contain counts/metadata.
    """
    registered_core: List[Type[Any]] = []
    summary: Dict[str, Any] = {"total_discovered": 0}

    try:
        # Register core plugins from both sources
        logger.info("Attempting to load core plugins...")
        
        # Try to load from platforms/core_plugins.py first
        platforms_core_plugins = []
        try:
            # Add parent directory to sys.path temporarily for platforms import
            parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            
            from platforms.core_plugins import get_core_plugins as get_platforms_core_plugins
            platforms_core_plugins = get_platforms_core_plugins()
            logger.info("Platforms core plugins retrieved: %d plugins", len(platforms_core_plugins))
            
            # Remove parent directory from sys.path
            if parent_dir in sys.path:
                sys.path.remove(parent_dir)
        except Exception as e:
            logger.info("Failed to load platforms core plugins: %s", e)
        
        # Try to load from GUI/plugins/core_plugins.py
        gui_core_plugins = []
        try:
            from ...plugins.core_plugins import get_core_plugins as get_gui_core_plugins
            gui_core_plugins = get_gui_core_plugins()
            logger.info("GUI core plugins retrieved: %d plugins", len(gui_core_plugins))
        except Exception as e:
            logger.info("Failed to load GUI core plugins: %s", e)
        
        # Combine and register all core plugins
        all_core_plugins = platforms_core_plugins + gui_core_plugins
        logger.info("Total core plugins to register: %d plugins", len(all_core_plugins))
        
        for plugin_class in all_core_plugins:
            try:
                plugin_registry.register_plugin(plugin_class, is_core=True)
                registered_core.append(plugin_class)
                logger.info("Registered core plugin: %s", getattr(plugin_class, "tab_name", plugin_class.__name__))
            except Exception as e:  # pragma: no cover - logging branch
                logger.error("Failed to register core plugin %s: %s", plugin_class.__name__, e)

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
