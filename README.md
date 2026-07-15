## GUI Submodule — How to Run and Build

### How to run

You can run the GUI in three ways:

**1. From the project root (with a `main.py` next to `GUI/`)**

- Windows (PowerShell):
  ```bash
  py main.py
  ```
- Linux/macOS:
  ```bash
  python3 main.py
  ```
  Run from the directory that contains `main.py` and the `GUI/` folder.

**2. From the project root using the module (no `main.py` required)**

- From the directory that contains the `GUI/` folder:
  ```bash
  python3 -m GUI
  ```
  (Windows: `py -m GUI`.) Behavior is the same as running `main.py`.

**3. Standalone (only the `GUI/` folder)**

- From inside the `GUI/` directory:
  ```bash
  cd GUI
  python3 run.py
  ```
  (Windows: `py run.py`.) Run adds the parent of the GUI directory to the path so the GUI package is found. Use this when the parent project does not provide a `main.py` or when you only have the GUI submodule. Optional flags: `run.py --dev`.

### Minimal `main.py` (when using option 1)

If you use option 1, create `main.py` at the same level as `GUI/`:

```
your-project/
  main.py              <-- same level as GUI/
  GUI/                 <-- the GUI submodule
```

Contents of `main.py`:

```python
import sys
from GUI.app.app import run

if __name__ == "__main__":
    raise SystemExit(run(sys.argv))
```

### Set up a virtual environment and install PySide6

It’s recommended to run the GUI inside a virtual environment.

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

To leave the environment later, run:
```bash
deactivate
```

For the complete runtime and build dependencies, install the platform
requirements file instead of installing only PySide6:

```bash
# Linux
pip install -r requirements-linux.txt

# Windows
pip install -r requirements-win.txt

# macOS
pip install PySide6 psutil pyinstaller
```

On Debian, Ubuntu, and Linux Mint, startup checks for the Qt xcb system
libraries and attempts to install missing packages through `pkexec` or `sudo`.
If automatic installation fails, the terminal error includes the required
`apt-get install` command.

### Building a standalone binary (PyInstaller)

You can build a single executable so that no external start script is needed.

- From inside the `GUI/` directory (standalone layout):
  ```bash
  cd GUI
  python3 scripts/build.py
  ```
- From the project root (same build):
  ```bash
  python3 GUI/scripts/build.py
  ```

The resulting binary is self-contained; you do **not** need to ship or run `main.py` or any other launcher. Build options (e.g. `--onedir`, `--name`, `--icon`) are documented in the script help: `python3 scripts/build.py --help`.

- In standalone layout the build script uses `run.py` as the entry; it adds the
  parent of the GUI directory (or the bundle root when frozen) to the path so
  PyInstaller sees the GUI package. In a parent-project layout the build uses
  the project's `main.py`.

### Standalone and external plugin directories

When you run standalone (`cd GUI && python run.py`), if the **parent** of `GUI/` contains an `app_plugins` or `platforms` folder that looks like this GUI’s plugin tree (e.g. has `constants.py`, `core_plugins.py`, or `linux/` / `windows/` subdirs), the app will load constants and plugins from those directories. That lets you use the full repo layout without running from the repo root. If the parent has a folder named `app_plugins` or `platforms` that is **not** for this app (e.g. another project’s), avoid running standalone from that location so the app doesn’t use the wrong constants or plugins.

### Engineering guides

- [Plugin development](docs/PLUGINS.md): discovery order, extension
  interfaces, compatibility, single-plugin mode, and cleanup.
- [Linux privileged daemon](docs/DAEMON.md): startup modes, command API,
  protocol constraints, shutdown behavior, and troubleshooting.

### Troubleshooting

- If you see `ModuleNotFoundError: No module named 'GUI'`:
  - When using `main.py` or `python -m GUI`: run from the directory that contains the `GUI/` folder (and `main.py` if using that).
  - When using standalone: run `python run.py` from inside the `GUI/` directory.
