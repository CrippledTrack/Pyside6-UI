## GUI Submodule — How to Run with a `main.py`

### Scenario
You only have the `GUI` submodule (folder) and need to run the application. Create a `main.py` file next to the `GUI` folder (not inside it) and use it to launch the GUI.

### Required placement
Keep the files arranged like this:

```
your-project/
  main.py              <-- create this at the same level as `GUI/`
  GUI/                 <-- the GUI submodule
```

### Minimal `main.py`
Create `main.py` with the following contents:

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

### How to run
- Windows (PowerShell):
  ```bash
  py main.py
  ```
- Linux/macOS:
  ```bash
  python3 main.py
  ```

Run these commands from the directory that contains `main.py` and the `GUI/` folder.

### Packaging note (PyInstaller)
- Do **not** build/target PyInstaller using `GUI/run.py`. It is a standalone/dev shim that manipulates import state; PyInstaller cannot trace its imports.
- Standalone builds use `standalone_entry.py`, which imports `app.app` directly so PyInstaller can discover all modules.
- Non-standalone builds use `main.py` at the project root as the entry point.

### Troubleshooting
- If you see `ModuleNotFoundError: No module named 'GUI'`:
  - Ensure you are running the command from the directory that contains both `main.py` and the `GUI/` folder.
  - Confirm `main.py` is not inside the `GUI/` directory.
