"""Collapsing the PCP metric namespace into a listing a model can actually read.

``pminfo -t`` names every metric the host knows about: around 2700 of them, some
190KB of text, on a stock RHEL install. The namespace is deep rather than wide,
though, so naming its interior nodes and saying how many metrics each one hides
conveys the shape of the whole thing in a few dozen lines. The caller drills in
by asking again with a node's name as the prefix.
"""

import functools

from collections import defaultdict
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from importlib import resources

import linux_mcp_server

from linux_mcp_server.models import PCPMetricNode
from linux_mcp_server.parsers import parse_pminfo_listing


#: Lines a collapsed listing aims for. Small enough that a caller can afford to
#: walk several levels of the namespace, large enough that most of them take one
#: step rather than three.
DEFAULT_MAX_LINES = 50

#: Descriptions of the interior nodes, which pminfo cannot supply because only
#: leaves are metrics and only metrics have help text.
_NAMESPACE_DESCRIPTIONS = "resources/pcp-namespaces.txt"


@functools.cache
def namespace_descriptions() -> Mapping[str, str]:
    """Descriptions of namespace nodes, shipped with the server.

    Deliberately incomplete: a namespace with no entry here simply lists without
    a description, which is no worse than what pminfo gives us.
    """
    listing = resources.files(linux_mcp_server).joinpath(_NAMESPACE_DESCRIPTIONS).read_text()
    return parse_pminfo_listing(listing)


def _group(names: Iterable[str], depth: int) -> dict[str, list[str]]:
    """Bucket metric names by their first ``depth + 1`` components, in first-seen order.

    This runs once per candidate namespace and walks that namespace's whole subtree
    each time, so a deep name is re-split at every level above it. Measured rather
    than assumed to be acceptable: collapsing the full 2700-metric RHEL 10 namespace
    takes about 1ms on a 2024 laptop, so there is nothing here worth optimizing.
    """
    groups: defaultdict[str, list[str]] = defaultdict(list)

    for name in names:
        groups[".".join(name.split(".")[: depth + 1])].append(name)

    return dict(groups)


def _is_metric(node: str, members: Mapping[str, list[str]]) -> bool:
    """Whether ``node`` is a metric rather than a namespace.

    Not ``len(members[node]) == 1``: a namespace holding a single metric has one
    member too, and that member is the metric's name rather than its own.
    """
    return members[node] == [node]


def _names_a_metric(node: str, expanded: Mapping[str, list[str]], members: Mapping[str, list[str]]) -> bool:
    """Whether the lines ``node`` expands into hold any metric name at all."""
    return any(
        _is_metric(child, members) or (child in expanded and _names_a_metric(child, expanded, members))
        for child in expanded[node]
    )


def _drop_pointless_expansions(
    expanded: dict[str, list[str]], members: Mapping[str, list[str]], max_lines: int
) -> None:
    """Undo the expansions that bought the caller nothing.

    An expansion earns its lines by naming a metric. One that yields nothing but
    further namespaces has not, and if the whole subtree would fit in a listing
    of its own then it never will: a caller who asks for the node gets back
    everything the expansion showed and the rest besides, so those lines only
    spelled out names they were going to see anyway. Without this, ``rpc``
    uselessly expands to ``rpc.client`` and ``rpc.server``.

    Deepest first, because collapsing a child can leave its parent with nothing
    but namespaces too. The freed lines are not spent again: a listing shorter
    than ``max_lines`` is the win here, not room to fill.
    """
    for node in reversed(list(expanded)):
        if len(members[node]) <= max_lines and not _names_a_metric(node, expanded, members):
            del expanded[node]


def _listing(nodes: Iterable[str], expanded: Mapping[str, list[str]]) -> Iterator[str]:
    """Walk ``nodes``, descending into the ones that stayed expanded."""
    for node in nodes:
        if node in expanded:
            yield from _listing(expanded[node], expanded)
        else:
            yield node


def collapse_metric_tree(
    metrics: Mapping[str, str],
    prefix: str | None = None,
    max_lines: int = DEFAULT_MAX_LINES,
) -> list[PCPMetricNode]:
    """Lay ``metrics`` out one level below ``prefix``, expanding what fits in ``max_lines``.

    Expansion runs level by level, cheapest namespace first, so a level's small
    namespaces all open up before a large one spends what is left of the budget.
    A namespace with a single child costs nothing and so always opens.

    A final pass then undoes the expansions that turned out to buy nothing; see
    :func:`_drop_pointless_expansions`.

    ``max_lines`` is a target rather than a limit. A namespace can be wider than
    it all on its own, and there is nothing to collapse in that case.
    """
    members = _group(metrics, prefix.count(".") + 1 if prefix else 0)
    top = list(members)
    expanded: dict[str, list[str]] = {}
    lines = len(top)
    level = list(top)

    while level:
        expandable = []
        for node in level:
            if not _is_metric(node, members):
                expandable.append((node, _group(members[node], node.count(".") + 1)))
        expandable.sort(key=lambda candidate: len(candidate[1]))

        level = []
        for node, children in expandable:
            cost = len(children) - 1
            if lines + cost > max_lines:
                continue
            lines += cost
            members.update(children)
            expanded[node] = list(children)
            level.extend(children)

    _drop_pointless_expansions(expanded, members, max_lines)

    layout = _listing(top, expanded)
    described = namespace_descriptions()
    return [
        PCPMetricNode(name=node, description=metrics[node])
        if _is_metric(node, members)
        else PCPMetricNode(name=node, description=described.get(node, ""), metric_count=len(members[node]))
        for node in layout
    ]
