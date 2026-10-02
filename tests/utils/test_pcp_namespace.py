"""Tests for collapsing the PCP metric namespace.

A real capture from a stock RHEL 10 install backs the last two classes, because
the whole point of the collapsing is to make *that* tree browsable; a synthetic
tree cannot tell us whether the budget is well chosen. pcp_list_metrics reads the
archives, so what a default pmlogger records is the tree a caller actually meets.
"""

import pytest

from linux_mcp_server.utils.pcp_namespace import collapse_metric_tree
from linux_mcp_server.utils.pcp_namespace import DEFAULT_MAX_LINES
from linux_mcp_server.utils.pcp_namespace import namespace_descriptions

from ..conftest import CapturedMetric


def tree(*names: str) -> dict[str, str]:
    """A namespace whose metrics are described by their own last component."""
    return {name: name.rsplit(".", 1)[-1] for name in names}


def crowded(*names: str) -> dict[str, str]:
    """``names`` alongside six metrics of their own, to leave little budget for expanding them.

    A namespace only stays shut while its own subtree is small when something
    else has spent the budget, which on a real system is the breadth of the top
    level. These tests want that state without a hundred lines of fixture.
    """
    return tree(*(f"z{i}" for i in range(6)), *names)


def listed(nodes) -> list[tuple[str, int | None]]:
    return [(node.name, node.metric_count) for node in nodes]


@pytest.fixture(scope="module")
def rhel10_logged(rhel10_metrics: dict[str, CapturedMetric]) -> dict[str, str]:
    """The capture in the shape collapse_metric_tree takes: name to help text."""
    return {name: metric.help for name, metric in rhel10_metrics.items()}


def under(metrics: dict[str, str], prefix: str) -> dict[str, str]:
    """The subtree pminfo would return for ``prefix``."""
    return {name: text for name, text in metrics.items() if name == prefix or name.startswith(f"{prefix}.")}


class TestCollapsing:
    def test_a_small_tree_is_listed_whole(self):
        nodes = collapse_metric_tree(tree("a.b", "a.c.d", "a.c.e"), "a", max_lines=10)

        assert listed(nodes) == [("a.b", None), ("a.c.d", None), ("a.c.e", None)]

    def test_a_namespace_that_does_not_fit_is_collapsed(self):
        metrics = tree("a.b", *(f"a.wide.m{i}" for i in range(10)))

        nodes = collapse_metric_tree(metrics, "a", max_lines=5)

        assert listed(nodes) == [("a.b", None), ("a.wide", 10)]

    def test_the_count_is_of_metrics_not_of_children(self):
        """It tells the caller how much is hidden, which direct children do not."""
        metrics = tree(*(f"a.deep.x{i}.y{j}" for i in range(3) for j in range(4)))

        nodes = collapse_metric_tree(metrics, "a", max_lines=1)

        assert listed(nodes) == [("a.deep", 12)]

    def test_small_namespaces_expand_before_large_ones(self):
        """Cheapest first, so one big namespace cannot spend the whole budget."""
        metrics = tree("a.small.p", "a.small.q", *(f"a.big.m{i}" for i in range(20)))

        nodes = collapse_metric_tree(metrics, "a", max_lines=5)

        assert listed(nodes) == [("a.small.p", None), ("a.small.q", None), ("a.big", 20)]

    def test_an_only_child_is_free_to_expand(self):
        """A chain of single children costs no extra lines, so it should never cost a round trip."""
        nodes = collapse_metric_tree(tree("a.b.c.d.e"), "a", max_lines=1)

        assert listed(nodes) == [("a.b.c.d.e", None)]

    def test_expansion_continues_into_the_next_level(self):
        metrics = tree("a.b.c", "a.b.d", "a.e.f", "a.e.g")

        nodes = collapse_metric_tree(metrics, "a", max_lines=4)

        assert listed(nodes) == [("a.b.c", None), ("a.b.d", None), ("a.e.f", None), ("a.e.g", None)]

    def test_a_level_stops_expanding_once_the_budget_is_gone(self):
        metrics = tree("a.b.c", "a.b.d", "a.e.f", "a.e.g")

        nodes = collapse_metric_tree(metrics, "a", max_lines=3)

        assert listed(nodes) == [("a.b.c", None), ("a.b.d", None), ("a.e", 2)]

    def test_a_flat_namespace_may_exceed_the_budget(self):
        """With nothing left to collapse the budget is a target, not a limit."""
        nodes = collapse_metric_tree(tree(*(f"a.m{i}" for i in range(20))), "a", max_lines=5)

        assert len(nodes) == 20

    def test_pminfo_order_is_preserved(self):
        """Listing metrics in namespace order keeps related ones together."""
        metrics = tree("a.z", "a.y.q", "a.y.p", "a.x")

        nodes = collapse_metric_tree(metrics, "a", max_lines=10)

        assert [node.name for node in nodes] == ["a.z", "a.y.q", "a.y.p", "a.x"]

    def test_a_prefix_naming_a_single_metric_lists_it(self):
        nodes = collapse_metric_tree({"mem.physmem": "total memory"}, "mem.physmem")

        assert listed(nodes) == [("mem.physmem", None)]

    def test_no_prefix_lists_from_the_root(self):
        nodes = collapse_metric_tree(tree("a.b", "c.d"), None, max_lines=2)

        assert listed(nodes) == [("a.b", None), ("c.d", None)]


class TestPointlessExpansions:
    """An expansion into nothing but more namespaces is undone again.

    The caller learns no metric name from such lines, and if the subtree fits in
    a listing of its own then asking for the one collapsed name gets them
    everything those lines held. Spending a line per child to say less is a
    straight loss.
    """

    def test_an_expansion_naming_no_metric_is_undone(self):
        nodes = collapse_metric_tree(crowded("a.b.p", "a.b.q", "a.c.p", "a.c.q"), None, max_lines=8)

        assert ("a", 4) in listed(nodes)
        assert "a.b" not in [node.name for node in nodes]

    def test_a_subtree_too_big_to_list_in_one_step_stays_expanded(self):
        """Collapsing this would promise a listing the caller cannot actually get back."""
        metrics = crowded(*(f"a.{child}.m{i}" for child in "bc" for i in range(10)))

        nodes = collapse_metric_tree(metrics, None, max_lines=8)

        assert ("a.b", 10) in listed(nodes)
        assert ("a.c", 10) in listed(nodes)

    def test_an_expansion_naming_even_one_metric_is_kept(self):
        """a.m is a name the caller can query, and collapsing a would hide it."""
        nodes = collapse_metric_tree(crowded("a.m", "a.c.p", "a.c.q"), None, max_lines=8)

        assert ("a.m", None) in listed(nodes)
        assert ("a.c", 2) in listed(nodes)

    def test_undoing_a_child_can_undo_its_parent_too(self):
        """Which is why this runs deepest first: a.b collapsing leaves a with only namespaces."""
        nodes = collapse_metric_tree(crowded("a.b.c.p", "a.b.c.q", "a.b.d.p", "a.b.d.q"), None, max_lines=8)

        assert ("a", 4) in listed(nodes)


class TestDescriptions:
    def test_a_metric_is_described_by_its_pminfo_help_text(self):
        nodes = collapse_metric_tree({"mem.physmem": "total system memory"}, "mem")

        assert nodes[0].description == "total system memory"

    def test_a_namespace_is_described_by_the_shipped_database(self):
        """pminfo cannot describe an interior node, so a bare name and count is all we would have."""
        nodes = collapse_metric_tree({f"mem.vmstat.m{i}": "" for i in range(200)}, "mem")

        assert [node.name for node in nodes] == ["mem.vmstat"]
        assert nodes[0].description == namespace_descriptions()["mem.vmstat"]

    def test_an_undescribed_namespace_simply_has_none(self):
        nodes = collapse_metric_tree(tree(*(f"a.wide.m{i}" for i in range(100))), "a")

        assert listed(nodes) == [("a.wide", 100)]
        assert nodes[0].description == ""


class TestAgainstARealSystem:
    """The tree that motivated all of this: ~1200 metrics, ~90KB of pminfo output."""

    def test_the_recorded_namespace_collapses_to_a_readable_listing(self, rhel10_logged):
        nodes = collapse_metric_tree(rhel10_logged, None)

        assert len(nodes) <= DEFAULT_MAX_LINES + 5, "the root listing should stay close to the budget"
        assert sum(node.metric_count or 1 for node in nodes) == len(rhel10_logged)

    @pytest.mark.parametrize("prefix", ["mem", "disk", "network", "kernel", "proc", "xfs"])
    def test_every_recorded_subsystem_is_browsable_in_one_step(self, prefix, rhel10_logged):
        nodes = collapse_metric_tree(under(rhel10_logged, prefix), prefix)

        assert len(nodes) <= DEFAULT_MAX_LINES + 5
        assert all(node.name.startswith(f"{prefix}.") for node in nodes)

    def test_the_metrics_the_guide_names_are_at_most_two_steps_away(self, rhel10_logged):
        """A caller who knows the subsystem but not the metric should not have to walk far."""
        target = "disk.dev.await"

        first = collapse_metric_tree(under(rhel10_logged, "disk"), "disk")
        assert "disk.dev" in [node.name for node in first]

        second = collapse_metric_tree(under(rhel10_logged, "disk.dev"), "disk.dev")
        assert target in [node.name for node in second]

    def test_a_namespace_of_namespaces_is_left_shut(self, rhel10_logged):
        """rpc.client and rpc.server name no metric between them, and rpc holds few
        enough that asking for it lists every one, so the two lines said nothing."""
        names = [node.name for node in collapse_metric_tree(rhel10_logged, None)]

        assert "rpc" in names
        assert "rpc.client" not in names

    def test_every_listed_namespace_can_be_asked_for(self, rhel10_logged):
        """A name the listing offers has to be one pminfo will accept as a prefix."""
        for node in collapse_metric_tree(rhel10_logged, None):
            if node.metric_count:
                assert under(rhel10_logged, node.name), f"{node.name} names nothing"
