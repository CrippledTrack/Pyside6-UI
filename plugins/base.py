"""
Base plugin interface for Basic GUI Application tabs.

All tab plugins must inherit from BaseTabPlugin.
"""
import platform
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Type
from PySide6.QtWidgets import QWidget

class BaseTabPlugin(ABC):
    """
    Base class for all tab plugins in the Basic GUI Application.
    
    All tab plugins must inherit from this class and implement the required methods.
    """
    
    # Required class attributes
    tab_name: str = "Unnamed Tab"
    tab_description: str = "No description provided"
    supported_platforms: List[str] = ["Windows", "Linux"]  # Platforms this plugin supports
    requires_admin: bool = False  # Whether this plugin requires admin privileges
    plugin_version: str = "1.0.0"
    plugin_author: str = "Unknown"
    plugin_authors: List[str] = []  # Optional list of authors; if provided, overrides plugin_author
    # If True, the plugin will be disabled by default on first discovery (can be enabled by user)
    disabled_by_default: bool = False
    
    # Version requirements (optional)
    # Simple minimum version (e.g., "3.0.0")
    min_gui_version: Optional[str] = None
    # Advanced range specification (e.g., ">=3.0.0,<4.0.0")
    # Takes precedence over min_gui_version if both are specified
    required_gui_version: Optional[str] = None
    
    @classmethod
    @abstractmethod
    def create_widget(cls, parent: Optional[QWidget] = None) -> QWidget:
        """
        Create and return the QWidget to be used as the tab's content.
        
        Args:
            parent: The parent widget (usually the QTabWidget)
            
        Returns:
            QWidget: The widget to be displayed in the tab
        """
        pass
    
    @classmethod
    def is_supported_platform(cls, platform_name: str) -> bool:
        """
        Check if this plugin supports the given platform.
        
        Args:
            platform_name: Name of the platform (e.g., "Windows", "Linux")
            
        Returns:
            bool: True if the platform is supported, False otherwise
        """
        return platform_name.capitalize() in cls.supported_platforms
    
    @classmethod
    def get_current_platform(cls) -> str:
        """Get the current platform name."""
        return platform.system()
    
    @classmethod
    def is_compatible(cls) -> bool:
        """
        Check if this plugin is compatible with the current platform.
        
        Returns:
            bool: True if compatible, False otherwise
        """
        return cls.is_supported_platform(cls.get_current_platform())
    
    @classmethod
    def get_plugin_info(cls) -> Dict[str, Any]:
        """
        Get comprehensive information about this plugin.
        
        Returns:
            dict: Plugin information including name, description, version, etc.
        """
        # Normalize authors: prefer plugin_authors if set; otherwise fallback to plugin_author
        authors_list: List[str] = []
        try:
            if isinstance(getattr(cls, 'plugin_authors', []), list) and getattr(cls, 'plugin_authors'):
                authors_list = [str(a) for a in getattr(cls, 'plugin_authors') if a]
        except Exception:
            authors_list = []
        if not authors_list and getattr(cls, 'plugin_author', None):
            authors_list = [str(getattr(cls, 'plugin_author'))]

        author_text = ", ".join(authors_list) if authors_list else str(getattr(cls, 'plugin_author', 'Unknown'))

        return {
            'name': cls.tab_name,
            'description': cls.tab_description,
            'supported_platforms': cls.supported_platforms,
            'requires_admin': cls.requires_admin,
            'version': cls.plugin_version,
            'author': author_text,           # Backward-compatible single string for display
            'authors': authors_list,         # New field for multi-author support
            'compatible': cls.is_compatible(),
            'current_platform': cls.get_current_platform(),
            'min_gui_version': getattr(cls, 'min_gui_version', None),
            'required_gui_version': getattr(cls, 'required_gui_version', None)
        }
    
    @classmethod
    def validate_plugin(cls) -> List[str]:
        """
        Validate the plugin configuration and return any error messages.
        
        Returns:
            List[str]: List of validation error messages (empty if valid)
        """
        errors = []
        
        if not cls.tab_name or cls.tab_name == "Unnamed Tab":
            errors.append("Plugin must define a valid tab_name")
        
        if not cls.supported_platforms:
            errors.append("Plugin must define supported_platforms")
        
        if not cls.plugin_version:
            errors.append("Plugin must define plugin_version")
        
        # Validate version requirements format (basic check)
        if hasattr(cls, 'min_gui_version') and cls.min_gui_version:
            import re
            if not re.match(r'^\d+\.\d+(?:\.\d+)?', str(cls.min_gui_version)):
                errors.append(f"Invalid min_gui_version format: {cls.min_gui_version}")
        
        if hasattr(cls, 'required_gui_version') and cls.required_gui_version:
            # Basic format check for range specifications
            # Should contain operators like >=, <, etc. and version numbers
            req_str = str(cls.required_gui_version)
            if not re.search(r'[><=]+', req_str):
                errors.append(f"Invalid required_gui_version format (must include operators): {cls.required_gui_version}")
        
        return errors


class CoreTabPlugin(BaseTabPlugin):
    """
    Base class for core (built-in) tab plugins.
    
    These are the original tabs that come with the application.
    Note: This doesn't inherit from QWidget to avoid metaclass conflicts.
    """
    
    plugin_author: str = "Basic GUI Application Team"
    is_core_plugin: bool = True


from .registry import PluginRegistry, plugin_registry  # re-export