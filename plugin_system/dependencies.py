"""Operational plugin dependency graph.

``dependencies`` entries may be ``plugin_id`` values or unique display names.
Missing edges and cycles are reported as actionable diagnostics; callers reject
those plugins instead of activating them.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple, Type

from .identity import plugin_display_name, plugin_identity


def _alias_map(plugins: Mapping[str, Type[Any]]) -> Dict[str, List[str]]:
    """Map display names (and ids) to plugin ids that claim them."""
    aliases: Dict[str, List[str]] = defaultdict(list)
    for plugin_id, plugin_class in plugins.items():
        aliases[plugin_id].append(plugin_id)
        display = plugin_display_name(plugin_class)
        if display != plugin_id:
            aliases[display].append(plugin_id)
    return aliases


def resolve_dep_token(
    token: str,
    plugins: Mapping[str, Type[Any]],
    aliases: Mapping[str, Sequence[str]] | None = None,
) -> Tuple[str | None, str | None]:
    """Resolve a dependency token to a plugin id.

    Returns ``(plugin_id, error)``. ``error`` is set when the token is missing
    or the display name is ambiguous.
    """
    if token in plugins:
        return token, None
    table = aliases if aliases is not None else _alias_map(plugins)
    matches = list(table.get(token, ()))
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, (
            f"ambiguous dependency '{token}' matches plugin ids: "
            + ", ".join(sorted(matches))
        )
    return None, f"missing dependency '{token}'"


def declared_dependencies(plugin_class: Type[Any]) -> List[str]:
    """Return the raw ``dependencies`` list for a plugin class."""
    raw = getattr(plugin_class, "dependencies", None) or []
    return [str(item) for item in raw if str(item).strip()]


def resolve_dependency_graph(
    plugins: Mapping[str, Type[Any]],
) -> Tuple[List[str], Dict[str, str], Dict[str, List[str]]]:
    """Resolve a provider-first startup order.

    Returns ``(startup_order, errors, edges)`` where ``errors`` maps plugin id
    to a diagnostic, and ``edges`` maps plugin id to resolved dependency ids
    (omitted for plugins that failed to resolve).
    """
    aliases = _alias_map(plugins)
    errors: Dict[str, str] = {}
    edges: Dict[str, List[str]] = {}

    for plugin_id, plugin_class in plugins.items():
        resolved: List[str] = []
        failed = False
        for token in declared_dependencies(plugin_class):
            dep_id, err = resolve_dep_token(token, plugins, aliases)
            if err or dep_id is None:
                label = plugin_display_name(plugin_class)
                errors[plugin_id] = (
                    f"Plugin '{label}' ({plugin_id}) {err}."
                )
                failed = True
                break
            if dep_id == plugin_id:
                errors[plugin_id] = (
                    f"Plugin '{plugin_display_name(plugin_class)}' "
                    f"({plugin_id}) lists itself as a dependency."
                )
                failed = True
                break
            resolved.append(dep_id)
        if not failed:
            edges[plugin_id] = resolved

    # Dependents of unresolved plugins cannot start either.
    changed = True
    while changed:
        changed = False
        for plugin_id, deps in list(edges.items()):
            bad = next((d for d in deps if d in errors or d not in plugins), None)
            if bad is None:
                continue
            if plugin_id not in errors:
                label = plugin_display_name(plugins[plugin_id])
                cause = errors.get(bad, f"'{bad}' is unavailable")
                errors[plugin_id] = (
                    f"Plugin '{label}' ({plugin_id}) depends on '{bad}' "
                    f"which cannot start ({cause})."
                )
            edges.pop(plugin_id, None)
            changed = True

    remaining = [pid for pid in plugins if pid not in errors]
    indegree = {pid: 0 for pid in remaining}
    forward: Dict[str, List[str]] = defaultdict(list)
    for plugin_id in remaining:
        for dep in edges.get(plugin_id, ()):
            if dep in indegree:
                # Edge dep -> plugin_id (provider before consumer)
                forward[dep].append(plugin_id)
                indegree[plugin_id] += 1

    queue = deque(sorted(pid for pid, n in indegree.items() if n == 0))
    order: List[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for consumer in sorted(forward[node]):
            indegree[consumer] -= 1
            if indegree[consumer] == 0:
                queue.append(consumer)

    cyclic = [pid for pid in remaining if pid not in order]
    if cyclic:
        cycle_txt = " -> ".join(cyclic + cyclic[:1])
        for plugin_id in cyclic:
            label = plugin_display_name(plugins[plugin_id])
            errors[plugin_id] = (
                f"Plugin '{label}' ({plugin_id}) is involved in a "
                f"dependency cycle: {cycle_txt}."
            )
        order = [pid for pid in order if pid not in errors]

    return order, errors, edges


def transitive_dependents(
    plugin_id: str,
    edges: Mapping[str, Iterable[str]],
) -> List[str]:
    """Return plugins that transitively depend on ``plugin_id`` (not including it)."""
    reverse: Dict[str, List[str]] = defaultdict(list)
    for consumer, deps in edges.items():
        for dep in deps:
            reverse[dep].append(consumer)
    seen: List[str] = []
    stack = list(reverse.get(plugin_id, ()))
    visiting = set(stack)
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.append(current)
        for nxt in reverse.get(current, ()):
            if nxt not in visiting:
                visiting.add(nxt)
                stack.append(nxt)
    return seen


__all__ = [
    "declared_dependencies",
    "resolve_dep_token",
    "resolve_dependency_graph",
    "transitive_dependents",
]
