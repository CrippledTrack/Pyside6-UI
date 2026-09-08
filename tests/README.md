"""How to run GUI headless smoke tests

From the repository root (parent of ``GUI/``)::

```bash
python -m pytest GUI/tests -q
```

Or from inside the GUI submodule::

```bash
python -m pytest tests -q
```

These tests cover ServiceContainer DI (interface keys, no raw PluginRegistry),
services Qt-import hygiene, daemon protocol serialize/parse, LocalDaemonClient
``run_command`` / streaming drain and timeouts, plugin lifecycle (single-flight
construction, failed activation, post-unload events, identity, dependencies),
settings merge and future-schema handling, HostConfig paths, tab labels vs plugin_id, PyInstaller
hidden imports for dynamic UI maps, and the current synchronous dialog
contracts. Theme JSON export stores stylesheets as line arrays and still loads
older string-form files. They do not start pkexec/sudo or require a display.

CI runs ``python -m pytest GUI/tests -q`` from `.github/workflows/test-gui.yml`.

"""
