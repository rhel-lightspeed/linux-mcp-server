"""Log and audit tools."""

import asyncio
import os
import subprocess
from pathlib import Path


async def get_journal_logs(unit: str = None, priority: str = None, 
                          since: str = None, lines: int = 100) -> str:
    """Get systemd journal logs."""
    try:
        cmd = ["journalctl", "-n", str(lines), "--no-pager"]
        
        if unit:
            cmd.extend(["-u", unit])
        
        if priority:
            cmd.extend(["-p", priority])
        
        if since:
            cmd.extend(["--since", since])
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            error_msg = stderr.decode()
            return f"Error reading journal logs: {error_msg}"
        
        output = stdout.decode()
        
        if not output or output.strip() == "":
            return "No journal entries found matching the criteria."
        
        # Build filter description
        filters = []
        if unit:
            filters.append(f"unit={unit}")
        if priority:
            filters.append(f"priority={priority}")
        if since:
            filters.append(f"since={since}")
        
        filter_desc = ", ".join(filters) if filters else "no filters"
        
        result = [f"=== Journal Logs (last {lines} entries, {filter_desc}) ===\n"]
        result.append(output)
        
        return "\n".join(result)
    except FileNotFoundError:
        return "Error: journalctl command not found. This tool requires systemd."
    except Exception as e:
        return f"Error reading journal logs: {str(e)}"


async def get_audit_logs(lines: int = 100) -> str:
    """Get audit logs."""
    audit_log_path = "/var/log/audit/audit.log"
    
    try:
        if not os.path.exists(audit_log_path):
            return f"Audit log file not found at {audit_log_path}. Audit logging may not be enabled."
        
        # Use tail to read last N lines
        proc = await asyncio.create_subprocess_exec(
            "tail", "-n", str(lines), audit_log_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            error_msg = stderr.decode()
            if "Permission denied" in error_msg:
                return f"Permission denied reading audit logs. This tool requires elevated privileges (root) to read {audit_log_path}."
            return f"Error reading audit logs: {error_msg}"
        
        output = stdout.decode()
        
        if not output or output.strip() == "":
            return "No audit log entries found."
        
        result = [f"=== Audit Logs (last {lines} entries) ===\n"]
        result.append(output)
        
        return "\n".join(result)
    except FileNotFoundError:
        return "Error: tail command not found."
    except Exception as e:
        return f"Error reading audit logs: {str(e)}"


async def read_log_file(log_path: str, lines: int = 100) -> str:
    """Read a specific log file."""
    try:
        # Get allowed log paths from environment variable
        allowed_paths_env = os.getenv("LINUX_MCP_ALLOWED_LOG_PATHS", "")
        
        if not allowed_paths_env:
            return (
                "No log files are allowed. Set LINUX_MCP_ALLOWED_LOG_PATHS environment variable "
                "with comma-separated list of allowed log file paths."
            )
        
        allowed_paths = [p.strip() for p in allowed_paths_env.split(",") if p.strip()]
        
        # Resolve the requested path
        try:
            requested_path = Path(log_path).resolve()
        except Exception:
            return f"Invalid log file path: {log_path}"
        
        # Check if the requested path is in the allowed list
        is_allowed = False
        for allowed_path in allowed_paths:
            try:
                allowed_resolved = Path(allowed_path).resolve()
                if requested_path == allowed_resolved:
                    is_allowed = True
                    break
            except Exception:
                continue
        
        if not is_allowed:
            return (
                f"Access to log file '{log_path}' is not allowed.\n"
                f"Allowed log files: {', '.join(allowed_paths)}"
            )
        
        # Check if file exists
        if not requested_path.exists():
            return f"Log file not found: {log_path}"
        
        if not requested_path.is_file():
            return f"Path is not a file: {log_path}"
        
        # Read the file using tail
        proc = await asyncio.create_subprocess_exec(
            "tail", "-n", str(lines), str(requested_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            error_msg = stderr.decode()
            if "Permission denied" in error_msg:
                return f"Permission denied reading log file: {log_path}"
            return f"Error reading log file: {error_msg}"
        
        output = stdout.decode()
        
        if not output or output.strip() == "":
            return f"Log file is empty: {log_path}"
        
        result = [f"=== Log File: {log_path} (last {lines} lines) ===\n"]
        result.append(output)
        
        return "\n".join(result)
    except FileNotFoundError:
        return "Error: tail command not found."
    except Exception as e:
        return f"Error reading log file: {str(e)}"

