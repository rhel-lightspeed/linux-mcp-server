from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from pydantic import BaseModel


class ExecutionContext(BaseModel):
    allow_local: bool = False
    allow_ssh_default: bool = False
    ssh_key_path: Path | None = None
    ssh_key_user: str | None = None


# Global ContextVar for storing the current execution context if no context is set execution should fail
execution_context_var: ContextVar[ExecutionContext | None] = ContextVar("execution_context", default=None)


@contextmanager
def use_execution_context(context: ExecutionContext):

    token = execution_context_var.set(context)
    try:
        yield context
    finally:
        execution_context_var.reset(token)


# Get the current execution context or None if not set
def get_execution_context() -> ExecutionContext | None:
    return execution_context_var.get()
