# Plugins

Plugins extend the shell through protocol-based extension points in `GUI.plugin_system`.

## Extension points

Plugins may implement any combination of:

- **Tab** — `create_tab_content(context)` (preferred) or legacy `create_widget`
- **Menu** / **Toolbar** / **Status**
- **Service** — background work via the container
- **Event subscriber** / **Settings**
- **Lifecycle / cleanup** — `IPluginLifecycle`, `IPluginResourceCleanup`

Canonical protocols: [`GUI.plugin_system.interfaces`](api/plugin-interfaces.md).  
Base classes: [`BaseTabPlugin` / `CoreTabPlugin`](api/plugin-base.md).

## Host plugin directories

At runtime the framework may load plugins from (highest priority first):

1. Host `app_plugins` (or `platforms`) next to `GUI/` — **host fixtures**, not framework code
2. Sample plugins in `GUI/plugins/` (when runtime `is_dev_mode()` is on and not frozen; skip with `GUI_LOAD_SAMPLE_PLUGINS=0`)
3. External `plugins/` drop-in next to the executable or project root

Constants merge the same way: host overrides → GUI defaults. `GUI_API_VERSION` is not overridable.

## Example

See `plugins/example_plugin.py` in this package for a plugin that exercises the main extension interfaces and the backend-neutral `definitions` kit.

## Backend-neutral tab content

New tabs should implement `create_tab_content(context)` and build their content
through `GUI.app.ui.definitions`. The facade provides semantic labels and
buttons, text and numeric inputs, checkboxes, combo selections, titled groups,
tabs, forms, and read-only tables. `TableRow` adds stable row keys, optional
check columns, selection callbacks, and row-toggle callbacks without exposing
toolkit item objects. State/event helpers include `get_value`, `set_enabled`,
`on_change`, `on_click`, and `on_interval`.

Desktop-only layout ideas — resizable splits, stretch spacers, expand fill,
and pixel sizing — are **optional capabilities**. Query them with
`supports(UICapability.…)` rather than assuming Qt-style layout. When a
capability is missing, helpers no-op or fall back (for example `create_split`
stacks panes in a column). `set_split_proportions(split, (3, 2))` expresses
relative pane sizing without hardcoded pixels. Prefer `expand=True` over pixel
heights. Labels wrap by default; use `create_label(..., wrap=False)` for compact
single-line status text.
Tabs and form rows are required operations because every backend can represent
their content, even if it uses stacked sections instead of desktop tab chrome.
Table `sortable=True` is a preference a backend may ignore. Pointer-oriented
context menus are optional via `UICapability.CONTEXT_MENU`.

The facade contains no toolkit imports. Each active backend implements the same
operations in its own `style_map`; plugins must not import a backend style map
directly. Definitions-built content may be hosted inside a backend-owned custom
dialog, but dialog window lifecycle remains outside this facade. Message boxes
and main-thread dispatch remain separate concerns supplied by
`IDialogPresenter` and `IUIEventLoop`.

Prefer `tab_root(context)` for the tab's root column, and
`create_button(..., on_click=callback)` to wire actions in one step. Role
arguments are optional (defaults are fine for simple tabs).

Omit `ui_backends` (or leave it empty) to support every registered UI backend;
set it only when a plugin must restrict hosts (for example `["qt"]`).
