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
2. Sample plugins in `GUI/plugins/` (dev / non-frozen; skip with `GUI_LOAD_SAMPLE_PLUGINS=0`)
3. External `plugins/` drop-in next to the executable or project root

Constants merge the same way: host overrides → GUI defaults. `GUI_API_VERSION` is not overridable.

## Example

See `plugins/example_plugin.py` in this package for a plugin that exercises the main extension interfaces and the backend-neutral `definitions` kit.
