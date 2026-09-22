import typing as t

from pydantic import Field
from pydantic import StringConstraints


# The host value that means "the system the MCP server is running on" - we never
# connect to it over SSH.
LOCALHOST = "localhost"

Host = t.Annotated[
    str,
    Field(
        description=f"System to run on: '{LOCALHOST}' for the system the MCP server runs on, "
        "or a remote host to connect to via SSH",
        examples=[LOCALHOST, "web1.example.com"],
    ),
]
UpperCase = t.Annotated[str, StringConstraints(to_upper=True)]
