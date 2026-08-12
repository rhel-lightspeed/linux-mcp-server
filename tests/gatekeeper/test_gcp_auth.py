import sys

import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import VertexAIGatekeeperConfig
from linux_mcp_server.gatekeeper.gcp_auth import GCPAuthError
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_access_token
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_location
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_project


class TestGCPAuth:
    def test_get_gcp_project_from_config(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "vertex_ai", VertexAIGatekeeperConfig(project="from-config"))
        mocker.patch.dict("os.environ", {}, clear=True)
        assert get_gcp_project() == "from-config"

    def test_get_gcp_project_from_env(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "vertex_ai", None)
        mocker.patch.dict("os.environ", {"VERTEXAI_PROJECT": "from-env"}, clear=True)
        assert get_gcp_project() == "from-env"

    def test_get_gcp_project_missing(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "vertex_ai", None)
        mocker.patch.dict("os.environ", {}, clear=True)
        with pytest.raises(GCPAuthError, match="Vertex AI provider requires a GCP project"):
            get_gcp_project()

    def test_get_gcp_location_from_env(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "vertex_ai", None)
        mocker.patch.dict("os.environ", {"VERTEXAI_LOCATION": "us-central1"}, clear=True)
        assert get_gcp_location() == "us-central1"

    def test_get_gcp_location_default(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "vertex_ai", None)
        mocker.patch.dict("os.environ", {}, clear=True)
        assert get_gcp_location() == "global"

    def test_get_gcp_access_token_missing_dependency(self, mocker):
        mocker.patch.dict(
            sys.modules,
            {
                "google": None,
                "google.auth": None,
                "google.auth.transport": None,
                "google.auth.transport.requests": None,
            },
        )
        with pytest.raises(GCPAuthError, match="gcp optional dependency"):
            get_gcp_access_token()

    def test_get_gcp_access_token_success(self, mocker):
        mock_credentials, mock_google_auth, mock_request = self._patch_google_auth(mocker, token="ya29.test-token")

        assert get_gcp_access_token() == "ya29.test-token"
        mock_google_auth.default.assert_called_once_with(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        mock_credentials.refresh.assert_called_once_with(mock_request)

    def test_get_gcp_access_token_empty_token(self, mocker):
        self._patch_google_auth(mocker, token=None)

        with pytest.raises(GCPAuthError, match="Failed to obtain GCP access token"):
            get_gcp_access_token()

    @staticmethod
    def _patch_google_auth(mocker, *, token: str | None):
        mock_credentials = mocker.Mock()
        mock_credentials.token = token
        mock_google_auth = mocker.Mock()
        mock_google_auth.default.return_value = (mock_credentials, "project")
        mock_request = mocker.Mock()
        mock_requests = mocker.Mock()
        mock_requests.Request.return_value = mock_request
        mock_transport = mocker.Mock()
        mock_transport.requests = mock_requests
        mock_google_auth.transport = mock_transport
        mock_google = mocker.Mock()
        mock_google.auth = mock_google_auth
        mocker.patch.dict(
            sys.modules,
            {
                "google": mock_google,
                "google.auth": mock_google_auth,
                "google.auth.transport": mock_transport,
                "google.auth.transport.requests": mock_requests,
            },
        )
        return mock_credentials, mock_google_auth, mock_request
