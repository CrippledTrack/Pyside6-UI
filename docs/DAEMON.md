# Linux privileged daemon

The Linux daemon keeps the Qt application unprivileged while executing selected
commands in a root process. Application and plugin code should use
`app/utils/privileged.py`; daemon transport classes and JSON messages are
lower-level interfaces.

This subsystem is Linux-only. Windows administration follows a separate
restart-as-administrator path.

## Modes

| Mode | Selection | Process model | Constraints |
| --- | --- | --- | --- |
| Local root | The GUI already has UID or EUID 0 | Commands run in the GUI process through `LocalDaemonClient` | Supports `run_command`, `ping`, and `shutdown`; no streaming or cancellation |
| Socket | `USE_PIPE_DAEMON = False` | A root daemon accepts authenticated Unix-socket clients | Compatibility mode scheduled for removal in 6.0.0; requests on one client are serialized |
| Pipe | `USE_PIPE_DAEMON = True` | One root child communicates with its GUI parent over stdin/stdout | Beta; supports concurrent requests, streaming, and cancellation |

The framework defaults are `REQUIRE_ADMIN_BY_DEFAULT = False` and
`USE_PIPE_DAEMON = False`, so no daemon starts automatically. A parent project
can opt in to pipe-mode startup:

```python
# app_plugins/constants.py
REQUIRE_ADMIN_BY_DEFAULT = True
USE_PIPE_DAEMON = True
```

When `REQUIRE_ADMIN_BY_DEFAULT` is false, the application starts in limited
mode. When visible, the Admin menu's primary action starts the mode selected by
`USE_PIPE_DAEMON` (socket by default), and a separate **Start Pipe Daemon
(Beta)** action explicitly selects pipe mode. Integration code can select a
mode with `DaemonService.start_socket()` or `DaemonService.start_pipe()`.

If the application is already root, bootstrap installs `LocalDaemonClient`
without launching another process. Otherwise startup tries `pkexec` first and
falls back to `sudo`. The `--daemon`, `--pipe`, `--uid`, and `--gid` arguments
are internal child-process arguments assembled by `start_daemon()`; normal
launchers should configure the constants instead of passing them directly.

## Running a privileged command

Use a list of arguments whenever possible:

```python
from GUI.app.utils.privileged import run_privileged_command

result = run_privileged_command(
    ["systemctl", "restart", "example.service"],
    timeout=30,
)
result.check_returncode()
```

The helper returns `subprocess.CompletedProcess`. Check `returncode` or call
`check_returncode()` when command failure must raise an exception. A transport
failure or missing daemon raises an exception before a result is returned.

A string command is converted to `["sh", "-c", command]`. Do not interpolate
untrusted values into a string command; pass an argument list instead. Pass
`timeout=None` only for operations that may block indefinitely.

`read_privileged_file(path)` and `write_privileged_file(path, content)` are
available for simple file operations. The write helper creates a temporary
file, moves it into place, then restores the previous numeric mode and
ownership. For a new file it applies mode `0644` and attempts `root:root`.
It returns `False` on failure, so callers must check the result.

Plugins that cannot function without elevation should set:

```python
requires_admin = True
```

This delays creation of their tab widget until the daemon is available. It does
not automatically elevate arbitrary plugin methods; those methods must still
call the privileged helper. The `--dev` flag bypasses this tab gate for
development, so do not use dev mode to validate production elevation behavior.

## Startup and shutdown

Application bootstrap selects the daemon in this order:

1. non-Linux platforms skip daemon initialization;
2. a root GUI uses the in-process local client;
3. a non-root GUI with `REQUIRE_ADMIN_BY_DEFAULT = False` continues without a
   client;
4. otherwise `start_daemon()` launches the configured socket or pipe mode and
   publishes the connected client globally.

On normal application exit, `DaemonLifecycleService` requests shutdown,
disconnects the client, and stops any tracked child process. Linux
`PR_SET_PDEATHSIG` also asks the kernel to send `SIGTERM` to a spawned daemon if
its direct parent dies.

Socket mode uses one of these paths, in order:

1. `/run/user/<uid>/privileged-daemon/daemon.sock`
2. `<home>/.local/run/privileged-daemon/daemon.sock`
3. `/tmp/privileged-daemon/daemon.sock`

The daemon requires the original UID/GID before opening the socket, sets socket
mode `0600`, and checks peer credentials when Linux `SO_PEERCRED` is available.
It exits automatically after its last previously connected client disconnects.
A shutdown request is ignored while more than one socket connection remains.

Pipe mode is tied to one GUI process. EOF on the child's stdin ends its request
loop. Standard output is reserved for newline-delimited protocol messages;
Python-level prints and daemon logs are redirected to standard error.

## Protocol and concurrency

Messages are UTF-8 JSON objects terminated by `\n`:

```json
{"id":"uuid","operation":"run_command","params":{"command":["id"],"timeout":30}}
{"id":"uuid","success":true,"result":{"returncode":0,"stdout":"...","stderr":"","success":true}}
```

Supported server operations are:

| Operation | Parameters | Notes |
| --- | --- | --- |
| `ping` | `{}` | Returns `"pong"` |
| `run_command` | `command` list, optional `timeout` | Captures stdout and stderr |
| `run_command_stream` | `command` list | Pipe only; combines stderr into stdout and sends line chunks |
| `cancel` | `target_id` | Sends `SIGTERM`, then `SIGKILL` after two seconds |
| `shutdown` | `{}` | Ends the daemon when lifecycle rules allow |

Top-level `success` reports whether the protocol request was handled. For
command operations, inspect `result.returncode` or `result.success` to determine
whether the subprocess succeeded.

The pipe server dispatches work to an eight-worker thread pool. A single
`PipeDaemonReader` thread in the GUI routes responses by request ID, and a write
lock prevents requests from interleaving. Streaming callbacks run on that
reader thread, not the Qt main thread; callbacks that update widgets must post
work back through a Qt signal.

Use the low-level client only when streaming is required:

```python
from GUI.app.daemon import get_daemon_client

client = get_daemon_client()
response = client.request_stream(
    "run_command_stream",
    {"command": ["journalctl", "-u", "example.service", "-n", "20"]},
    on_chunk=print,
    timeout=30,
)
if not response["result"]["success"]:
    raise RuntimeError("journalctl failed")
```

`request_stream()` raises `RuntimeError` in socket mode. Although
`cancel_request(target_id)` exists, the convenience request methods do not
expose their generated request ID until the final response. Cancellation is
therefore currently useful only to lower-level code that already tracks the
outstanding protocol ID.

## Troubleshooting

### Privileged operations are disabled

- Confirm the host is Linux.
- If startup elevation is expected, verify
  `REQUIRE_ADMIN_BY_DEFAULT = True` in the merged constants.
- Check that either `pkexec` or `sudo` is installed and authentication was not
  cancelled.
- If startup elevation is optional, start the daemon from the Admin menu before
  opening a tab with `requires_admin = True`.

### The Admin menu is missing

`HIDE_ADMIN_MENU_BY_DEFAULT` defaults to true and the saved user setting can
also hide it. Enable the menu in the application's settings or start the daemon
through `DaemonService`. Dev mode forces the menu visible.

### Socket exists but the daemon is unavailable

`DaemonService.start_socket()` checks the existing socket, attempts a
connection, removes a stale socket if connection fails, and starts a new
daemon. Prefer that workflow over deleting runtime files manually.

### Pipe requests fail after daemon output

Only protocol JSON may be written to the daemon's raw stdout. New daemon code
must log to stderr. The pipe startup guard redirects normal `print()` calls, but
code that writes directly to `sys.stdout.buffer` can still corrupt the stream.

### Long operations time out

The privileged helper defaults to 300 seconds. Pass a larger timeout or `None`
deliberately. Client timeouts do not imply that an arbitrary external process
has performed application-level rollback; commands should be designed to be
safe to retry.
