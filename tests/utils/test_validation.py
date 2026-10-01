"""Tests for input validation utilities."""

from pathlib import Path

import pytest

from linux_mcp_server.utils.validation import is_empty_output
from linux_mcp_server.utils.validation import is_successful_output
from linux_mcp_server.utils.validation import PathValidationError
from linux_mcp_server.utils.validation import validate_path
from linux_mcp_server.utils.validation import validate_pcp_metrics
from linux_mcp_server.utils.validation import validate_pcp_prefix


class TestIsEmptyOutput:
    """Test is_empty_output function."""

    @pytest.mark.parametrize(
        "stdout,expected",
        [
            # Empty cases - should return True
            (None, True),
            ("", True),
            ("   ", True),
            ("\t", True),
            ("\n", True),
            ("\r\n", True),
            ("  \t\n  ", True),
            # Non-empty cases - should return False
            ("output", False),
            ("  output  ", False),
            ("\noutput\n", False),
            ("0", False),
            ("false", False),
        ],
    )
    def test_is_empty_output(self, stdout, expected):
        """Test is_empty_output with various inputs."""
        assert is_empty_output(stdout) is expected


class TestIsSuccessfulOutput:
    """Test is_successful_output function."""

    @pytest.mark.parametrize(
        "returncode,stdout,expected",
        [
            # Successful cases - should return True
            (0, "output", True),
            (0, "  output  ", True),
            (0, "\noutput\n", True),
            (0, "0", True),
            (0, "false", True),
            # Failed due to non-zero returncode - should return False
            (1, "output", False),
            (1, "error message", False),
            (-1, "output", False),
            (127, "command not found", False),
            # Failed due to empty stdout - should return False
            (0, None, False),
            (0, "", False),
            (0, "   ", False),
            (0, "\t", False),
            (0, "\n", False),
            (0, "\r\n", False),
            (0, "  \t\n  ", False),
            # Both conditions fail - should return False
            (1, None, False),
            (1, "", False),
            (1, "   ", False),
        ],
    )
    def test_is_successful_output(self, returncode, stdout, expected):
        """Test is_successful_output with various returncode and stdout combinations."""
        assert is_successful_output(returncode, stdout) is expected


class TestValidatePath:
    """Test validate_path function for security and correctness."""

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/var/log/messages", Path("/var/log/messages")),
            ("/home/user/file.txt", Path("/home/user/file.txt")),
            ("/", Path("/")),
            ("/tmp", Path("/tmp")),
            ("/path/with spaces/file.txt", Path("/path/with spaces/file.txt")),
        ],
    )
    def test_valid_absolute_paths(self, path, expected):
        """Valid absolute paths are accepted and returned in POSIX format."""
        assert validate_path(path) == expected

    @pytest.mark.parametrize(
        "path",
        [
            "",
            "relative/path",
            "file.txt",
            "./relative",
            "../parent",
        ],
    )
    def test_rejects_non_absolute_paths(self, path):
        """Non-absolute paths raise PathValidationError."""
        with pytest.raises(PathValidationError, match="must be absolute|cannot be empty"):
            validate_path(path)

    @pytest.mark.parametrize(
        "path",
        [
            "/path/with\nnewline",
            "/path/with\rcarriage",
            "/path/with\x00null",
            "/path\n/injection",
            "\n/leading/newline",
        ],
    )
    def test_rejects_injection_characters(self, path):
        """Paths with injection characters (newline, carriage return, null) are rejected."""
        with pytest.raises(PathValidationError, match="invalid characters"):
            validate_path(path)

    @pytest.mark.parametrize(
        "path",
        [
            "-rf",
            "--help",
            "-/path/starting/with/dash",
        ],
    )
    def test_rejects_flag_injection(self, path):
        """Paths starting with '-' are rejected to prevent flag injection."""
        with pytest.raises(PathValidationError, match="cannot start with"):
            validate_path(path)

    def test_pathvalidationerror_is_valueerror(self):
        """PathValidationError is a ValueError subclass for compatibility."""
        assert issubclass(PathValidationError, ValueError)

    @pytest.mark.parametrize(
        "path",
        [
            "/tmp/../etc/passwd",
            "/var/log/../../etc/hosts",
            "/../root",
            "/home/user/../../../etc/shadow",
        ],
    )
    def test_rejects_path_traversal(self, path):
        """Paths containing '..' components are rejected to prevent path traversal."""
        with pytest.raises(PathValidationError, match=r"invalid component '\.\.'"):
            validate_path(path)


#: Metrics and namespaces are named the same way, so both validators take the same
#: names. Every one of these would reach pminfo or pmrep as an option, as several
#: arguments, or as a name other than the one the caller wrote.
BAD_PCP_NAMES = [
    pytest.param("-h", id="flag"),
    pytest.param("--archive=/tmp/x", id="long-flag"),
    pytest.param("mem; rm -rf /", id="shell-metacharacters"),
    pytest.param("mem util", id="space"),
    pytest.param("mem\nutil", id="newline"),
    pytest.param("mem/util", id="slash"),
    pytest.param("", id="empty"),
    pytest.param("1mem", id="leading-digit"),
    pytest.param("mem.", id="trailing-dot"),
    pytest.param(".mem", id="leading-dot"),
    pytest.param("mem..util", id="empty-component"),
]

GOOD_PCP_NAMES = ["mem", "disk.dev", "mem.util.committed_AS", "nfs4.server", "x"]


class TestValidatePcpPrefix:
    @pytest.mark.parametrize("prefix", GOOD_PCP_NAMES)
    def test_accepts_a_pmns_name(self, prefix):
        assert validate_pcp_prefix(prefix) == prefix

    @pytest.mark.parametrize("prefix", BAD_PCP_NAMES)
    def test_rejects_anything_that_could_reach_pminfo_as_an_option(self, prefix):
        with pytest.raises(ValueError, match="Invalid PCP namespace prefix"):
            validate_pcp_prefix(prefix)


class TestValidatePcpMetrics:
    def test_accepts_pmns_names(self):
        assert validate_pcp_metrics(GOOD_PCP_NAMES) == GOOD_PCP_NAMES

    @pytest.mark.parametrize("metric", BAD_PCP_NAMES)
    def test_rejects_anything_that_could_reach_pmrep_as_an_option(self, metric):
        with pytest.raises(ValueError, match="Invalid PCP metric name"):
            validate_pcp_metrics([metric])

    def test_rejects_one_bad_name_among_good_ones(self):
        with pytest.raises(ValueError, match="Invalid PCP metric name"):
            validate_pcp_metrics(["mem.util.used", "--output-file"])

    def test_requires_at_least_one_metric(self):
        """pmrep with no metrics is pmrep with whatever follows taken as the metric."""
        with pytest.raises(ValueError, match="At least one PCP metric name is required"):
            validate_pcp_metrics([])
