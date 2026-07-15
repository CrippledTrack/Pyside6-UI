# Plugin development

Plugins are instance-based extensions discovered at startup. The registry stores
plugin classes, creates an instance on first use, injects the application
`ServiceContainer`, and reuses that instance until the plugin is disabled or the
registry is cleared.

Use `plugins/example_plugin.py` as the complete reference implementation. The
examples below assume this repository is checked out as the `GUI/` package in a
parent project.

## Minimal tab plugin

Create a module in one of the discovery locations listed below. A tab plugin
should inherit `BaseTabPlugin`, declare its metadata as class attributes, and
accept the injected container:

```python
from GUI.app.qt_bindings import QLabel
from GUI.plugin_system.base import BaseTabPlugin


class HealthPlugin(BaseTabPlugin):
    plugin_name = "Health"
    tab_title = "System Health"
    plugin_version = "1.0.0"
    supported_platforms = ["Linux"]
    min_gui_version = "5.2.0"

    def __init__(self, container):
        super().__init__(container)

    def create_widget(self, parent=None):
        return QLabel("Healthy", parent)
```

`plugin_name` and `tab_title` must not use the `BaseTabPlugin` placeholder
values, and `plugin_version` must be non-empty. An empty `supported_platforms`
list means all platforms. Recognized macOS names include `Darwin`, `macOS`, and
`osx`.

Each plugin class must expose at least one extension method. Inheriting
`BaseTabPlugin` supplies the tab contract and common lifecycle behavior.

## Discovery and conflict order

Core plugins come from each source's `core_plugins.py`. Plugins with the same
registered name are merged in this order:

1. `app_plugins/core_plugins.py`
2. `platforms/core_plugins.py`
3. `GUI/plugin_system/core_plugins.py`

Non-core packages are scanned in descending priority:

| Priority | Current platform | Common |
| --- | --- | --- |
| Project | `app_plugins.<platform>.plugins` (300) | `app_plugins.common.plugins` (290) |
| Shared | `platforms.<platform>.plugins` (200) | `platforms.common.plugins` (190) |
| Framework | `GUI.plugins` (100) | — |

In development mode, enabling cross-platform display also scans foreign
`app_plugins` packages at priority 250 and foreign `platforms` packages at
priority 150. Foreign plugins receive a platform prefix in their registered
name and load with OS API mocks where available.

User plugin files are scanned after package sources and cannot replace an
already registered name. Their directory depends on the launch layout:

| Launch layout | User plugin directory |
| --- | --- |
| Parent project (`main.py` or `python -m GUI`) | `<project>/plugins/*.py` |
| Standalone source (`GUI/run.py`) | `GUI/user_plugins/*.py` |
| Frozen executable | `<executable-dir>/plugins/*.py` |

Create the user plugin directory if it does not exist.

Only top-level `.py` files are scanned in user plugin directories. Package
sources scan immediate importable modules in each `plugins` package. Keep an
`__init__.py` in package directories and ensure plugin imports work from the
parent project root.

Name conflicts are resolved before registration: higher-priority package
sources win, and core plugins cannot be replaced by external plugins.

`PluginDiscovery` contains support for the `gui_app_tabs` packaging entry-point
group, but application startup does not enable entry-point discovery. Use one
of the package or user-file locations above for plugins that must load
automatically.

## Metadata and compatibility

`BaseTabPlugin` supports these class attributes:

| Attribute | Meaning |
| --- | --- |
| `plugin_name` | Unique registry and settings key |
| `tab_title` | Tab label |
| `plugin_version` | Plugin's own version |
| `plugin_description` | Description in plugin management |
| `plugin_author`, `plugin_authors` | Displayed authorship |
| `supported_platforms` | Empty for all, or names such as `Windows`, `Linux`, `macOS` |
| `requires_admin` | Delay tab creation until the privileged daemon is available |
| `disabled_by_default` | Disable on first discovery |
| `min_gui_version` | Minimum GUI version, for example `5.2.0` |
| `required_gui_version` | Version range, for example `>=5.2.0,<6.0.0` |
| `dependencies` | Informational list of plugin names |

Compatibility checks use `GUI_API_VERSION`, not an application's overridden
display version. `GUI_API_VERSION` cannot be overridden by
`app_plugins/constants.py`.

## Extension surfaces

A single plugin instance may implement any combination of these methods:

| Extension | Required method | Result or lifecycle |
| --- | --- | --- |
| Tab | `create_widget(parent)` | Return a `QWidget`; creation is deferred until the tab is opened |
| Menu | `get_menu_items()` | Return `MenuItemDefinition` values |
| Status | `create_status_widget(parent)` | Return a status-bar widget |
| Toolbar | `get_toolbar_actions()` | Return `ToolbarAction` values |
| Service | `on_application_start(container)` | Start non-UI work |
| Event subscriber | `get_event_subscriptions()` | Map event names to callbacks |
| Settings | Override `get_settings_widget(parent)` | Return a widget whose `get_settings()` returns a dictionary |

Optional lifecycle methods include `on_tab_activated`,
`on_tab_deactivated`, `on_plugin_enabled`, `on_plugin_disabled`,
`on_application_shutdown`, and `on_settings_changed(settings)`. Definitions for
menu and toolbar values live in the repository's `plugin_system/types.py`; all
extension protocols live in `plugin_system/interfaces.py`. Parent projects
import these as `GUI.plugin_system.types` and `GUI.plugin_system.interfaces`.

The container is the supported route to application services:

```python
from GUI.app.services.notification_service import NotificationService


def __init__(self, container):
    super().__init__(container)
    self.notifications = container.get(NotificationService)
```

## Lifecycle and cleanup

The registry constructs `plugin_class(container)` lazily and caches the result.
Disabling a plugin follows this order:

1. call `on_plugin_disabled()` when an instance exists;
2. remove menu, toolbar, status, and service extensions;
3. call `on_application_shutdown()` for a running service extension;
4. unload the cached instance and run framework cleanup.

`BaseTabPlugin` cleanup stops `QTimer` attributes, asks `QThread` attributes to
quit and waits up to one second, and closes/deletes widgets found on the plugin
or its tab widget. Keep these resources as instance attributes so cleanup can
find them. The framework does not understand arbitrary worker pools, processes,
file handles, or subscriptions; release those in `on_application_shutdown()` or
`on_plugin_disabled()`.

Do not reuse a widget or plugin instance after disable. Re-enabling constructs a
new plugin instance.

## Single-plugin builds

Single-plugin mode filters classes while they register and hides multi-plugin
UI controls. Configure it in a parent project's `app_plugins/constants.py`:

```python
SINGLE_PLUGIN_MODE = True
SINGLE_PLUGIN_NAME = "Health"
```

It can also be selected at launch:

```bash
python -m GUI --single-plugin=Health
GUI_SINGLE_PLUGIN=Health python -m GUI
```

`GUI_SINGLE_PLUGIN_NAME` is an alias for `GUI_SINGLE_PLUGIN`.

Matching is case-insensitive against the class name, `plugin_name`, and
`tab_title`; substring matches are accepted. If mode is enabled without a name,
the first plugin accepted in discovery order is the only plugin registered, so
set an explicit name for deterministic builds.

The merged configuration is cached on first access. Set environment variables
and command-line arguments before application bootstrap.

## Troubleshooting

- **Plugin is absent:** check that its module imports successfully, its class is
  defined in that module, and its name does not conflict with a higher-priority
  source.
- **Plugin is rejected:** inspect logs for metadata validation, platform, or GUI
  version incompatibility messages.
- **Relative imports fail in a user plugin:** user files are loaded as
  namespaced standalone modules. Put shared code in an importable parent-project
  package or use a package discovery source.
- **Admin tab stays unavailable:** start the Linux privileged daemon or remove
  `requires_admin` if the tab does not perform privileged work. See
  [Linux privileged daemon](DAEMON.md). The `--dev` flag bypasses this tab gate
  for development and should not be used to validate production elevation.
- **Resources survive disable:** store Qt resources as plugin/widget attributes
  and explicitly close non-Qt resources in lifecycle hooks.
