"""Tests for the PCP metrics guide that the pcp_guide tool returns.

The guide exists so models stop inventing PCP metric names, so the name checks
below are the point of this file: a name that drifts out of the real namespace
makes the guide worse than useless. Everything is checked against the
``rhel10_metrics`` capture, which is what a default pmlogger records.
"""

import re

from collections.abc import Iterator

import pytest

from linux_mcp_server.utils.pcp import PCP_GUIDE_TOOL
from linux_mcp_server.utils.pcp import read_pcp_guide

from .conftest import CapturedMetric


#: The guide is loaded into a model's context on demand, so it has to stay small
#: enough that reading it is cheaper than the pcp_list_metrics dump it replaces.
MAX_GUIDE_BYTES = 20_000


@pytest.fixture(scope="module")
def guide() -> str:
    return read_pcp_guide()


@pytest.fixture(scope="module")
def guide_metrics(guide: str) -> set[str]:
    """Every dotted, backticked name in the guide, which is how it cites metrics.

    Subtree prefixes such as ``kernel.cpu.util`` are deliberately written without
    backticks in the guide, since they are not queryable names.
    """
    return set(re.findall(r"`([a-z][a-z0-9_]*(?:\.[a-zA-Z0-9_]+)+)`", guide))


def test_guide_cites_metrics(guide_metrics: set[str]):
    assert len(guide_metrics) > 100, "guide should cover the common metrics across all subsystems"


def test_every_metric_is_one_a_default_pmlogger_records(
    guide_metrics: set[str], rhel10_metrics: dict[str, CapturedMetric]
):
    """No invented names, and nothing that only exists live: the tools read archives,
    so a metric no pmlogger records is of no use even if the PMNS does know it.

    A site can configure pmlogger to record more or less than the default, which is
    why the guide says to check pcp_list_metrics rather than promising this holds
    everywhere; the default is the one configuration we can hold the catalog to.
    """
    unlogged = guide_metrics - rhel10_metrics.keys()
    assert unlogged == set(), f"guide cites metrics a default pmlogger does not record: {sorted(unlogged)}"


def _catalog_entries(guide: str) -> list[str]:
    """Each catalog bullet, joined with the continuation lines it wraps onto.

    Only bullets count. Metrics are also named in the surrounding prose, and
    attributing a prose mention to whichever bullet happens to precede it would
    check the annotations of an unrelated metric.
    """
    entries: list[str] = []
    for line in guide.splitlines():
        if line.lstrip().startswith("- "):
            entries.append(line.strip())
        elif entries and line.startswith("  ") and line.strip():
            entries[-1] += " " + line.strip()
        elif not line.strip():
            entries.append("")  # a blank line ends any open bullet
    return [e for e in entries if e]


def _catalog_entry(guide: str, name: str) -> str | None:
    """The catalog bullet that *defines* ``name``, or None if nothing does.

    An entry reads ``- `a`, `b` — description [markers]``. Only the names before
    the dash are defined by it; ones in the description are cross-references to
    an entry elsewhere, and carry no annotations of their own.
    """
    defining = [e for e in _catalog_entries(guide) if f"`{name}`" in e.split("—")[0]]
    assert len(defining) <= 1, f"{name} is defined by {len(defining)} catalog entries; annotations could disagree"
    return defining[0] if defining else None


def _annotated(
    guide: str, guide_metrics: set[str], rhel10_metrics: dict[str, CapturedMetric]
) -> Iterator[tuple[str, str, CapturedMetric]]:
    """Each metric the catalog defines, with its bullet and what pminfo said of it.

    Metrics cited only in prose are skipped: they carry no annotations of their own,
    so there is nothing about them to agree or disagree with the capture.
    """
    for name in sorted(guide_metrics & rhel10_metrics.keys()):
        if (entry := _catalog_entry(guide, name)) is not None:
            yield name, entry, rhel10_metrics[name]


def test_every_catalog_metric_has_a_descriptor(
    guide: str, guide_metrics: set[str], rhel10_metrics: dict[str, CapturedMetric]
):
    """Listing a metric pminfo cannot describe just buys the caller a failed query.

    An archive names derived metrics whether or not their definitions bind, so being
    recorded is not enough on its own; an empty descriptor is pminfo reporting that it
    could not look the metric up.
    """
    undescribed = [
        name for name, _entry, metric in _annotated(guide, guide_metrics, rhel10_metrics) if not metric.semantics
    ]
    assert undescribed == [], f"catalog metrics pminfo has no descriptor for: {undescribed}"


def test_counter_markers_match_pcp(guide: str, guide_metrics: set[str], rhel10_metrics: dict[str, CapturedMetric]):
    """A counter read as an instantaneous value is silently misinterpreted: the guide
    tells the caller that anything unmarked is reported as-is, when in fact a counter
    comes back rate-converted. An unwarranted marker misleads just as badly."""
    wrong = [
        f"{name} is {metric.semantics!r} but its entry {'omits' if metric.semantics == 'counter' else 'has'} [counter]"
        for name, entry, metric in _annotated(guide, guide_metrics, rhel10_metrics)
        if (metric.semantics == "counter") != ("[counter]" in entry)
    ]
    assert wrong == [], "\n".join(wrong)


def test_per_instance_markers_match_pcp(guide: str, guide_metrics: set[str], rhel10_metrics: dict[str, CapturedMetric]):
    """An unflagged instance domain means unexpected `metric-instance` columns."""
    wrong = [
        f"{name} is {'instanced' if metric.instanced else 'singular'} but its entry "
        f"{'lacks' if metric.instanced else 'has'} a [per-X] marker"
        for name, entry, metric in _annotated(guide, guide_metrics, rhel10_metrics)
        if metric.instanced != ("[per-" in entry)
    ]
    assert wrong == [], "\n".join(wrong)


def test_guide_fits_in_budget(guide: str):
    size = len(guide.encode())
    assert size <= MAX_GUIDE_BYTES, f"guide is {size} bytes, over the {MAX_GUIDE_BYTES} byte budget"


async def test_the_tool_returns_the_guide(mcp_client, guide: str):
    result = await mcp_client.call_tool(PCP_GUIDE_TOOL, {"host": "localhost"})

    assert result.content[0].text == guide


async def test_whatever_asks_for_a_metric_name_points_at_the_guide(mcp_client):
    """A guide nothing points at is a guide the model never reads, which leaves it
    inventing metric names — the thing the guide exists to stop. So every tool that
    makes the model supply a PCP name has to say where the names come from.

    Tools that mention PCP without taking a name of their own are left out:
    pcp_performance_summary picks its own metrics, and get_system_information
    returns the pointer in its result rather than carrying it in its description.
    """
    from linux_mcp_server import server

    texts = {
        name: text
        for name, text in vars(server).items()
        if name.startswith("INSTRUCTIONS_") and "PCP" in text  # not the run-script-only set
    }
    for tool in await mcp_client.list_tools():
        if {"metrics", "prefix"} & tool.inputSchema.get("properties", {}).keys():
            texts[tool.name] = tool.description or ""

    assert texts.keys() >= {"pcp_list_metrics", "pcp_query_metrics"}, f"expected tools missing from {texts.keys()}"

    silent = sorted(where for where, text in texts.items() if PCP_GUIDE_TOOL not in text)
    assert silent == [], f"these ask for a metric name without naming the guide: {silent}"
