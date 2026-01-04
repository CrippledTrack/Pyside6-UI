"""
Plugin discovery system for Basic GUI Application.

Supports both entry points (for installed plugins) and local plugins folder.
"""
from __future__ import annotations

import inspect
import importlib
import importlib.util
import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

from .base import BaseTabPlugin, plugin_registry

# Try to import entry_points (Python 3.8+)
try:
    from importlib.metadata import entry_points
    HAS_ENTRY_POINTS = True
except ImportError:
    try:
        # importlib_metadata is a backport for older Python versions
        from importlib_metadata import entry_points  # type: ignore
        HAS_ENTRY_POINTS = True
    except ImportError:
        HAS_ENTRY_POINTS = False
        entry_points = None

logger = logging.getLogger(__name__)

# Entry point group name for tab plugins
ENTRY_POINT_GROUP = "gui_app_tabs"

# Default plugins directory relative to the main script
DEFAULT_PLUGINS_DIR = "plugins"

class PluginDiscovery:
    """Plugin discovery and loading system."""
    
    def __init__(self, plugins_dir: Optional[str] = None):
        """
        Initialize the plugin discovery system.
        
        Args:
            plugins_dir: Path to the plugins directory (defaults to "plugins")
        """
        self.plugins_dir = plugins_dir or DEFAULT_PLUGINS_DIR
        self.discovered_plugins: List[Tuple[str, Type[BaseTabPlugin], str]] = []  # (name, class, source)
        
    def discover_all_plugins(self) -> List[Tuple[str, Type[BaseTabPlugin], str]]:
        """
        Discover all plugins from both entry points and local directory.
        
        Returns:
            List of tuples containing (plugin_name, plugin_class, source)
        """
        self.discovered_plugins.clear()
        
        # Discover entry point plugins
        if HAS_ENTRY_POINTS:
            entry_point_plugins = self.discover_entry_point_plugins()
            self.discovered_plugins.extend(entry_point_plugins)
            logger.info(f"Discovered {len(entry_point_plugins)} entry point plugins")
        else:
            logger.warning("Entry points not available, skipping entry point plugin discovery")
        
        # Discover local plugins
        local_plugins = self.discover_local_plugins()
        self.discovered_plugins.extend(local_plugins)
        logger.info(f"Discovered {len(local_plugins)} local plugins")
        
        logger.info(f"Total plugins discovered: {len(self.discovered_plugins)}")
        return self.discovered_plugins.copy()
    
    def discover_entry_point_plugins(self) -> List[Tuple[str, Type[BaseTabPlugin], str]]:
        """
        Discover plugins via entry points.
        
        Returns:
            List of tuples containing (plugin_name, plugin_class, "entry_point")
        """
        if not HAS_ENTRY_POINTS:
            return []
        
        plugins = []
        
        try:
            # Get all entry points for our group
            eps = entry_points(group=ENTRY_POINT_GROUP)
            
            for ep in eps:
                try:
                    logger.debug(f"Loading entry point plugin: {ep.name}")
                    plugin_class = ep.load()
                    
                    # Validate that it's a BaseTabPlugin subclass
                    if not self._is_valid_plugin_class(plugin_class):
                        logger.warning(f"Entry point {ep.name} does not provide a valid BaseTabPlugin subclass")
                        continue
                    
                    plugins.append((ep.name, plugin_class, "entry_point"))
                    logger.info(f"Successfully loaded entry point plugin: {ep.name}")
                    
                except Exception as e:
                    logger.error(f"Failed to load entry point plugin {ep.name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error discovering entry point plugins: {e}")
        
        return plugins
    
    def discover_local_plugins(self) -> List[Tuple[str, Type[BaseTabPlugin], str]]:
        """
        Discover plugins in the local plugins directory.
        
        Returns:
            List of tuples containing (plugin_name, plugin_class, "local")
        """
        plugins = []
        plugins_path = Path(self.plugins_dir)
        
        if not plugins_path.exists():
            logger.info(f"Plugins directory does not exist: {plugins_path}")
            return plugins
        
        if not plugins_path.is_dir():
            logger.warning(f"Plugins path is not a directory: {plugins_path}")
            return plugins
        
        with self._plugin_path_context(plugins_path):
            plugins = self._load_plugins_from_directory(plugins_path)
        
        return plugins

    @contextmanager
    def _plugin_path_context(self, plugins_path: Path):
        """Context manager for temporarily adding plugin paths to sys.path."""
        plugins_dir_str = str(plugins_path.absolute())
        is_gui_plugins_dir = self._is_gui_plugins_directory(plugins_path)
        
        # Add plugins directory to path
        plugins_in_path = plugins_dir_str in sys.path
        if not plugins_in_path:
            sys.path.insert(0, plugins_dir_str)
        
        # For external plugins, add project root to path
        project_root_in_path = False
        project_root_path = None
        if not is_gui_plugins_dir:
            project_root_path = plugins_path.parent
            project_root_str = str(project_root_path.absolute())
            project_root_in_path = project_root_str in sys.path
            if not project_root_in_path:
                sys.path.insert(0, project_root_str)
        
        try:
            yield
        finally:
            # Clean up paths
            if not plugins_in_path and plugins_dir_str in sys.path:
                sys.path.remove(plugins_dir_str)
            if project_root_path and not project_root_in_path:
                project_root_str = str(project_root_path.absolute())
                if project_root_str in sys.path:
                    sys.path.remove(project_root_str)

    def _is_gui_plugins_directory(self, plugins_path: Path) -> bool:
        """Check if the plugins path is the GUI/plugins directory."""
        # Normalize path separators for comparison
        path_str = str(plugins_path.absolute())
        gui_plugins_patterns = ['GUI/plugins', 'GUI\\plugins']
        return any(path_str.endswith(pattern) for pattern in gui_plugins_patterns)

    def _load_plugins_from_directory(self, plugins_path: Path) -> List[Tuple[str, Type[BaseTabPlugin], str]]:
        """Load all plugin files from a directory."""
        plugins = []
        python_files = list(plugins_path.glob("*.py"))
        skip_files = {
            '__init__.py',
            'base.py',
            'discovery.py',
            'core_plugins.py',
            'plugin_management.py',
            'registry.py'
        }
        
        for py_file in python_files:
            if py_file.name.startswith('_') or py_file.name in skip_files:
                logger.debug(f"Skipping system file: {py_file.name}")
                continue
            
            try:
                loaded_plugins = self._load_plugin_from_file(py_file)
                plugins.extend(loaded_plugins)
            except Exception as e:
                logger.error(f"Failed to load local plugin from {py_file}: {e}")
        
        return plugins

    def _load_plugin_from_file(self, py_file: Path) -> List[Tuple[str, Type[BaseTabPlugin], str]]:
        """Load plugin classes from a single Python file."""
        plugins = []
        module_name = py_file.stem
        logger.debug(f"Attempting to load local plugin module: {module_name}")
        
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            logger.warning(f"Could not create spec for {py_file}")
            return plugins
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        plugin_classes = self._find_plugin_classes_in_module(module)
        for plugin_class in plugin_classes:
            # v4.0.0: Prefer plugin_name, fall back to tab_name
            plugin_name = getattr(plugin_class, 'plugin_name', None)
            if not plugin_name or plugin_name == "Unnamed Plugin":
                plugin_name = getattr(plugin_class, 'tab_name', "Unknown Plugin")
                
            plugins.append((plugin_name, plugin_class, f"local:{py_file.name}"))
            logger.info(f"Successfully loaded local plugin: {plugin_name} from {py_file.name}")
        
        return plugins
    
    def _find_plugin_classes_in_module(self, module) -> List[Type[BaseTabPlugin]]:
        """
        Find all BaseTabPlugin subclasses in a module.
        
        Args:
            module: The imported module
            
        Returns:
            List of plugin classes found in the module
        """
        plugin_classes = []
        
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if self._is_valid_plugin_class(obj) and obj.__module__ == module.__name__:
                plugin_classes.append(obj)
        
        return plugin_classes
    
    def _is_valid_plugin_class(self, cls) -> bool:
        """
        Check if a class is a valid plugin class.
        
        Args:
            cls: The class to check
            
        Returns:
            bool: True if it's a valid plugin class
        """
        try:
            # Must be a class
            if not inspect.isclass(cls):
                return False
            
            # Must be a subclass of BaseTabPlugin
            if not issubclass(cls, BaseTabPlugin):
                return False
            
            # Must not be BaseTabPlugin itself
            if cls is BaseTabPlugin:
                return False
            
            # Must implement the create_widget method
            if not hasattr(cls, 'create_widget') or not callable(cls.create_widget):
                return False
            
            # Check for valid name (plugin_name OR tab_name)
            # v4.0.0: plugin_name is preferred
            has_plugin_name = hasattr(cls, 'plugin_name') and cls.plugin_name and cls.plugin_name != "Unnamed Plugin"
            has_tab_name = hasattr(cls, 'tab_name') and cls.tab_name and cls.tab_name != "Unnamed Tab"
            
            if not has_plugin_name and not has_tab_name:
                return False
            
            return True
            
        except Exception:
            return False
    
    def register_discovered_plugins(self, 
                                  discovered_plugins: Optional[List[Tuple[str, Type[BaseTabPlugin], str]]] = None,
                                  skip_validation: bool = False) -> Dict[str, str]:
        """
        Register discovered plugins in the global registry.
        
        Args:
            discovered_plugins: List of plugins to register (uses self.discovered_plugins if None)
            skip_validation: Skip plugin validation during registration
            
        Returns:
            Dict mapping plugin names to their registration status
        """
        if discovered_plugins is None:
            discovered_plugins = self.discovered_plugins
        
        registration_results = {}
        
        for plugin_name, plugin_class, source in discovered_plugins:
            try:
                # Determine if it's a core plugin (part of the main application)
                # Use explicit attribute only
                is_core = bool(getattr(plugin_class, 'is_core_plugin', False))
                
                # Register the plugin
                plugin_registry.register_plugin(plugin_class, is_core=is_core)
                
                registration_results[plugin_name] = f"success ({source})"
                logger.info(f"Registered plugin: {plugin_name} from {source}")
                
            except Exception as e:
                registration_results[plugin_name] = f"failed: {e}"
                logger.error(f"Failed to register plugin {plugin_name}: {e}")
        
        return registration_results
    
    def get_plugin_info_summary(self) -> Dict[str, any]:
        """
        Get a summary of all discovered plugins.
        
        Returns:
            Dictionary with plugin discovery summary
        """
        total_plugins = len(self.discovered_plugins)
        entry_point_count = len([p for p in self.discovered_plugins if p[2] == "entry_point"])
        local_count = len([p for p in self.discovered_plugins if p[2].startswith("local:")])
        
        return {
            'total_discovered': total_plugins,
            'entry_point_plugins': entry_point_count,
            'local_plugins': local_count,
            'plugins': [
                {
                    'name': name,
                    'source': source,
                    'class': cls.__name__,
                    'module': cls.__module__
                }
                for name, cls, source in self.discovered_plugins
            ]
        }


def discover_and_register_plugins(plugins_dir: Optional[str] = None) -> Tuple[Dict[str, str], Dict[str, any]]:
    """
    Convenience function to discover and register all plugins.
    
    Args:
        plugins_dir: Path to the plugins directory
        
    Returns:
        Tuple of (registration_results, discovery_summary)
    """
    discovery = PluginDiscovery(plugins_dir)
    discovered = discovery.discover_all_plugins()
    registration_results = discovery.register_discovered_plugins(discovered)
    summary = discovery.get_plugin_info_summary()
    
    return registration_results, summary


__all__ = ['PluginDiscovery', 'discover_and_register_plugins'] 