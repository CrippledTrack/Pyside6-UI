"""
Plugin discovery system for Basic GUI Application.

Supports both entry points (for installed plugins) and local plugins folder.
"""
from __future__ import annotations

import os
import sys
import inspect
import importlib
import importlib.util
import logging
from pathlib import Path
from typing import List, Dict, Type, Optional, Tuple, Any
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
        
        # Add plugins directory to Python path if not already there
        plugins_dir_str = str(plugins_path.absolute())
        if plugins_dir_str not in sys.path:
            sys.path.insert(0, plugins_dir_str)
        
        # For external plugins, we need to add the parent directory (project root) to the path
        # so plugins can import from GUI.plugins and other project modules
        # But only do this if we're not already in the GUI/plugins directory
        if not plugins_dir_str.endswith('GUI/plugins') and not plugins_dir_str.endswith('GUI\\plugins'):
            project_root = str(plugins_path.parent.absolute())
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
        
        try:
            # Find all Python files in the plugins directory
            python_files = list(plugins_path.glob("*.py"))
            
            # Files to skip (system files, not plugins)
            skip_files = {
                '__init__.py',
                'base.py',
                'discovery.py',
                'core_plugins.py',
                'plugin_management.py',
                'registry.py'
            }
            
            for py_file in python_files:
                # Skip system files and files starting with underscore
                if py_file.name.startswith('_') or py_file.name in skip_files:
                    logger.debug(f"Skipping system file: {py_file.name}")
                    continue
                
                try:
                    module_name = py_file.stem
                    logger.debug(f"Attempting to load local plugin module: {module_name}")
                    
                    # Load the module
                    spec = importlib.util.spec_from_file_location(module_name, py_file)
                    if spec is None or spec.loader is None:
                        logger.warning(f"Could not create spec for {py_file}")
                        continue
                    
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Find all BaseTabPlugin subclasses in the module
                    plugin_classes = self._find_plugin_classes_in_module(module)
                    
                    for plugin_class in plugin_classes:
                        plugin_name = plugin_class.tab_name
                        plugins.append((plugin_name, plugin_class, f"local:{py_file.name}"))
                        logger.info(f"Successfully loaded local plugin: {plugin_name} from {py_file.name}")
                        
                except Exception as e:
                    logger.error(f"Failed to load local plugin from {py_file}: {e}")
        
        finally:
            # Remove directories from Python path
            if plugins_dir_str in sys.path:
                sys.path.remove(plugins_dir_str)
            # Only remove project_root if we added it
            if not plugins_dir_str.endswith('GUI/plugins') and not plugins_dir_str.endswith('GUI\\plugins'):
                project_root = str(plugins_path.parent.absolute())
                if project_root in sys.path:
                    sys.path.remove(project_root)
        
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
            
            # Must have a valid tab_name
            if not hasattr(cls, 'tab_name') or not cls.tab_name or cls.tab_name == "Unnamed Tab":
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