# Basic UI Application

Reusable multi-UI application framework (git submodule / [Pyside6-UI](https://github.com/CrippledTrack/Pyside6-UI)).

Host applications supply branding and plugins via an optional `app_plugins/` (or `platforms/`) tree next to `GUI/`. Those host trees are **integration fixtures**, not part of the framework itself.

## What you get

- **Services** — Qt-free DI (`ServiceContainer`, settings, admin, daemon, plugins, notifications)
- **Plugin system** — protocol-based extension points (tabs, menus, toolbar, status, settings, …)
- **UI abstractions** — toolkit-neutral shell / presenter contracts
- **Qt backend** — full implementation under `GUI/app/ui/qt/` (classic and modern themes)
- **Privileged daemon** (Linux) — pipe-based elevated command runner

API version: see `GUI_API_VERSION` in `app/constants.py`.

## Quick start

See the package `README.md` (next to `mkdocs.yml`) for run/build instructions.

```bash
# from the directory that contains GUI/
python -m GUI
```

## Documentation

This site is built with MkDocs + mkdocstrings. Prefer updating **docstrings** and these pages when the public API changes, rather than hand-maintaining a separate API reference.
