# UI abstractions

Toolkit-neutral contracts for the application shell, presenters, and plugin host.

::: GUI.app.ui.abstractions

## UI definitions

Toolkit-neutral controls, layouts, events, and state helpers for plugin content.

::: GUI.app.ui.definitions

## Host dialogs

Toolkit-neutral shell dialogs (About, Log Viewer, Plugin Management) live in
`GUI.app.ui.dialogs`. Qt-only dialogs such as Theme remain under
`GUI.app.ui.qt.dialogs`.

## Controllers

Shared host controllers (for example `PluginController`) live under
`GUI.app.ui.controllers`. Backend-specific controllers remain under
`GUI.app.ui.qt.controllers`.

## UI backends

- **Qt** (`GUI.app.ui.qt`) — shipped desktop backend for 6.0 (default)

Additional backends are not registered in 6.0; the abstractions and definitions
contracts are the extension point for later releases.
