import pytest

from linux_mcp_server.gatekeeper import GatekeeperResult
from linux_mcp_server.gatekeeper import GatekeeperStatus


RESULT_CASES = [
    (GatekeeperStatus.OK, "", "OK"),
    (GatekeeperStatus.BAD_DESCRIPTION, "Script does something else", "Bad description: Script does something else"),
    (GatekeeperStatus.POLICY, "Violates policy X", "Policy violation: Violates policy X"),
    (GatekeeperStatus.MODIFIES_SYSTEM, "Writes to /etc",
     "Script modifies the system - use run_script_modify: Writes to /etc"),
    (GatekeeperStatus.UNCLEAR, "Hard to understand", "Unclear script: Hard to understand"),
    (GatekeeperStatus.DANGEROUS, "Could break the system", "Dangerous script: Could break the system"),
    (GatekeeperStatus.MALICIOUS, "Contains backdoor", "Possibly malicious script: not allowed"),
]


class TestGatekeeperResultDescription:
    @pytest.mark.parametrize("status,detail,expected_description", RESULT_CASES)
    def test_description(self, status, detail, expected_description):
        result = GatekeeperResult(status=status, detail=detail)
        assert result.description == expected_description

    @pytest.mark.parametrize("status,detail,expected_description", RESULT_CASES)
    def test_round_trip(self, status, detail, expected_description):
        """Test that we can round-trip from result -> description -> parsed result."""
        result = GatekeeperResult(status=status, detail=detail)
        parsed = GatekeeperResult.parse_from_description(result.description)

        assert parsed.status == status
        # MALICIOUS descriptions hide the original detail
        if status == GatekeeperStatus.MALICIOUS:
            assert parsed.detail == "not allowed"
        else:
            assert parsed.detail == detail
