"""
PyInstaller build orchestration script for the GUI application.

Handles the full build pipeline:
  1. Resolves project layout (parent-project vs standalone).
  2. Generates build metadata (_build_info_generated.py).
  3. Creates a Windows version-info resource file (Windows only).
  4. Programmatically builds a PyInstaller .spec and invokes the bundler.

Usage (from the parent project root):
    python GUI/scripts/build.py [options]

Usage (standalone, from inside the GUI directory):
    python scripts/build.py [options]

Options:
    --onefile           Build a single executable (default).
    --onedir            Build a one-directory bundle instead.
    --name NAME         Override the output executable name.
    --icon PATH         Path to an .ico (Windows) or .icns/.png (macOS/Linux) icon.
    --console           Show the console window (default: auto from constants).
    --windowed          Hide the console window.
    --clean             Run a clean build (remove previous build/dist).
    --extra-data SRC:DST  Add extra data files (PyInstaller --add-data syntax).
    --extra-hidden IMPORT Add extra hidden imports.
    --exclude MODULE    Exclude a module from bundling (repeatable).
    --debug             Enable PyInstaller debug/verbose output.
    --dry-run           Print what would be done without actually building.
    --skip-build-info   Skip the build-info generation step.
    --dist-dir DIR      Override the output dist directory.
    --work-dir DIR      Override the PyInstaller work directory.
"""

from __future__ import annotations

import argparse
import datetime
import os
import platform
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _resolve_roots() -> tuple[Path, Path, Path]:
    """Return (script_dir, gui_root, project_root).

    Works regardless of whether we are invoked from the parent project or
    directly from inside the GUI directory.
    """
    script_dir = Path(__file__).resolve().parent          # GUI/scripts/
    gui_root = script_dir.parent                          # GUI/
    project_root = gui_root.parent                        # parent project

    # Heuristic: if project_root contains main.py that imports from GUI,
    # we are inside the full parent project.  Otherwise treat gui_root as
    # the standalone root.
    main_py = project_root / "main.py"
    if main_py.exists():
        return script_dir, gui_root, project_root

    # Standalone – project_root IS the gui_root.
    return script_dir, gui_root, gui_root


SCRIPT_DIR, GUI_ROOT, PROJECT_ROOT = _resolve_roots()
IS_STANDALONE = (GUI_ROOT == PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Constants helpers
# ---------------------------------------------------------------------------

def _load_constants() -> dict[str, object]:
    """Load merged constants the same way the app does at runtime.

    Falls back to GUI/app/constants.py when running standalone.
    """
    consts: dict[str, object] = {}

    # 1. GUI defaults (always available)
    gui_const_path = GUI_ROOT / "app" / "constants.py"
    consts.update(_exec_constants_file(gui_const_path))

    if not IS_STANDALONE:
        # 2. app_plugins overrides (parent project)
        app_const_path = PROJECT_ROOT / "app_plugins" / "constants.py"
        if app_const_path.exists():
            consts.update(_exec_constants_file(app_const_path))

    return consts


def _exec_constants_file(path: Path) -> dict[str, object]:
    """Execute a constants module and extract uppercase symbols."""
    namespace: dict[str, object] = {}
    try:
        code = path.read_text(encoding="utf-8")
        exec(compile(code, str(path), "exec"), namespace)  # noqa: S102
    except Exception as exc:
        print(f"  Warning: could not load {path}: {exc}", file=sys.stderr)
        return {}
    return {
        k: v
        for k, v in namespace.items()
        if k.isupper() and isinstance(v, (str, int, float, bool, list, dict, tuple, type(None)))
    }


# ---------------------------------------------------------------------------
# Build-info generation (mirrors generate_build_info.py)
# ---------------------------------------------------------------------------

def _read_pretty_name() -> str:
    """Detect the OS pretty name for embedding in build metadata."""
    override = os.environ.get("BUILD_DISTRO")
    if override:
        return override

    sysname = platform.system().lower()

    if sysname == "linux":
        return _read_linux_pretty_name() or "Linux"
    if sysname == "windows":
        return _read_windows_pretty_name() or "Windows"
    if sysname == "darwin":
        return _read_macos_pretty_name() or "macOS"

    try:
        return platform.platform() or "unknown"
    except Exception:
        return "unknown"


def _read_linux_pretty_name() -> Optional[str]:
    os_release = "/etc/os-release"
    if not os.path.exists(os_release):
        return None
    try:
        with open(os_release, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "PRETTY_NAME":
                    return v.strip().strip('"') or None
    except Exception:
        return None
    return None


def _read_windows_pretty_name() -> Optional[str]:
    try:
        release, version, csd, _ptype = platform.win32_ver()
        parts = [f"Windows {release}" if release else "Windows"]
        if version:
            parts.append(f"({version})")
        if csd:
            parts.append(csd)
        return " ".join(parts).strip() or None
    except Exception:
        return None


def _read_macos_pretty_name() -> Optional[str]:
    try:
        release, _vinfo, _machine = platform.mac_ver()
        return f"macOS {release}" if release else "macOS"
    except Exception:
        return None


def generate_build_info() -> Path:
    """Write ``GUI/app/_build_info_generated.py`` and return its path."""
    target = GUI_ROOT / "app" / "_build_info_generated.py"
    distro = _read_pretty_name()
    now = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    target.write_text(
        (
            '"""Auto-generated by scripts/build.py – do not edit."""\n\n'
            f"BUILD_DISTRO = {distro!r}\n"
            f"BUILD_TIME_UTC = {now!r}\n"
            "__all__ = ['BUILD_DISTRO', 'BUILD_TIME_UTC']\n"
        ),
        encoding="utf-8",
    )
    print(f"  Build info -> {target}")
    print(f"    BUILD_DISTRO   = {distro!r}")
    print(f"    BUILD_TIME_UTC = {now!r}")
    return target


# ---------------------------------------------------------------------------
# Windows version-info resource
# ---------------------------------------------------------------------------

def _parse_version_tuple(version_str: str) -> tuple[int, int, int, int]:
    """Turn a version string like '2.4.1' or '4.1.0-dev-3' into a 4-tuple."""
    # Strip everything from the first non-digit/dot character.
    clean = ""
    for ch in version_str:
        if ch.isdigit() or ch == ".":
            clean += ch
        else:
            break
    parts = [int(p) for p in clean.split(".") if p] if clean else [0]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])  # type: ignore[return-value]


def generate_windows_version_info(
    *,
    version: str,
    app_name: str,
    description: str,
    company: str = "",
    copyright_text: str = "",
    original_filename: str = "",
) -> Optional[Path]:
    """Generate a PyInstaller ``file_version_info.txt`` resource (Windows only).

    Returns the path to the generated file, or ``None`` on non-Windows.
    """
    if platform.system().lower() != "windows":
        return None

    ver = _parse_version_tuple(version)
    ver_str = ".".join(str(v) for v in ver)

    target = GUI_ROOT / "scripts" / "_version_info.txt"
    target.write_text(
        textwrap.dedent(f"""\
            # UTF-8
            #
            # Auto-generated by scripts/build.py – do not edit.

            VSVersionInfo(
              ffi=FixedFileInfo(
                filevers={ver},
                prodvers={ver},
                mask=0x3F,
                flags=0x0,
                OS=0x40004,
                fileType=0x1,
                subtype=0x0,
                date=(0, 0),
              ),
              kids=[
                StringFileInfo(
                  [
                    StringTable(
                      '040904B0',
                      [
                        StringStruct('CompanyName', {company!r}),
                        StringStruct('FileDescription', {description!r}),
                        StringStruct('FileVersion', {ver_str!r}),
                        StringStruct('InternalName', {app_name!r}),
                        StringStruct('LegalCopyright', {copyright_text!r}),
                        StringStruct('OriginalFilename', {original_filename!r}),
                        StringStruct('ProductName', {app_name!r}),
                        StringStruct('ProductVersion', {ver_str!r}),
                      ],
                    )
                  ]
                ),
                VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
              ]
            )
        """),
        encoding="utf-8",
    )
    print(f"  Version info -> {target}")
    return target


# ---------------------------------------------------------------------------
# Spec / PyInstaller invocation
# ---------------------------------------------------------------------------

def _collect_hidden_imports() -> List[str]:
    """Return hidden imports for modules PyInstaller cannot trace statically.

    Most of the application is reachable through the normal import graph:
    - Non-standalone: main.py -> GUI.app.app -> services, ui, themes, ...
    - Standalone: standalone_entry.py -> app.app -> services, ui, themes, ...

    Standalone uses standalone_entry.py (not run.py) because run.py relies on
    runtime sys.modules patching for ``GUI``; PyInstaller does not execute that
    shim, so ``GUI.app.*`` imports would not be discovered.

    Plugin modules are pulled in via their respective ``core_plugins.py``
    which uses explicit static imports specifically so PyInstaller can
    follow them.  We therefore only list imports that are truly dynamic
    (e.g. loaded via importlib, env-var gated, or optional).
    """
    imports = [
        # The generated build-info module is imported via a try/except and
        # may not exist at analysis time.
        "app._build_info_generated" if IS_STANDALONE else "GUI.app._build_info_generated",
    ]

    if not IS_STANDALONE:
        # app_plugins.core_plugins is imported at runtime by the plugin
        # service; ensure PyInstaller can see the top-level package.
        imports.append("app_plugins")

    return sorted(set(imports))


def _collect_data_files() -> List[tuple[str, str]]:
    """Return a list of (source, dest) pairs for --add-data.

    Most Python packages (themes, plugins, app_plugins) are reached
    through normal imports and do **not** need to be bundled as data.
    Only truly non-Python assets (icons, JSON configs, etc.) belong here.
    """
    data: List[tuple[str, str]] = []

    # Add non-Python assets here as needed, for example:
    # data.append(("path/to/assets", "assets"))

    return data


def build_pyinstaller_args(opts: argparse.Namespace, consts: dict[str, object]) -> List[str]:
    """Assemble the ``pyinstaller`` CLI arguments from parsed options."""
    # Determine the entry point
    if IS_STANDALONE:
        entry = str(GUI_ROOT / "standalone_entry.py")
    else:
        entry = str(PROJECT_ROOT / "main.py")

    args: List[str] = ["pyinstaller"]

    # Standalone: add GUI root to module search path so "app" package is found.
    if IS_STANDALONE:
        args.extend(["--paths", str(GUI_ROOT)])

    # -- One-file vs one-dir ---------------------------------------------------
    if opts.onedir:
        args.append("--onedir")
    else:
        args.append("--onefile")

    # -- Name ------------------------------------------------------------------
    name = opts.name
    if not name:
        raw_name = str(consts.get("VERSION_NAME", "Application"))
        # Sanitize for a filename
        name = raw_name.replace(" ", "_")
    args.extend(["--name", name])

    # -- Console / windowed ----------------------------------------------------
    if opts.windowed:
        args.append("--windowed")
    elif opts.console:
        args.append("--console")
    else:
        # Auto-detect from constants
        show_console = consts.get("SHOW_CONSOLE", False)
        args.append("--console" if show_console else "--windowed")

    # -- Icon ------------------------------------------------------------------
    if opts.icon:
        icon_path = Path(opts.icon).resolve()
        if icon_path.exists():
            args.extend(["--icon", str(icon_path)])
        else:
            print(f"  Warning: icon not found at {icon_path}, skipping", file=sys.stderr)

    # -- Hidden imports --------------------------------------------------------
    hidden = _collect_hidden_imports()
    for extra in (opts.extra_hidden or []):
        hidden.append(extra)
    for imp in hidden:
        args.extend(["--hidden-import", imp])

    # -- Data files ------------------------------------------------------------
    sep = ";" if platform.system().lower() == "windows" else ":"
    data_files = _collect_data_files()
    for extra in (opts.extra_data or []):
        # Expect "src:dst" or "src;dst"
        parts = extra.replace(";", ":").split(":", 1)
        if len(parts) == 2:
            data_files.append((parts[0], parts[1]))
        else:
            print(f"  Warning: ignoring malformed --extra-data {extra!r}", file=sys.stderr)

    for src, dst in data_files:
        args.extend(["--add-data", f"{src}{sep}{dst}"])

    # -- Excludes --------------------------------------------------------------
    excludes = list(opts.exclude or [])
    for mod in excludes:
        args.extend(["--exclude-module", mod])

    # -- Windows version info --------------------------------------------------
    if platform.system().lower() == "windows":
        version_str = str(consts.get("VERSION", "0.0.0"))
        app_name_str = str(consts.get("VERSION_NAME", "Application"))
        desc = str(consts.get("VERSION_INFO", {}).get("description", app_name_str))  # type: ignore[union-attr]
        vi_path = generate_windows_version_info(
            version=version_str,
            app_name=app_name_str,
            description=desc,
            original_filename=f"{name}.exe",
        )
        if vi_path:
            args.extend(["--version-file", str(vi_path)])

    # -- Output dirs -----------------------------------------------------------
    if opts.dist_dir:
        args.extend(["--distpath", opts.dist_dir])

    if opts.work_dir:
        args.extend(["--workpath", opts.work_dir])

    # -- Misc ------------------------------------------------------------------
    if opts.clean:
        args.append("--clean")

    if opts.debug:
        args.extend(["--log-level", "DEBUG"])

    # Don't prompt for confirmation
    args.append("--noconfirm")

    # Entry point last
    args.append(entry)

    return args


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the GUI application with PyInstaller.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python GUI/scripts/build.py
              python GUI/scripts/build.py --onedir --name MyApp --icon assets/icon.ico
              python GUI/scripts/build.py --clean --debug
              python GUI/scripts/build.py --dry-run
        """),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--onefile", action="store_true", default=True, help="Single-file executable (default)")
    mode.add_argument("--onedir", action="store_true", help="One-directory bundle")

    parser.add_argument("--name", type=str, default="", help="Override executable name")
    parser.add_argument("--icon", type=str, default="", help="Path to application icon")

    console_group = parser.add_mutually_exclusive_group()
    console_group.add_argument("--console", action="store_true", help="Show console window")
    console_group.add_argument("--windowed", action="store_true", help="Hide console window")

    parser.add_argument("--clean", action="store_true", help="Clean build artifacts before building")
    parser.add_argument("--debug", action="store_true", help="Enable verbose PyInstaller output")
    parser.add_argument("--dry-run", action="store_true", help="Print build plan without executing")
    parser.add_argument("--skip-build-info", action="store_true", help="Skip build-info generation step")

    parser.add_argument("--extra-data", action="append", metavar="SRC:DST", help="Additional data files (repeatable)")
    parser.add_argument("--extra-hidden", action="append", metavar="IMPORT", help="Additional hidden imports (repeatable)")
    parser.add_argument("--exclude", action="append", metavar="MODULE", help="Modules to exclude from bundling (repeatable)")

    parser.add_argument("--dist-dir", type=str, default="", help="Override dist output directory")
    parser.add_argument("--work-dir", type=str, default="", help="Override PyInstaller work directory")

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    opts = parse_args(argv)
    sysname = platform.system().lower()

    print("=" * 60)
    print("  GUI PyInstaller Build")
    print("=" * 60)
    print(f"  Platform     : {sysname}")
    print(f"  GUI root     : {GUI_ROOT}")
    print(f"  Project root : {PROJECT_ROOT}")
    print(f"  Standalone   : {IS_STANDALONE}")
    print()

    # ---- Load constants ------------------------------------------------------
    print("[1/4] Loading application constants ...")
    consts = _load_constants()
    version = consts.get("VERSION", "unknown")
    app_name = consts.get("VERSION_NAME", "Application")
    print(f"  VERSION      = {version!r}")
    print(f"  VERSION_NAME = {app_name!r}")
    print()

    # ---- Generate build info -------------------------------------------------
    if not opts.skip_build_info:
        print("[2/4] Generating build metadata ...")
        generate_build_info()
    else:
        print("[2/4] Skipping build metadata (--skip-build-info)")
    print()

    # ---- Assemble PyInstaller command ----------------------------------------
    print("[3/4] Preparing PyInstaller configuration ...")
    pyinstaller_args = build_pyinstaller_args(opts, consts)

    hidden_count = sum(1 for a in pyinstaller_args if a == "--hidden-import")
    data_count = sum(1 for a in pyinstaller_args if a == "--add-data")
    exclude_count = sum(1 for a in pyinstaller_args if a == "--exclude-module")
    print(f"  Hidden imports : {hidden_count}")
    print(f"  Data bundles   : {data_count}")
    print(f"  Excludes       : {exclude_count}")
    print()

    if opts.dry_run:
        print("[DRY RUN] Would execute:")
        # Pretty-print the command
        print("  " + " \\\n    ".join(pyinstaller_args))
        print()
        print("Done (dry run).")
        return 0

    # ---- Run PyInstaller -----------------------------------------------------
    print("[4/4] Running PyInstaller ...")
    print("-" * 60)
    try:
        result = subprocess.run(
            pyinstaller_args,
            cwd=str(PROJECT_ROOT),
            check=False,
        )
    except FileNotFoundError:
        print(
            "\nError: 'pyinstaller' not found. Install it with:\n"
            "  pip install pyinstaller",
            file=sys.stderr,
        )
        return 1

    print("-" * 60)

    if result.returncode == 0:
        print("\nBuild succeeded!")
        dist_dir = opts.dist_dir or str(PROJECT_ROOT / "dist")
        print(f"  Output: {dist_dir}")
    else:
        print(f"\nBuild failed (exit code {result.returncode}).", file=sys.stderr)

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
