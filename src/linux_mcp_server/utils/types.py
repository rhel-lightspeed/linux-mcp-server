import typing as t


Host = t.Annotated[str, "Remote host to connect to"]
Username = t.Annotated[str, "SSH username (if not provided, the current user account is used)"]
