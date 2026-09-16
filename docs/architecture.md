# Architecture

High-level layout after the 6.0 Qt / abstractions separation. Import, API, and release notes live in the host repo's per-version changelogs (`CHANGELOG_6.0.0.md`, `CHANGELOG_6.1.0.md`) when developing from a test bed.

## Layers

| Layer | Role | Location |
|-------|------|----------|
| Bootstrap | argv, logging, DI, UI backend selection | `app/app.py` |
| Host config | App id, writable data/log/plugin paths | `app/host_config.py` |
| Services | Qt-free at import; registered as `I*` protocols | `app/services/` |
| Plugin system | Toolkit-neutral plugin contracts | `plugin_system/` |
| UI abstractions | Shell, presenters, plugin host, event loop | `app/ui/abstractions/` |
| UI glue | Backend registry, wiring, definitions kit | `app/ui/registry.py`, `backend_wiring.py`, `definitions.py` |
| Qt backend | All Qt code | `app/ui/qt/` |
| Daemon | Unix privileged pipe daemon (Linux/macOS) | `app/daemon/`, `app/utils/privileged.py`, `app/utils/elevation.py` |

## Rules of thumb

- Services must not import Qt at module load time.
- Use `PluginService` from the container; do not register raw `PluginRegistry` for app code.
- Plugin registry keys are ``plugin_id`` (display ``plugin_name`` is a unique-name convenience). Tab chrome shows ``tab_title`` (or ``plugin_name``), not the id. Show All prefixes ``tab_title`` and ``plugin_ui_label`` only; ``plugin_name`` and identity stay canonical.
- Writable settings/logs go through ``GUI.app.host_config.HostConfig`` (portable adapter defaults to ``get_base_path()``).
- Import Qt widgets from **leaf** modules under `app/ui/qt/widgets/` (package `__init__` does not re-export).
- Themes live under `app/ui/qt/themes/`.
- Prefer `app/ui/qt/themes/ui_mode` helpers for classic vs modern stylesheet branches.

## UI backends

`app/ui/registry.py` registers the shipped backends for this release (currently **`qt` only**). Plugins that need chrome without hard-coding Qt should prefer `app/ui/definitions` so the active backend supplies widgets. Definitions load `style_map` / `dialog_map` by package convention (`GUI.app.ui.<backend>…`), which leaves room for additional backends later without editing the facade.
