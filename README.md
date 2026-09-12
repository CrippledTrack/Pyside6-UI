# Basic UI Application (Pyside6-UI)

Reusable Qt application framework with toolkit-neutral plugin contracts. This package is the `GUI/` git submodule ([Pyside6-UI](https://github.com/CrippledTrack/Pyside6-UI)).


Host apps may supply branding and plugins via an optional `app_plugins/` or `platforms/` tree next to `GUI/`. Those directories are **host integration**, not part of this framework.

For architecture, plugins, and generated API reference, use the [MkDocs site](#documentation) under `docs/`. This README is run/build only.

---

## How to run

**1. From the project root (with a `main.py` next to `GUI/`)**

- Windows (PowerShell): `py main.py`
- Linux/macOS: `python3 main.py`

Run from the directory that contains `main.py` and `GUI/`.

**2. As a module (no `main.py` required)**

```bash
python3 -m GUI    # Windows: py -m GUI
```

**3. Standalone (only the `GUI/` folder)**

```bash
cd GUI
python3 run.py    # Windows: py run.py
```

`run.py` adds the parent of `GUI/` to the path so the package imports. Optional: `run.py --dev` (enables runtime dev mode, which loads sample plugins under `GUI/plugins/`). On Linux, only the explicit `run.py --skip-qt-deps` flag skips the Qt xcb system-package check/install (`--dev` alone never bypasses it; you may chain both, e.g. `run.py --dev --skip-qt-deps`).

### Minimal `main.py` (option 1)

```
your-project/
  main.py
  GUI/
```

```python
import sys
from GUI.app.app import run

if __name__ == "__main__":
    raise SystemExit(run(sys.argv))
```

## Virtual environment and PySide6

- Windows (PowerShell):

  ```bash
  py -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  pip install PySide6
  ```

- Linux/macOS:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install --upgrade pip
  pip install PySide6
  ```

## Build a standalone binary (PyInstaller)

```bash
cd GUI && python3 scripts/build.py
# or from the parent project:
python3 GUI/scripts/build.py
```

Uses `run.py` as the entry. Options: `python3 scripts/build.py --help`.

## Host plugin directories

When the **parent** of `GUI/` contains an `app_plugins` or `platforms` tree that looks like this framework’s plugin layout (`constants.py`, `core_plugins.py`, and/or `linux/` / `windows/`), the app loads constants and plugins from there. That supports test-bed or product hosts without forking the submodule.

If the parent has an unrelated folder with those names, do not run standalone from that location.

Sample plugins in `GUI/plugins/` are framework examples (loaded when runtime `is_dev_mode()` is on and the build is not frozen; force off with `GUI_LOAD_SAMPLE_PLUGINS=0`).

## Troubleshooting

`ModuleNotFoundError: No module named 'GUI'`:

- With `main.py` or `python -m GUI`: run from the directory that contains `GUI/`.
- Standalone: run `python run.py` from inside `GUI/`.

## Classic vs modern Qt UI

Themes live under `app/ui/qt/themes/` (not a top-level `themes/` package).

- **Modern UI** — per-theme stylesheets in `builtin_themes/` (`new_ui` in settings).
- **Classic UI** — still supported; prefer `GUI.app.ui.qt.themes.ui_mode` (`is_classic_ui`, `classic_stylesheet_for`).

## Plugin widget toolkit

Import Qt widgets from leaf modules under `app/ui/qt/widgets/` (the package `__init__` does not re-export). Optional helpers: `ProgressIndicator`, `StreamOutputPanel`, `LoadingOverlay`, `CardSection`, `HorizontalCard`, `InfoCard`. Prefer `GUI.app.ui.definitions` for backend-neutral chrome when writing plugins.

## Documentation

Generated with MkDocs + mkdocstrings (`docs/`, `mkdocs.yml`). Update **docstrings** and those pages when the API changes—do not maintain a parallel hand-written API reference here.

```bash
cd GUI
python -m pip install -r requirements-docs.txt
python -m mkdocs serve    # local preview
python -m mkdocs build    # writes site/ (gitignored)
```
