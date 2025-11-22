import typing as t

from pydantic import Field


Host = t.Annotated[str, Field(description="Remote host to connect to")]
Username = t.Annotated[str, Field(description="SSH username (if not provided, the current user account is used)")]
