"""Tests for parse_pminfo_listing."""

from linux_mcp_server.parsers import parse_pminfo_listing


def test_reads_names_and_help_text():
    listing = "mem.physmem [total system memory metric reported by /proc/meminfo]\nmem.freemem [free system memory]\n"

    assert parse_pminfo_listing(listing) == {
        "mem.physmem": "total system memory metric reported by /proc/meminfo",
        "mem.freemem": "free system memory",
    }


def test_keeps_pminfo_order():
    """pminfo walks the namespace depth first, which groups related metrics far better than sorting."""
    listing = "mem.util.used [used]\nmem.util.free [free]\ndisk.all.read [read]\n"

    assert list(parse_pminfo_listing(listing)) == ["mem.util.used", "mem.util.free", "disk.all.read"]


def test_accepts_a_metric_with_no_help_text():
    """A PMDA need not ship help text, and pminfo then prints the bare name."""
    assert parse_pminfo_listing("mem.physmem\n") == {"mem.physmem": ""}


def test_keeps_a_metric_whose_help_text_an_archive_lacks():
    """Read from an archive, pminfo reports the missing text inline. Dropping the
    line would lose a metric that is recorded and perfectly queryable."""
    listing = "pmcd.seqnum One-line Help: Error: One-line or help text is not available\n"

    assert parse_pminfo_listing(listing) == {"pmcd.seqnum": ""}


def test_keeps_brackets_inside_help_text():
    listing = "ipc.sem.max_sem [maximum number of semaphores (from semctl(..,IPC_INFO,..)) [sic]]\n"

    assert parse_pminfo_listing(listing) == {
        "ipc.sem.max_sem": "maximum number of semaphores (from semctl(..,IPC_INFO,..)) [sic]"
    }


def test_skips_what_is_not_an_entry():
    """The namespace description file is in this format too, and carries comments."""
    listing = "# a comment\n\nmem.physmem [total memory]\nError: nosuch: Unknown metric name\n"

    assert parse_pminfo_listing(listing) == {"mem.physmem": "total memory"}
