import typing as t

from pydantic import Field


Host = t.Annotated[str, Field(description="Remote host to connect to")]
