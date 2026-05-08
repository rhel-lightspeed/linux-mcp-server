# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
import typing as t

from pydantic import Field
from pydantic import StringConstraints


Host = t.Annotated[str | None, Field(description="Remote host to connect to via SSH")]
UpperCase = t.Annotated[str, StringConstraints(to_upper=True)]
