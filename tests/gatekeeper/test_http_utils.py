import pytest

from linux_mcp_server.gatekeeper.http_utils import GatekeeperHTTPError
from linux_mcp_server.gatekeeper.http_utils import post_json


async def test_post_json_success(mocker):
    response = mocker.MagicMock()
    response.is_success = True
    response.json.return_value = {"ok": True}
    mock_client = mocker.AsyncMock()
    mock_client.post.return_value = response
    mocker.patch("linux_mcp_server.gatekeeper.http_utils.HTTP_CLIENT", mock_client)

    result = await post_json(
        provider="openai",
        url="https://example.com/v1/responses",
        headers={"Authorization": "Bearer test"},
        body={"model": "gpt-5.4"},
    )

    assert result == {"ok": True}
    mock_client.post.assert_awaited_once()


async def test_post_json_error(mocker):
    response = mocker.MagicMock()
    response.is_success = False
    response.status_code = 503
    response.text = "service unavailable"
    mock_client = mocker.AsyncMock()
    mock_client.post.return_value = response
    mocker.patch("linux_mcp_server.gatekeeper.http_utils.HTTP_CLIENT", mock_client)

    with pytest.raises(GatekeeperHTTPError, match="openai API error \\(503\\)"):
        await post_json(
            provider="openai",
            url="https://example.com/v1/responses",
            headers={},
            body={},
        )
