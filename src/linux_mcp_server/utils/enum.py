# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
from enum import Enum


try:
    from enum import StrEnum  # pyright: ignore[reportAttributeAccessIssue]
except ImportError:
    StrEnum = None


class StringEnum(str, Enum):
    def __str__(self):
        return self.value


if StrEnum is None:
    StrEnum = StringEnum
