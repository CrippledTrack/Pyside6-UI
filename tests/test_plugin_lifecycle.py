"""Plugin construction, activation, events, identity, and dependencies."""

from __future__ import annotations

import threading
import time
from concurrent.futures import CancelledError
from typing import Any, Dict, List

from GUI.app.services.plugin_service import PluginService
from GUI.plugin_system.base import BaseTabPlugin
from GUI.plugin_system.registry import PluginRegistry


class _FakeContainer:
    def get(self, _service_type: Any) -> Any:
        raise ValueError("not registered")


def _probe(
    name: str,
    *,
    plugin_id: str = "",
    dependencies: List[str] | None = None,
    **ns: Any,
) -> type:
    attrs: Dict[str, Any] = {
        "plugin_name": name,
        "plugin_id": plugin_id,
        "tab_title": name,
        "plugin_version": "1.0.0",
        "dependencies": list(dependencies or []),
        "create_tab_content": lambda self, context: object(),
    }
    attrs.update(ns)
    return type(f"Probe_{name.replace(' ', '_')}", (BaseTabPlugin,), attrs)


def _service(registry: PluginRegistry | None = None) -> PluginService:
    reg = registry or PluginRegistry()
    svc = PluginService(registry=reg)
    svc.bind_container(_FakeContainer())
    return svc


def test_single_flight_construction() -> None:
    constructed: List[Any] = []

    class Slow(_probe("Once")):
        def __init__(self, container: Any) -> None:
            super().__init__(container)
            constructed.append(self)
            time.sleep(0.08)

    svc = _service()
    svc.register_plugin(Slow)
    results: List[Any] = []

    def worker() -> None:
        results.append(svc.get_plugin_instance("Once"))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2)
    assert len(constructed) == 1
    assert results[0] is results[1] is constructed[0]


def test_stale_constructor_after_reload_is_discarded() -> None:
    started = threading.Event()
    proceed = threading.Event()
    cleaned: List[Any] = []

    class First(_probe("Reload")):
        def __init__(self, container: Any) -> None:
            super().__init__(container)
            started.set()
            proceed.wait(timeout=2)

        def _cleanup_plugin_resources(self) -> None:
            cleaned.append(self)

    class Second(_probe("Reload")):
        marker = "second"

        def __init__(self, container: Any) -> None:
            super().__init__(container)
            self.marker = "second"

    svc = _service()
    svc.register_plugin(First)
    error: List[BaseException] = []

    def worker() -> None:
        try:
            svc.get_plugin_instance("Reload")
        except BaseException as exc:
            error.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    assert started.wait(timeout=2)
    svc.clear()
    svc.register_plugin(Second)
    proceed.set()
    t.join(timeout=2)
    assert cleaned, "discarded constructor must receive cleanup"
    inst = svc.get_plugin_instance("Reload")
    assert getattr(inst, "marker", None) == "second"


def test_reentrant_construction_raises() -> None:
    class Recurse(_probe("Recurse")):
        def __init__(self, container: Any) -> None:
            super().__init__(container)
            Recurse.registry.get_plugin_instance("Recurse")

    svc = _service()
    Recurse.registry = svc._registry  # type: ignore[attr-defined]
    svc.register_plugin(Recurse)
    try:
        svc.get_plugin_instance("Recurse")
        raise AssertionError("expected re-entrant construction to raise")
    except RuntimeError as exc:
        assert "cyclic" in str(exc).lower() or "re-entrant" in str(exc).lower()


def test_failed_activation_not_committed() -> None:
    class Boom(_probe("Boom")):
        def on_plugin_enabled(self) -> None:
            raise RuntimeError("enable failed")

    svc = _service()
    svc.register_plugin(Boom)
    svc.disable_plugin("Boom")
    assert svc.activate_plugin("Boom") is False
    assert svc.is_enabled("Boom") is False
    assert svc.has_plugin_instance("Boom") is False
    assert "enable failed" in (svc.get_last_activation_error() or "")


def test_post_unload_async_event_is_dropped() -> None:
    gate = threading.Event()
    entered = threading.Semaphore(0)
    delivered: List[Any] = []

    class Sub(_probe("Sub")):
        def get_event_subscriptions(self) -> Dict[str, Any]:
            return {"probe": self._on_probe}

        def _on_probe(self, data: Dict[str, Any]) -> None:
            entered.release()
            gate.wait(timeout=2)
            delivered.append(data)

        def on_application_start(self, container: Any) -> None:
            return None

    svc = _service()
    svc.register_plugin(Sub)
    svc.get_plugin_instance("Sub")
    for _ in range(4):
        svc.publish_event_async("probe", {"n": "block"})
    for _ in range(4):
        assert entered.acquire(timeout=2)
    queued = svc.publish_event_async("probe", {"n": "late"})
    svc.unload_plugin_instance("Sub")
    gate.set()
    for fut in queued:
        try:
            fut.result(timeout=2)
        except CancelledError:
            pass
    assert all(item.get("n") != "late" for item in delivered)


def test_service_shutdown_sees_instance_before_unload() -> None:
    called: List[str] = []

    class Combo(_probe("Combo")):
        def on_application_start(self, container: Any) -> None:
            return None

        def on_application_shutdown(self) -> None:
            called.append("shutdown")

    svc = _service()
    svc.register_plugin(Combo)
    instance = svc.get_plugin_instance("Combo")
    assert svc.has_plugin_instance("Combo")
    instance.on_application_shutdown()
    svc.unload_plugin_instance("Combo")
    assert called == ["shutdown"]
    assert svc.has_plugin_instance("Combo") is False


def test_missing_dependency_rejected() -> None:
    svc = _service()
    svc.register_plugin(_probe("Consumer", dependencies=["MissingProvider"]))
    errors = svc.finalize_plugin_graph()
    assert any("MissingProvider" in msg for msg in errors.values())
    assert svc.get_plugin("Consumer") is None


def test_dependency_cycle_rejected() -> None:
    svc = _service()
    svc.register_plugin(_probe("A", plugin_id="cycle.a", dependencies=["cycle.b"]))
    svc.register_plugin(_probe("B", plugin_id="cycle.b", dependencies=["cycle.a"]))
    errors = svc.finalize_plugin_graph()
    assert errors
    assert svc.get_plugin("cycle.a") is None
    assert svc.get_plugin("cycle.b") is None


def test_provider_first_startup_and_disable_cascade() -> None:
    order: List[str] = []

    class Provider(_probe("Provider", plugin_id="graph.provider")):
        def on_application_start(self, container: Any) -> None:
            order.append("provider")

        def on_application_shutdown(self) -> None:
            order.append("provider-stop")

    class Consumer(_probe("Consumer", plugin_id="graph.consumer", dependencies=["graph.provider"])):
        def on_application_start(self, container: Any) -> None:
            order.append("consumer")

        def on_application_shutdown(self) -> None:
            order.append("consumer-stop")

    svc = _service()
    svc.register_plugin(Consumer)
    svc.register_plugin(Provider)
    errors = svc.finalize_plugin_graph()
    assert not errors
    assert svc.get_startup_order() == ["graph.provider", "graph.consumer"]
    assert svc.get_shutdown_order() == ["graph.consumer", "graph.provider"]
    deactivated = svc.deactivate_plugin("graph.provider")
    assert deactivated[0] == "graph.consumer"
    assert deactivated[-1] == "graph.provider"
    assert svc.is_enabled("graph.consumer") is False


def test_same_display_name_different_ids_coexist() -> None:
    svc = _service()
    svc.register_plugin(_probe("Probe", plugin_id="vendor.one"))
    svc.register_plugin(_probe("Probe", plugin_id="vendor.two"))
    assert svc.get_plugin("vendor.one") is not None
    assert svc.get_plugin("vendor.two") is not None
    try:
        svc.get_plugin("Probe")
        raise AssertionError("display name Probe should be ambiguous")
    except ValueError as exc:
        assert "Ambiguous" in str(exc)


def test_tab_label_uses_title_not_plugin_id() -> None:
    from GUI.plugin_system.identity import plugin_tab_label

    titled = _probe("Example Plugin", plugin_id="gui.example", tab_title="Example")
    assert plugin_tab_label(titled) == "Example"
    unnamed = _probe("Example Plugin", plugin_id="gui.example", tab_title="Unnamed Tab")
    assert plugin_tab_label(unnamed) == "Example Plugin"


def test_show_all_wrap_keeps_canonical_id() -> None:
    from GUI.plugin_system.identity import (
        plugin_identity,
        plugin_display_name,
        plugin_ui_label,
        plugin_tab_label,
    )
    from GUI.plugin_system.registry import PluginRegistry, _create_prefixed_plugin
    from GUI.plugin_system.dependencies import resolve_dep_token

    original = _probe("Updates", plugin_id="gui.linux.updates", tab_title="Updates")
    wrapped = _create_prefixed_plugin(original, "[Linux]")
    assert plugin_identity(wrapped) == "gui.linux.updates"
    assert plugin_display_name(wrapped) == "Updates"
    assert plugin_ui_label(wrapped) == "[Linux] Updates"
    assert wrapped.tab_title == "[Linux] Updates"
    assert plugin_tab_label(wrapped) == "[Linux] Updates"
    assert PluginRegistry().get_registered_name(wrapped) == "gui.linux.updates"
    plugins = {plugin_identity(wrapped): wrapped}
    dep_id, err = resolve_dep_token("gui.linux.updates", plugins)
    assert err is None and dep_id == "gui.linux.updates"
    dep_id, err = resolve_dep_token("Updates", plugins)
    assert err is None and dep_id == "gui.linux.updates"

    svc = _service()
    svc.register_plugin(wrapped)
    assert svc.resolve_plugin_key("Updates") == "gui.linux.updates"


def test_show_all_wrap_name_only_stamps_original_identity() -> None:
    from GUI.plugin_system.identity import plugin_identity, plugin_display_name, plugin_ui_label
    from GUI.plugin_system.registry import _create_prefixed_plugin

    original = _probe("Updates")
    wrapped = _create_prefixed_plugin(original, "[Linux]")
    assert plugin_identity(wrapped) == "Updates"
    assert plugin_display_name(wrapped) == "Updates"
    assert plugin_ui_label(wrapped) == "[Linux] Updates"


def test_same_plugin_id_second_external_skipped() -> None:
    svc = _service()
    first = _probe("One", plugin_id="shared.id")
    second = _probe("Two", plugin_id="shared.id")
    svc.register_plugin(first)
    svc.register_plugin(second)
    assert svc.get_plugin("shared.id") is first


def test_force_register_enables_immediately() -> None:
    svc = _service()
    rejected = _probe(
        "Incompatible",
        plugin_id="gui.incompatible",
        required_gui_version=">=99.0.0",
    )
    svc.register_plugin(rejected)
    assert svc.get_plugin("gui.incompatible") is None
    rejected_map = svc.get_rejected_plugins()
    assert "gui.incompatible" in rejected_map
    svc.register_plugin_force("gui.incompatible", rejected)
    assert svc.get_plugin("gui.incompatible") is rejected
    assert svc.is_enabled("gui.incompatible") is True
    assert "gui.incompatible" not in svc.get_rejected_plugins()


def test_register_rejected_plugin_does_not_enable() -> None:
    svc = _service()
    rejected = _probe(
        "Incompatible",
        plugin_id="gui.incompatible.off",
        required_gui_version=">=99.0.0",
    )
    svc.register_plugin(rejected)
    svc.register_rejected_plugin("gui.incompatible.off", rejected)
    assert svc.get_plugin("gui.incompatible.off") is rejected
    assert svc.is_enabled("gui.incompatible.off") is False
    assert "gui.incompatible.off" not in svc.get_rejected_plugins()


def test_core_replaces_external_drops_old_extension_categories() -> None:
    cleaned: List[Any] = []

    class External(_probe("Same", plugin_id="gui.replace")):
        def get_menu_items(self) -> list:
            return []

        def _cleanup_plugin_resources(self) -> None:
            cleaned.append(self)

    class Core(_probe("Same", plugin_id="gui.replace")):
        is_core_plugin = True

    svc = _service()
    svc.register_plugin(External)
    instance = svc.get_plugin_instance("gui.replace")
    assert "gui.replace" in svc.get_menu_extensions(enabled_only=False)
    svc.register_plugin(Core, is_core=True)
    assert svc.get_plugin("gui.replace") is Core
    assert "gui.replace" not in dict(svc.get_menu_extensions(enabled_only=False))
    assert "gui.replace" in dict(svc.get_tab_extensions(enabled_only=False))
    assert svc.peek_plugin_instance("gui.replace") is None
    assert cleaned == [instance]
