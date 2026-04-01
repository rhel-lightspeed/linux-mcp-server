# Copyright Red Hat
import json


async def test_get_disk_usage(mcp_session):
    """ """
    response = await mcp_session.call_tool("get_disk_usage")
    assert response is not None
    data = json.loads(response.content[0].text)
    assert "filesystems" in data
    assert len(data["filesystems"]) > 0
    assert "target" in data["filesystems"][0]
