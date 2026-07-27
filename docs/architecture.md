# Architecture

High-level layout after the 6.0 Qt / abstractions separation. Breaking import and API notes live in the host repo changelog (`CHANGELOG_6.0.0.md`) when developing from a test bed.

## Layers

| Layer | Role | Location |
|-------|------|----------|
| Bootstrap | argv, logging, DI, UI backend selection | `app/app.py` |
| Services | Qt-free at import; registered as `I*` protocols | `app/services/` |
| Plugin system | Toolkit-neutral plugin contracts | `plugin_system/` |
| UI abstractions | Shell, presenters, plugin host, event loop | `app/ui/abstractions/` |
| UI glue | Backend registry, wiring, definitions kit | `app/ui/registry.py`, `backend_wiring.py`, `definitions.py` |
| Qt backend | All Qt code | `app/ui/qt/` |
| Daemon | Linux privileged pipe daemon | `app/daemon/`, `app/utils/privileged.py` |

## Rules of thumb

- Services must not import Qt at module load time.
- Use `PluginService` from the container; do not register raw `PluginRegistry` for app code.
- Import Qt widgets from **leaf** modules under `app/ui/qt/widgets/` (package `__init__` does not re-export).
- Themes live under `app/ui/qt/themes/`.
- Prefer `app/ui/qt/themes/ui_mode` helpers for classic vs modern stylesheet branches.

## Multi-UI

`app/ui/registry.py` registers backends (currently `qt`; `tui` is registered as WIP). Plugins that need chrome without hard-coding Qt should prefer `app/ui/definitions` so the active backend supplies widgets.
