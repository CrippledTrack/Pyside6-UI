"""
Service container for dependency injection.

This module provides a ServiceContainer class that manages service lifecycle
and dependency injection, replacing global singleton patterns.
"""

from __future__ import annotations

import logging
from typing import Dict, Type, TypeVar, Optional, Any, Callable

from .settings_service import SettingsService
from .daemon_service import DaemonService
from .admin_service import AdminService
from .plugin_service import PluginService
from .plugin_registry_facade import PluginRegistryFacade
from .notification_service import NotificationService
from .dev_mode_service import DevModeService
from ...plugin_system.registry import PluginRegistry
from ...plugin_system.interfaces import IServiceContainer, ISettingsService
from .interfaces import IAdminService, IDaemonService, INotificationService, ISettingsService as IAppSettingsService

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceContainer:
    """Service container for dependency injection and service management."""
    
    def __init__(self) -> None:
        """Initialize the service container."""
        self._services: Dict[Type[Any], Any] = {}
        self._factories: Dict[Type[Any], Callable[[], Any]] = {}
        self._initialized = False
    
    def register_singleton(self, service_type: Type[T], instance: T) -> None:
        """Register a singleton service instance.
        
        Args:
            service_type: Type of the service
            instance: Service instance
        """
        self._services[service_type] = instance
        logger.debug(f"Registered singleton: {service_type.__name__}")
    
    def register_factory(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        """Register a factory function for creating service instances.
        
        Args:
            service_type: Type of the service
            factory: Factory function that creates the service instance
        """
        self._factories[service_type] = factory
        logger.debug(f"Registered factory: {service_type.__name__}")
    
    def get(self, service_type: Type[T]) -> T:
        """Get a service instance by type.
        
        Args:
            service_type: Type of the service to get
            
        Returns:
            Service instance
            
        Raises:
            ValueError: If service is not registered
        """
        # Check if already registered as singleton
        if service_type in self._services:
            return self._services[service_type]
        
        # Check if factory is registered
        if service_type in self._factories:
            instance = self._factories[service_type]()
            # Cache as singleton for future use
            self._services[service_type] = instance
            logger.debug(f"Created and cached service: {service_type.__name__}")
            return instance
        
        raise ValueError(f"Service {service_type.__name__} is not registered")
    
    def initialize_services(self) -> None:
        """Initialize all services with their dependencies.
        
        This method sets up service dependencies in the correct order.
        Note: ThemeManager is NOT initialized here because it requires QApplication
        to exist first. Register it manually after QApplication is created.
        """
        if self._initialized:
            return
        
        logger.info("Initializing services...")
        
        # Register container itself under the IServiceContainer interface
        self.register_singleton(IServiceContainer, self)
        
        # Services are imported at the top level
        
        # 0. Dev mode service (no dependencies, needed before settings)
        if DevModeService not in self._services:
            dev_mode_service = DevModeService()
            self.register_singleton(DevModeService, dev_mode_service)
            # Wire into admin.py backward-compat shim
            try:
                from ..utils.admin import set_dev_mode_service
                set_dev_mode_service(dev_mode_service)
            except Exception as e:
                logger.debug(f"Failed to wire DevModeService into admin shim: {e}")

        # 1. Settings service (no dependencies)
        if SettingsService not in self._services:
            settings_service = SettingsService()
            # DEPRECATED: Concrete registration for backward compatibility, will be removed in v6.0.0
            self.register_singleton(SettingsService, settings_service)
            self.register_singleton(ISettingsService, settings_service)
            self.register_singleton(IAppSettingsService, settings_service)
            try:
                dev_svc = self.get(DevModeService)
                dev_svc.configure_settings_service(settings_service)
            except Exception as e:
                logger.debug(f"Failed to configure dev mode settings: {e}")
        
        # 2. Daemon service (no dependencies)
        if DaemonService not in self._services:
            daemon_service = DaemonService()
            # DEPRECATED: Concrete registration for backward compatibility, will be removed in v6.0.0
            self.register_singleton(DaemonService, daemon_service)
            self.register_singleton(IDaemonService, daemon_service)
        
        # 3. Admin service (depends on daemon service)
        if AdminService not in self._services:
            daemon_service = self.get(DaemonService)
            admin_service = AdminService(daemon_service)
            # DEPRECATED: Concrete registration for backward compatibility, will be removed in v6.0.0
            self.register_singleton(AdminService, admin_service)
            self.register_singleton(IAdminService, admin_service)
        
        # 4. Plugin registry (no dependencies initially, container set below)
        if PluginRegistry not in self._services:
            registry = PluginRegistry()
            self.register_singleton(PluginRegistry, registry)

        # 4a. Plugin service (depends on settings service + registry)
        if PluginService not in self._services:
            settings_service = self.get(SettingsService)
            registry = self.get(PluginRegistry)
            plugin_service = PluginService(
                settings_service=settings_service,
                registry=registry,
            )
            self.register_singleton(PluginService, plugin_service)

        # 4b. Plugin registry facade (depends on registry + container)
        if PluginRegistryFacade not in self._services:
            registry = self.get(PluginRegistry)
            registry_facade = PluginRegistryFacade(self, registry=registry)
            self.register_singleton(PluginRegistryFacade, registry_facade)

        # 5. Notification service (no dependencies)
        if NotificationService not in self._services:
            notification_service = NotificationService()
            # DEPRECATED: Concrete registration for backward compatibility, will be removed in v6.0.0
            self.register_singleton(NotificationService, notification_service)
            self.register_singleton(INotificationService, notification_service)
        
        self._initialized = True
        logger.info("Services initialized successfully")
    
    def reset(self) -> None:
        """Reset the container (mainly for testing)."""
        self._services.clear()
        self._factories.clear()
        self._initialized = False
        logger.debug("Service container reset")


# Global container instance (for backward compatibility during migration)
_global_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """Get the global service container instance.
    
    Returns:
        Service container instance
    """
    global _global_container
    if _global_container is None:
        _global_container = ServiceContainer()
        _global_container.initialize_services()
    return _global_container


def set_container(container: ServiceContainer) -> None:
    """Set the global service container instance.
    
    Call this from the application bootstrap (app.py) after creating
    the primary ServiceContainer so that get_container() returns the
    same instance instead of creating a second one.
    
    Args:
        container: The service container to register globally
    """
    global _global_container
    _global_container = container


def reset_container() -> None:
    """Reset the global container (mainly for testing)."""
    global _global_container
    _global_container = None


__all__ = [
    'ServiceContainer',
    'get_container',
    'set_container',
    'reset_container',
]

