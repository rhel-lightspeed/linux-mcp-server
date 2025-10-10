"""Decorators for tool functions."""

import functools
import inspect
import logging
from typing import Any, Callable


def log_tool_output(func: Callable) -> Callable:
    """
    Decorator to log tool function outputs at DEBUG level.
    
    Automatically captures function name, arguments, and return value,
    logging them only when DEBUG level is enabled. This provides full
    visibility into what content is being returned to the LLM.
    
    Args:
        func: The tool function to decorate
        
    Returns:
        Wrapped function with logging
    """
    logger = logging.getLogger(func.__module__)
    
    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> str:
        result = await func(*args, **kwargs)
        
        # Only log if DEBUG is enabled
        if logger.isEnabledFor(logging.DEBUG):
            # Get function signature to map args to parameter names
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Build extra context with all parameters
            extra_context = {
                "function": func.__name__,
                "content": result
            }
            
            # Add all non-None parameters to the context
            for param_name, param_value in bound_args.arguments.items():
                if param_value is not None:
                    extra_context[param_name] = param_value
            
            logger.debug(
                f"{func.__name__} returning content",
                extra=extra_context
            )
        
        return result
    
    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> str:
        result = func(*args, **kwargs)
        
        # Only log if DEBUG is enabled
        if logger.isEnabledFor(logging.DEBUG):
            # Get function signature to map args to parameter names
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Build extra context with all parameters
            extra_context = {
                "function": func.__name__,
                "content": result
            }
            
            # Add all non-None parameters to the context
            for param_name, param_value in bound_args.arguments.items():
                if param_value is not None:
                    extra_context[param_name] = param_value
            
            logger.debug(
                f"{func.__name__} returning content",
                extra=extra_context
            )
        
        return result
    
    # Return appropriate wrapper based on whether function is async
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

