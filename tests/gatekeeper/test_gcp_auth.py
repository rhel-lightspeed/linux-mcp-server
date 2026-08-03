import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.gatekeeper.gcp_auth import GCPAuthError
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_location
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_project


class TestGCPAuth:
    def test_get_gcp_project_from_config(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "project", "from-config")
        mocker.patch.dict("os.environ", {}, clear=True)
        assert get_gcp_project() == "from-config"

    def test_get_gcp_project_from_env(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "project", None)
        mocker.patch.dict("os.environ", {"VERTEXAI_PROJECT": "from-env"}, clear=True)
        assert get_gcp_project() == "from-env"

    def test_get_gcp_project_missing(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "project", None)
        mocker.patch.dict("os.environ", {}, clear=True)
        with pytest.raises(GCPAuthError, match="Vertex backend requires a GCP project"):
            get_gcp_project()

    def test_get_gcp_location_from_env(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "location", None)
        mocker.patch.dict("os.environ", {"VERTEXAI_LOCATION": "us-central1"}, clear=True)
        assert get_gcp_location() == "us-central1"

    def test_get_gcp_location_default(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "location", None)
        mocker.patch.dict("os.environ", {}, clear=True)
        assert get_gcp_location() == "global"
