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

The facade contains no toolkit imports. Each active backend implements controls
in its own `style_map` and content-bearing windows in its own `dialog_map`;
plugins must not import either backend map directly. Definitions loads these
modules by package convention (`GUI.app.ui.<backend>.style_map` and
`GUI.app.ui.<backend>.dialog_map`), so adding a backend does not require editing
the facade.

Custom windows use `create_dialog`, `set_dialog_content`, and `open_dialog`.
Pass `default_size=(width, height)` only when a desktop window needs a
best-effort initial pixel size; other backends may ignore the hint. Completion
is callback-driven:

```python
dialog = create_dialog("Settings", parent=context.parent, modal=True)
content = create_column(parent=dialog)
add(content, create_label("Settings content"))
add(content, dialog_button_row(dialog))
set_dialog_content(dialog, content)
open_dialog(dialog, on_closed=lambda accepted: save() if accepted else None)
```

There is deliberately no blocking public `run_modal()` result. Backends may
render a dialog as a native window, overlay, or panel while preserving the
callback contract. Message boxes and main-thread dispatch remain separate
concerns supplied by `IDialogPresenter` and `IUIEventLoop`.
Live log viewers should marshal worker-thread records with
`IUIEventLoop.invoke_on_main` rather than toolkit signal bridges.

Host dialog controllers that are toolkit-neutral live in `GUI.app.ui.dialogs`
(About, Log Viewer, Plugin Management). Qt-only dialogs such as Theme remain
under `GUI.app.ui.qt.dialogs`.

Use `create_card()` for themed untitled panels, `create_label(..., align="center"|"end")`
for header/value alignment, and `ButtonRole.SECONDARY` for outlined actions next
to `ButtonRole.PRIMARY` closes/saves.

Combo items may be plain labels or `(label, opaque_value)` tuples; `get_value`
returns the opaque value when supplied. Log-like surfaces can use
`append_log_text(..., level=logging.INFO)` so line colors follow the same
level mapping as console logging, or `append_text(..., role=...)` for generic
themed lines. `clear_text` and `scroll_to_end` avoid toolkit cursors.
`pick_save_file` provides a best-effort backend save picker and returns `None`
when cancelled or unavailable.
For log/code output, `create_text_area(wrap=False, monospace=True)` requests
readable backend-native fixed-width presentation without naming a font.

Prefer `tab_root(context)` for the tab's root column, and
`create_button(..., on_click=callback)` to wire actions in one step. Role
arguments are optional (defaults are fine for simple tabs).

Omit `ui_backends` (or leave it empty) to support every registered UI backend;
set it only when a plugin must restrict hosts (for example `["qt"]`).

Legacy tabs that only override `create_widget` (Qt widgets) are treated as
Qt-shaped: future non-Qt backends will not host them even when `ui_backends`
is empty. Prefer `create_tab_content` + definitions for portable tabs.

Only plugins that implement the **Tab** extension are hosted as tabs. Menu-only
or service-only plugins can still be enabled for their other extensions.

User enable/disable choices are persisted as diffs from each plugin's
`disabled_by_default` flag (`disabled_plugins` and `enabled_plugins` in
settings). Enabling a default-off plugin survives restart and reload.

## Identity, dependencies, and lifecycle

Set `plugin_id` to a namespaced immutable id (for example `gui.example`).
`plugin_name` and `tab_title` are display strings. The main window tab bar and
window title use `tab_title` (falling back to `plugin_name`); session restore
and registry lookups keep using `plugin_id`. If `plugin_id` is omitted,
it defaults to `plugin_name`, so unique existing names keep working.

Show All Platform Tabs prefixes UI labels (`plugin_ui_label`) and
`tab_title` (`[Linux] Updates`). `plugin_name` and `plugin_id` stay
unprefixed so settings, session restore, and `dependencies` never see a
prefixed key.

`dependencies` lists provider ids (or unique display names). After discovery
the host rejects missing or cyclic edges, starts providers first, and stops
consumers first. Disabling a provider also disables enabled dependents
(Plugin Management warns first).

`PluginService.activate_plugin` / `deactivate_plugin` own enablement:
construction and `on_plugin_enabled` must succeed before the enabled flag is
kept; disable stops dependents, runs `on_plugin_disabled`, then unloads.
Queued async events are dropped after unload. Application close shuts service
extensions down before disposing tab views.

Public `register_plugin_force` still bypasses version checks and enables
immediately. Plugin Management uses `register_rejected_plugin` (register
without enable) and then a single True `toggle_plugin` so enablement is not
applied twice.

