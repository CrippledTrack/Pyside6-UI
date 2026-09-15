"""Linux Qt xcb deps: package managers by tool presence, not distro ID.

Mocks ``shutil.which`` / package queries. No sudo, display, or package managers.
"""

from __future__ import annotations

from GUI.app.ui.qt import deps_service as deps
from GUI.app.ui.qt.deps_service import (
    APT_PACKAGES,
    DNF_PACKAGES,
    PACMAN_PACKAGES,
    PackageManager,
    QtDepsService,
)


_QT6_APT_RUNTIME = (
    "libxcb-cursor0",
    "libxcb-icccm4",
    "libxcb-image0",
    "libxcb-keysyms1",
    "libxcb-randr0",
    "libxcb-render-util0",
    "libxcb-shape0",
    "libxcb-shm0",
    "libxcb-sync1",
    "libxcb-util1",
    "libxcb-xfixes0",
    "libxcb-xinerama0",
    "libxcb-xkb1",
    "libx11-xcb1",
    "libxkbcommon0",
    "libxkbcommon-x11-0",
    "libegl1",
)

_QT6_DNF_RUNTIME = (
    "xcb-util-cursor",
    "xcb-util-image",
    "xcb-util-keysyms",
    "xcb-util-renderutil",
    "xcb-util-wm",
    "xcb-util",
    "libxcb",
    "libX11-xcb",
    "libxkbcommon",
    "libxkbcommon-x11",
    "libglvnd-egl",
)

_QT6_PACMAN_RUNTIME = (
    "xcb-util-cursor",
    "xcb-util-image",
    "xcb-util-keysyms",
    "xcb-util-renderutil",
    "xcb-util-wm",
    "xcb-util",
    "libxcb",
    "libx11",
    "libxkbcommon",
    "libxkbcommon-x11",
    "libglvnd",
)


def _which_for(*tools: str):
    present = set(tools)

    def _which(name: str) -> str | None:
        if name in present:
            return f"/usr/bin/{name}"
        return None

    return _which


def test_apt_detected_when_tools_present(monkeypatch) -> None:
    monkeypatch.setattr(deps.shutil, "which", _which_for("apt-get", "dpkg-query"))
    manager = deps._detect_package_manager()
    assert manager is not None
    assert manager.id == "apt"
    assert manager.packages == tuple(APT_PACKAGES)


def test_dnf_detected_when_tools_present(monkeypatch) -> None:
    monkeypatch.setattr(deps.shutil, "which", _which_for("dnf", "rpm"))
    manager = deps._detect_package_manager()
    assert manager is not None
    assert manager.id == "dnf"
    assert manager.packages == tuple(DNF_PACKAGES)


def test_pacman_detected_when_tools_present(monkeypatch) -> None:
    monkeypatch.setattr(deps.shutil, "which", _which_for("pacman"))
    manager = deps._detect_package_manager()
    assert manager is not None
    assert manager.id == "pacman"
    assert manager.packages == tuple(PACMAN_PACKAGES)


def test_apt_wins_over_dnf_and_pacman(monkeypatch) -> None:
    monkeypatch.setattr(
        deps.shutil,
        "which",
        _which_for("apt-get", "dpkg-query", "dnf", "rpm", "pacman"),
    )
    manager = deps._detect_package_manager()
    assert manager is not None
    assert manager.id == "apt"


def test_dnf_wins_over_pacman_when_no_apt(monkeypatch) -> None:
    monkeypatch.setattr(deps.shutil, "which", _which_for("dnf", "rpm", "pacman"))
    manager = deps._detect_package_manager()
    assert manager is not None
    assert manager.id == "dnf"


def test_no_manager_when_tools_missing(monkeypatch) -> None:
    monkeypatch.setattr(deps.shutil, "which", lambda _name: None)
    assert deps._detect_package_manager() is None


def test_detection_without_distro_id(monkeypatch) -> None:
    monkeypatch.setattr(deps.shutil, "which", _which_for("dnf", "rpm"))
    assert not hasattr(deps, "_detect_distribution_id")
    manager = deps._detect_package_manager()
    assert manager is not None
    assert manager.id == "dnf"


def test_apt_packages_are_qt6_xcb_runtime() -> None:
    assert "qtwayland5" not in APT_PACKAGES
    missing = [pkg for pkg in _QT6_APT_RUNTIME if pkg not in APT_PACKAGES]
    assert missing == [], f"APT_PACKAGES missing Qt 6 xcb runtime packages: {missing}"


def test_dnf_packages_are_qt6_xcb_runtime() -> None:
    missing = [pkg for pkg in _QT6_DNF_RUNTIME if pkg not in DNF_PACKAGES]
    assert missing == [], f"DNF_PACKAGES missing Qt 6 xcb runtime packages: {missing}"


def test_pacman_packages_are_qt6_xcb_runtime() -> None:
    missing = [pkg for pkg in _QT6_PACMAN_RUNTIME if pkg not in PACMAN_PACKAGES]
    assert missing == [], f"PACMAN_PACKAGES missing Qt 6 xcb runtime packages: {missing}"


def test_manual_hints_match_managers() -> None:
    apt_hint = deps._apt_manual_hint()
    assert "apt-get update" in apt_hint
    assert "apt-get install" in apt_hint
    assert "qtwayland5" not in apt_hint
    for pkg in APT_PACKAGES:
        assert pkg in apt_hint

    dnf_hint = deps._dnf_manual_hint()
    assert "dnf install" in dnf_hint
    for pkg in DNF_PACKAGES:
        assert pkg in dnf_hint

    pacman_hint = deps._pacman_manual_hint()
    assert "pacman -S --needed" in pacman_hint
    assert "pacman -Syu" in pacman_hint
    for pkg in PACMAN_PACKAGES:
        assert pkg in pacman_hint


def test_ensure_skips_without_package_manager(monkeypatch) -> None:
    monkeypatch.setattr(deps.platform, "system", lambda: "Linux")
    monkeypatch.setattr(deps, "_detect_package_manager", lambda: None)
    ok, hint = QtDepsService().ensure_dependencies()
    assert ok is True
    assert hint is None


def test_ensure_ok_when_packages_present(monkeypatch) -> None:
    monkeypatch.setattr(deps.platform, "system", lambda: "Linux")

    def _present(_pkg: str) -> bool:
        return True

    def _must_not_install(_packages: list[str]) -> bool:
        raise AssertionError("install must not run when packages are present")

    monkeypatch.setattr(
        deps,
        "_package_managers",
        lambda: (
            PackageManager(
                id="dnf",
                packages=tuple(DNF_PACKAGES),
                detect=lambda: True,
                is_installed=_present,
                install=_must_not_install,
                manual_hint=deps._dnf_manual_hint(),
            ),
        ),
    )
    ok, hint = QtDepsService().ensure_dependencies()
    assert ok is True
    assert hint is None


def test_ensure_installs_missing_and_returns_hint_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(deps.platform, "system", lambda: "Linux")
    installed: set[str] = set()
    calls: list[list[str]] = []

    def _is_installed(pkg: str) -> bool:
        return pkg in installed

    def _install(packages: list[str]) -> bool:
        calls.append(list(packages))
        return False

    hint = deps._pacman_manual_hint(("xcb-util-cursor", "libglvnd"))
    monkeypatch.setattr(
        deps,
        "_package_managers",
        lambda: (
            PackageManager(
                id="pacman",
                packages=("xcb-util-cursor", "libglvnd"),
                detect=lambda: True,
                is_installed=_is_installed,
                install=_install,
                manual_hint=hint,
            ),
        ),
    )
    ok, message = QtDepsService().ensure_dependencies()
    assert ok is False
    assert message == hint
    assert calls == [["xcb-util-cursor", "libglvnd"]]


def test_ensure_succeeds_after_install(monkeypatch) -> None:
    monkeypatch.setattr(deps.platform, "system", lambda: "Linux")
    installed: set[str] = set()

    def _is_installed(pkg: str) -> bool:
        return pkg in installed

    def _install(packages: list[str]) -> bool:
        installed.update(packages)
        return True

    monkeypatch.setattr(
        deps,
        "_package_managers",
        lambda: (
            PackageManager(
                id="dnf",
                packages=("xcb-util-cursor",),
                detect=lambda: True,
                is_installed=_is_installed,
                install=_install,
                manual_hint=deps._dnf_manual_hint(),
            ),
        ),
    )
    ok, hint = QtDepsService().ensure_dependencies()
    assert ok is True
    assert hint is None
    assert installed == {"xcb-util-cursor"}


def test_apt_install_shell_survives_update_hook_failure() -> None:
    script = deps._apt_install_shell(["libxcb-cursor0", "libegl1"])
    assert "APT::Update::Post-Invoke-Success::=" in script
    assert "apt-get update &&" not in script
    assert "continuing with install" in script
    assert "apt-get install -y --no-install-recommends libxcb-cursor0 libegl1" in script
    assert script.rstrip().endswith("exit $?")


def test_apt_install_command_shape(monkeypatch) -> None:
    seen: list[list[str]] = []

    def _fake_elevated(cmd: list[str], description: str) -> bool:
        seen.append(list(cmd))
        assert "apt" in description.lower()
        return True

    monkeypatch.setattr(deps, "_run_elevated", _fake_elevated)
    assert deps._install_apt_packages(["libxcb-cursor0", "libegl1"]) is True
    assert len(seen) == 1
    assert seen[0][:2] == ["sh", "-c"]
    assert seen[0][2] == deps._apt_install_shell(["libxcb-cursor0", "libegl1"])


def test_dnf_install_command_shape(monkeypatch) -> None:
    seen: list[list[str]] = []

    def _fake_elevated(cmd: list[str], description: str) -> bool:
        seen.append(list(cmd))
        assert "dnf" in description.lower()
        return True

    monkeypatch.setattr(deps, "_run_elevated", _fake_elevated)
    assert deps._install_dnf_packages(["xcb-util-cursor", "libxcb"]) is True
    assert seen == [
        [
            "dnf",
            "install",
            "-y",
            "--setopt=install_weak_deps=False",
            "xcb-util-cursor",
            "libxcb",
        ]
    ]


def test_pacman_install_command_shape(monkeypatch) -> None:
    seen: list[list[str]] = []

    def _fake_elevated(cmd: list[str], description: str) -> bool:
        seen.append(list(cmd))
        assert "pacman" in description.lower()
        return True

    monkeypatch.setattr(deps, "_run_elevated", _fake_elevated)
    assert deps._install_pacman_packages(["xcb-util-cursor", "libxcb"]) is True
    assert seen == [
        [
            "pacman",
            "-S",
            "--needed",
            "--noconfirm",
            "xcb-util-cursor",
            "libxcb",
        ]
    ]


def test_ensure_non_linux_skips(monkeypatch) -> None:
    monkeypatch.setattr(deps.platform, "system", lambda: "Windows")

    def _boom() -> None:
        raise AssertionError("package manager must not be probed off Linux")

    monkeypatch.setattr(deps, "_detect_package_manager", _boom)
    ok, hint = QtDepsService().ensure_dependencies()
    assert ok is True
    assert hint is None


def test_should_skip_qt_deps_flag() -> None:
    assert deps.should_skip_qt_deps(["main.py", "--skip-qt-deps"]) is True
    assert deps.should_skip_qt_deps(["main.py", "--dev"]) is False
    assert deps.should_skip_qt_deps(["main.py", "-dev"]) is False
    assert deps.should_skip_qt_deps(["main.py", "--dev", "--ui-backend=qt"]) is False
    assert deps.should_skip_qt_deps([]) is False
    # Chained with --dev: still only the explicit skip flag bypasses.
    assert deps.should_skip_qt_deps(["main.py", "--dev", "--skip-qt-deps"]) is True
    assert deps.should_skip_qt_deps(["main.py", "--skip-qt-deps", "--dev"]) is True


def test_ensure_dependencies_skip_bypasses_check(monkeypatch) -> None:
    monkeypatch.setattr(deps.platform, "system", lambda: "Linux")

    def _boom() -> None:
        raise AssertionError("package manager must not be probed when skip=True")

    monkeypatch.setattr(deps, "_detect_package_manager", _boom)
    ok, hint = QtDepsService().ensure_dependencies(skip=True)
    assert ok is True
    assert hint is None
