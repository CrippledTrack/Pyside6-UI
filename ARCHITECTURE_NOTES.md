# GUI Architecture Anomalies

This document outlines architectural inconsistencies identified in the GUI submodule.

## 1. The `ThemeManager` Outlier
*   **Observation:** `ThemeManager` is manually instantiated in `app.py` and passed explicitly to `MainWindow`, while other services (`SettingsService`, `DaemonService`) use the `ServiceContainer`.
*   **Impact:** breaks the dependency injection pattern. Components needing `ThemeManager` require manual prop-drilling (e.g., passing it through `MainWindow` -> `ToastManager`).
*   **Recommendation:** Register `ThemeManager` in the `ServiceContainer`.

## 2. The `plugin_registry` Bypass
*   **Observation:** The `plugin_registry` is accessed via global import (`from ...plugin_system import plugin_registry`) rather than through the `ServiceContainer`.
*   **Impact:** Harder to test and mock. It acts as a global singleton state outside the container's control.
*   **Recommendation:** Wrap or register `plugin_registry` access within the `ServiceContainer` or a `PluginService`.

## 3. `MainWindow` as a "Manual" Factory
*   **Observation:** `MainWindow` manually instantiates controllers and unpacks services to pass to them.
    ```python
    self.tab_controller = TabController(self.admin_service, ...)
    ```
*   **Impact:** Tight coupling. `MainWindow` has to know exactly what every controller needs.
*   **Recommendation:** Controllers should accept the `ServiceContainer` or have their dependencies injected automatically.

## 4. `TabLoaderThread` Identity Crisis
*   **Observation:** `TabLoaderThread` is a UI class (`QThread`) but handles business logic for plugin discovery and registry manipulation.
*   **Impact:** Violation of Separation of Concerns.
*   **Recommendation:** Move detailed discovery logic into `PluginService`. The thread should only handle the asynchronous execution of `PluginService` methods.
