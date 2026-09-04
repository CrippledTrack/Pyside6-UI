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
``run_command``, and ``run_privileged_command`` with a mock local client. They
do not start pkexec/sudo or require a display.
"""
