"""Tests for tool decorators."""

import logging
import pytest

from linux_mcp_server.tools.decorators import log_tool_output


class TestLogToolOutput:
    """Test the log_tool_output decorator."""
    
    @pytest.fixture
    def logger_caplog(self, caplog):
        """Fixture to capture logs at DEBUG level."""
        caplog.set_level(logging.DEBUG)
        return caplog
    
    def test_decorator_logs_async_function_output(self, logger_caplog):
        """Test that decorator logs output from async functions."""
        
        @log_tool_output
        async def sample_tool(param1: str, param2: int) -> str:
            return f"Result: {param1}-{param2}"
        
        # Call the decorated function
        import asyncio
        result = asyncio.run(sample_tool("test", 42))
        
        # Verify the function works correctly
        assert result == "Result: test-42"
        
        # Verify debug logging occurred (filter out asyncio internal logs)
        tool_records = [r for r in logger_caplog.records if "sample_tool" in r.message]
        assert len(tool_records) == 1
        record = tool_records[0]
        
        assert record.levelname == "DEBUG"
        assert "sample_tool returning content" in record.message
        # Check extra fields in __dict__
        assert record.__dict__["function"] == "sample_tool"
        assert record.__dict__["content"] == "Result: test-42"
        assert record.__dict__["param1"] == "test"
        assert record.__dict__["param2"] == 42
    
    def test_decorator_logs_sync_function_output(self, logger_caplog):
        """Test that decorator logs output from sync functions."""
        
        @log_tool_output
        def sample_sync_tool(value: str) -> str:
            return f"Sync result: {value}"
        
        # Call the decorated function
        result = sample_sync_tool("hello")
        
        # Verify the function works correctly
        assert result == "Sync result: hello"
        
        # Verify debug logging occurred
        assert len(logger_caplog.records) == 1
        record = logger_caplog.records[0]
        
        assert record.levelname == "DEBUG"
        assert "sample_sync_tool returning content" in record.message
        assert record.function == "sample_sync_tool"
        assert record.content == "Sync result: hello"
        assert record.value == "hello"
    
    def test_decorator_only_logs_at_debug_level(self, caplog):
        """Test that decorator only logs when DEBUG level is enabled."""
        # Set log level to INFO (above DEBUG)
        caplog.set_level(logging.INFO)
        
        @log_tool_output
        async def sample_tool() -> str:
            return "test output"
        
        # Call the function
        import asyncio
        result = asyncio.run(sample_tool())
        
        # Verify function works but no logs at INFO level
        assert result == "test output"
        assert len(caplog.records) == 0
    
    def test_decorator_handles_optional_params(self, logger_caplog):
        """Test that decorator handles optional parameters correctly."""
        
        @log_tool_output
        async def tool_with_optionals(
            required: str,
            optional1: str = None,
            optional2: int = None
        ) -> str:
            return "result"
        
        # Call with only required param
        import asyncio
        result = asyncio.run(tool_with_optionals("test"))
        
        assert result == "result"
        
        # Verify only non-None params are logged
        tool_records = [r for r in logger_caplog.records if "tool_with_optionals" in r.message]
        record = tool_records[0]
        assert record.__dict__["required"] == "test"
        # optional1 and optional2 should not be in the extra fields
        assert "optional1" not in record.__dict__
        assert "optional2" not in record.__dict__
    
    def test_decorator_logs_all_provided_params(self, logger_caplog):
        """Test that decorator logs all provided parameters."""
        
        @log_tool_output
        async def tool_with_many_params(
            host: str = None,
            username: str = None,
            port: int = None
        ) -> str:
            return "connected"
        
        # Call with all params
        import asyncio
        result = asyncio.run(
            tool_with_many_params(host="example.com", username="admin", port=22)
        )
        
        assert result == "connected"
        
        # Verify all params are logged
        tool_records = [r for r in logger_caplog.records if "tool_with_many_params" in r.message]
        record = tool_records[0]
        assert record.__dict__["host"] == "example.com"
        assert record.__dict__["username"] == "admin"
        assert record.__dict__["port"] == 22
        assert record.__dict__["content"] == "connected"
    
    def test_decorator_logs_full_content(self, logger_caplog):
        """Test that decorator logs full content without truncation."""
        
        @log_tool_output
        async def tool_returning_large_output() -> str:
            # Generate a large output (>1000 chars)
            return "x" * 2000
        
        # Call the function
        import asyncio
        result = asyncio.run(tool_returning_large_output())
        
        # Verify full content is logged without truncation
        tool_records = [r for r in logger_caplog.records if "tool_returning_large_output" in r.message]
        record = tool_records[0]
        assert len(record.__dict__["content"]) == 2000
        assert record.__dict__["content"] == "x" * 2000

