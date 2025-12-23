# GUI Architecture Flowchart

This file contains a Mermaid diagram describing the architecture of the GUI submodule.
You can view this diagram by opening this file in an editor that supports Mermaid (like VS Code with the "Markdown Preview Mermaid Support" extension) or by copy-pasting the code block below into [Mermaid Live Editor](https://mermaid.live).

```mermaid
graph TD
    %% Entry Point
    Entry[app.py : run] -->|Initializes| Container[ServiceContainer]
    Entry -->|Initializes| ThemeMgr[ThemeManager]
    Entry -->|Initializes| MainWindow[MainWindow]
    Entry -->|Setup| Log[LoggingService]

    %% Service Container Dependencies
    Container -->|1. Manages| Settings[SettingsService]
    Container -->|2. Manages| Daemon[DaemonService]
    Container -->|3. Manages| Admin[AdminService]
    
    %% MainWindow Components
    MainWindow -->|Uses| Container
    MainWindow -->|Uses| ThemeMgr
    MainWindow -->|Connects| TabCtrl[TabController]
    MainWindow -->|Connects| PluginCtrl[PluginController]
    MainWindow -->|Connects| MenuCtrl[MenuBarController]
    MainWindow -->|Start| TabLoader[TabLoaderThread]
    
    %% Secondary Windows (Dialogs)
    MainWindow -.->|Creates| PDialog[PluginManagementDialog]
    MainWindow -.->|Creates| TDialog[ThemeDialog]
    MainWindow -.->|Creates| LDialog[LogViewerDialog]

    %% UI Managers
    MainWindow -->|Owns| ToastMgr[ToastManager]
    MainWindow -->|Owns| StatusMgr[StatusBarManager]
    MainWindow -->|Owns| TitleMgr[WindowTitleManager]
    MainWindow -->|Owns| ShortcutMgr[ShortcutManager]

    %% Plugin System Flow
    TabLoader -->|Uses| PluginSvc[PluginService]
    PluginSvc -->|Registers to| Registry[plugin_registry]
    Registry -->|Provides| Plugins[Plugins / Tabs]
    TabLoader -->|Adds to| TabCtrl
    PluginCtrl -->|Toggles| Plugins
    
    %% Cross-Component
    MenuCtrl -->|Updates| Admin
    TabCtrl -->|Uses| Admin
    ThemeMgr -->|Applies Styles| MainWindow

    %% Styling
    classDef container fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef mainwindow fill:#f3e5f5,stroke:#4a148c,stroke-width:2px;
    classDef service fill:#e8f5e9,stroke:#1b5e20,stroke-width:1px;
    classDef dialog fill:#fff3e0,stroke:#e65100,stroke-width:1px,stroke-dasharray: 5 5;
    
    class Container container;
    class MainWindow mainwindow;
    class Settings,Daemon,Admin,Log,PluginSvc service;
    class PDialog,TDialog,LDialog dialog;
```
