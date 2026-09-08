"""How to run GUI headless smoke tests

From the CyberPatriot repo root (parent of ``GUI/``)::

```bash
python -m pytest GUI/tests -q
```

Or from inside the GUI submodule::

```bash
python -m pytest tests -q
```

These tests cover ServiceContainer DI (interface keys, no raw PluginRegistry),
services Qt-import hygiene, daemon protocol serialize/parse, LocalDaemonClient
``run_command`` / streaming drain and timeouts, plugin registry lock ownership,
tab-vs-plugin teardown, plugin enable persistence, Tab-extension filtering,
and PyInstaller hidden imports for dynamic UI maps. They do not start
pkexec/sudo or require a display.
"""
