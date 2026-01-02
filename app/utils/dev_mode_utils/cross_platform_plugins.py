"""
Cross-platform plugin loading for dev mode.

This module handles loading plugins from other platforms when in dev mode
with show_all_platforms enabled. It dynamically discovers plugins from
the other platform's directory without hardcoding imports.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import List, Type, Any, Optional

from ...constants import CURRENT_PLATFORM

logger = logging.getLogger(__name__)

# Cache for loaded cross-platform plugins
_cross_platform_plugins: List[Type[Any]] = []
_cache_valid: bool = False


def clear_cross_platform_cache() -> None:
    """Clear the cached cross-platform plugins.
    
    Call this before reloading plugins to ensure fresh imports.
    """
    global _cross_platform_plugins, _cache_valid
    _cross_platform_plugins = []
    _cache_valid = False
    logger.info("Cross-platform plugin cache cleared")


def load_cross_platform_plugins() -> List[Type[Any]]:
    """Load plugins from the other platform for dev mode testing.
    
    On Linux: loads Windows plugins (requires win32 mocks to be installed first)
    On Windows: loads Linux plugins
    
    Dynamically discovers plugins by scanning the other platform's tabs directory.
    
    Returns:
        List of plugin classes from the other platform
    """
    global _cross_platform_plugins, _cache_valid
    
    if _cache_valid:
        return _cross_platform_plugins
    
    plugins: List[Type[Any]] = []
    
    if CURRENT_PLATFORM == "linux":
        # Load Windows plugins
        plugins = _discover_platform_plugins("windows")
    elif CURRENT_PLATFORM == "windows":
        # Load Linux plugins
        plugins = _discover_platform_plugins("linux")
    
    _cross_platform_plugins = plugins
    _cache_valid = True
    
    return plugins


def _find_app_plugins_dir() -> Optional[Path]:
    """Find the app_plugins or platforms directory.
    
    Searches common locations for the external plugins directory.
    Supports both 'app_plugins' (preferred) and 'platforms' (legacy) folder names.
    
    Returns:
        Path to plugins directory, or None if not found
    """
    # Try relative to the GUI package
    gui_path = Path(__file__).parent.parent.parent.parent.parent  # dev_mode_utils -> utils -> app -> GUI -> project root
    
    # Check common locations (app_plugins first, then legacy platforms)
    candidates = [
        gui_path.parent / "app_plugins",  # Sibling to GUI
        gui_path / "app_plugins",  # Inside GUI's parent
        Path.cwd() / "app_plugins",  # Current working directory
        gui_path.parent / "platforms",  # Legacy: sibling to GUI
        gui_path / "platforms",  # Legacy: inside GUI's parent
        Path.cwd() / "platforms",  # Legacy: current working directory
    ]
    
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            logger.debug(f"Found plugins directory at: {candidate}")
            return candidate
    
    logger.warning("Could not find app_plugins or platforms directory")
    return None


def _create_prefixed_plugin(original_class: Type[Any], platform_prefix: str) -> Type[Any]:
    """Create a wrapper plugin class with a prefixed tab_name.
    
    This avoids name conflicts when loading plugins from both platforms.
    
    Args:
        original_class: The original plugin class
        platform_prefix: Prefix to add (e.g., "[Win]" or "[Linux]")
        
    Returns:
        A new class with prefixed tab_name
    """
    original_tab_name = getattr(original_class, 'tab_name', 'Unknown')
    prefixed_name = f"{platform_prefix} {original_tab_name}"
    
    # Create a new class that inherits from the original but with modified tab_name
    new_class = type(
        f"CrossPlatform_{original_class.__name__}",
        (original_class,),
        {
            'tab_name': prefixed_name,
            '_original_tab_name': original_tab_name,
            '_is_cross_platform': True,
        }
    )
    
    return new_class


def _discover_platform_plugins(target_platform: str) -> List[Type[Any]]:
    """Discover and load plugins from a specific platform's directory.
    
    Args:
        target_platform: 'windows' or 'linux'
        
    Returns:
        List of discovered plugin classes (with prefixed tab names)
    """
    plugins: List[Type[Any]] = []
    
    app_plugins_dir = _find_app_plugins_dir()
    if not app_plugins_dir:
        return plugins
    
    # Look for the platform's tabs directory
    tabs_dir = app_plugins_dir / target_platform / "tabs"
    if not tabs_dir.exists():
        logger.warning(f"Tabs directory not found: {tabs_dir}")
        return plugins
    
    logger.info(f"Discovering {target_platform} plugins from: {tabs_dir}")
    
    # Get the BaseTabPlugin class for isinstance checking
    try:
        from GUI.plugin_system.base import BaseTabPlugin
    except ImportError:
        logger.error("Could not import BaseTabPlugin")
        return plugins
    
    # Ensure the app_plugins directory is in sys.path for imports
    app_plugins_parent = str(app_plugins_dir.parent)
    if app_plugins_parent not in sys.path:
        sys.path.insert(0, app_plugins_parent)
    
    # Determine the platform prefix for tab names
    platform_prefix = "[Win]" if target_platform == "windows" else "[Linux]"
    
    # Scan for Python files in the tabs directory
    for py_file in tabs_dir.glob("*_tab.py"):
        if py_file.name.startswith("_"):
            continue
        
        module_name = f"app_plugins.{target_platform}.tabs.{py_file.stem}"
        
        try:
            # Import the module
            module = importlib.import_module(module_name)
            
            # Find plugin classes in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Check if it's a plugin class (inherits from BaseTabPlugin)
                if (obj is not BaseTabPlugin and 
                    issubclass(obj, BaseTabPlugin) and
                    hasattr(obj, 'tab_name')):
                    # Create a prefixed version to avoid name conflicts
                    prefixed_plugin = _create_prefixed_plugin(obj, platform_prefix)
                    plugins.append(prefixed_plugin)
                    logger.debug(f"Discovered {target_platform} plugin: {prefixed_plugin.tab_name}")
                    
        except Exception as e:
            logger.warning(f"Could not load module {module_name}: {e}")
    
    if plugins:
        logger.info(f"Discovered {len(plugins)} {target_platform} plugins for cross-platform testing")
    else:
        logger.warning(f"No {target_platform} plugins could be discovered")
    
    return plugins


__all__ = ['load_cross_platform_plugins', 'clear_cross_platform_cache']

