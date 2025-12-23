# Testing Strategy

This document outlines the strategy for implementing tests in the GUI submodule.

## 1. Testing Frameworks
*   **pytest**: The primary runner. It is more flexible and requires less boilerplate than `unittest`.
*   **pytest-qt**: Essential for testing PySide6 widgets. It provides a `qtbot` fixture to simulate user interaction (clicks, keypresses) and manages the Qt event loop.
*   **pytest-mock**: For easily mocking dependencies (wrapping `unittest.mock`).

## 2. Test Pyramid Layers

### A. Unit Tests (Logic Only)
**Target:** Services, Utils, and non-GUI logic.
*   **Goal:** Verify individual logic units in isolation.
*   **Challenges in Current Architecture:**
    *   **Global State:** Tests using `plugin_registry` must manually clear it in a `teardown` or fixture to avoid polluting subsequent tests.
    *   **File I/O:** `SettingsService` and `ThemeManager` read/write real files. Use `tmp_path` fixture or mock `builtins.open` to avoid writing to the actual config directory.

### B. Integration Tests (Wiring)
**Target:** `ServiceContainer`, Plugin Discovery.
*   **Goal:** Ensure components talk to each other correctly.
*   **Focus:**
    *   Verify `ServiceContainer` correctly resolves dependency chains (e.g., `AdminService` gets the `DaemonService`).
    *   Verify `PluginService` can correctly parse a dummy directory of plugins (using a temporary folder).

### C. GUI Tests (Component Level)
**Target:** Custom Widgets, Dialogs, Controllers.
*   **Tool:** `pytest-qt`
*   **Goal:** Verify a widget behaves correctly when interacted with.
*   **Example Strategy:**
    1.  Initialize `MainWindow`.
    2.  Use `qtbot.mouseClick` on a menu item.
    3.  Assert that `plugin_registry` state changed or a Dialog appeared.
*   **Current Architecture Workaround:** Since we inject dependencies manually in `MainWindow`, we must construct a "Test Container" with Mock objects (e.g., a `MockAdminService` that returns `True`) and pass that container to `MainWindow`.

## 3. Handling Architectural Barriers (Current State)

Until the identified architectural anomalies are refactored, tests must employ specific workarounds:

| Barrier | Workaround |
| :--- | :--- |
| **Global `plugin_registry`** | Use a customized `autouse=True` fixture that calls `plugin_registry.clear()` before *and* after every test. |
| **`ThemeManager` Coupling** | Tests initializing `MainWindow` must manually create a `ThemeManager` instance (potentially with a temporary themes directory) and pass it in. |
| **Threaded Loading (`TabLoader`)** | `pytest-qt` handles threads well, but for unit tests, you may need to mock `TabLoaderThread` to execute synchronously or bypass the thread entirely by manually populating the registry. |

## 4. Directory Structure Recommendation

```
GUI/
  tests/
    conftest.py          # Shared fixtures (qtbot, mock_container, clean_registry)
    unit/
      test_services.py
      test_utils.py
    integration/
      test_discovery.py
      test_container.py
    ui/
      test_main_window.py
      test_plugin_dialog.py
```
