"""Command executor with sandboxing, resource limits, and network isolation."""

import asyncio
import os
import resource
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp.utilities.logging import get_logger

from .whitelist import CommandWhitelist

logger = get_logger(__name__)


@dataclass
class ProcessLimits:
    """Process resource limits configuration."""

    # Memory limit in MB per process
    max_memory_mb: int = 512

    # CPU time limit in seconds
    max_cpu_seconds: int = 60

    # Maximum file size in MB that can be created
    max_file_size_mb: int = 100

    # Maximum number of child processes
    max_processes: int = 32

    # Maximum number of open files
    max_open_files: int = 256

    @property
    def max_memory_bytes(self) -> int:
        return self.max_memory_mb * 1024 * 1024

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@dataclass
class CommandResult:
    """Result of command execution."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    timed_out: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "execution_time": self.execution_time,
            "timed_out": self.timed_out,
            "error": self.error,
        }


class CommandExecutor:
    """Executes commands with security restrictions."""

    def __init__(
        self,
        workspace_path: Path,
        whitelist: Optional[CommandWhitelist] = None,
        limits: Optional[ProcessLimits] = None,
        network_isolated: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize command executor.

        Args:
            workspace_path: The workspace directory for command execution.
            whitelist: Command whitelist. If None, uses default.
            limits: Process resource limits. If None, uses default.
            network_isolated: Whether to isolate network access.
            config: Additional configuration from config.json.
        """
        self.workspace_path = workspace_path
        self.whitelist = whitelist or CommandWhitelist()
        self.limits = limits or ProcessLimits()
        self.network_isolated = network_isolated
        self.config = config or {}

        # Override limits from config if provided
        limits_config = self.config.get("limits", {})
        if limits_config:
            if "max_memory_mb" in limits_config:
                self.limits.max_memory_mb = int(limits_config["max_memory_mb"])
            if "max_cpu_seconds" in limits_config:
                self.limits.max_cpu_seconds = int(limits_config["max_cpu_seconds"])
            if "max_file_size_mb" in limits_config:
                self.limits.max_file_size_mb = int(limits_config["max_file_size_mb"])
            if "max_processes" in limits_config:
                self.limits.max_processes = int(limits_config["max_processes"])
            if "timeout_seconds" in limits_config:
                self.default_timeout = int(limits_config["timeout_seconds"])
            else:
                self.default_timeout = 120

        # Network isolation setting from config
        if "network_isolated" in self.config:
            self.network_isolated = bool(self.config["network_isolated"])

        # Check if unshare is available and has required permissions
        if self.network_isolated:
            self.network_isolated = self._check_unshare_available()

    def _check_unshare_available(self) -> bool:
        """Check if unshare is available and has required permissions.
        
        Returns:
            True if unshare can be used, False otherwise.
        """
        if sys.platform != "linux":
            logger.warning("Network isolation is only supported on Linux, disabling it")
            return False
        
        # Check if unshare command exists
        if not shutil.which("unshare"):
            logger.warning("unshare command not found, disabling network isolation")
            return False
        
        # Try to test unshare with a simple command
        # This will fail if we don't have permissions
        try:
            result = subprocess.run(
                ["unshare", "--net", "--map-root-user", "--", "true"],
                capture_output=True,
                timeout=2,
            )
            if result.returncode == 0:
                return True
            else:
                logger.warning(
                    f"unshare test failed (exit code {result.returncode}), "
                    "disabling network isolation. Error: "
                    f"{result.stderr.decode('utf-8', errors='replace')[:200]}"
                )
                return False
        except subprocess.TimeoutExpired:
            logger.warning("unshare test timed out, disabling network isolation")
            return False
        except Exception as e:
            logger.warning(
                f"unshare test failed with exception: {e}, "
                "disabling network isolation"
            )
            return False

    def _validate_command_paths(self, command: str, cwd: Path) -> Optional[str]:
        """Validate that all paths in command arguments are within workspace.
        
        Args:
            command: The command string to validate
            cwd: The current working directory (must be within workspace)
            
        Returns:
            Error message if validation fails, None otherwise
        """
        try:
            import shlex
            parts = shlex.split(command)
            if len(parts) <= 1:
                return None  # No arguments to validate
            
            workspace_resolved = self.workspace_path.resolve()
            cwd_resolved = cwd.resolve()
            
            # Commands that typically take path arguments
            path_commands = {"find", "file", "cat", "head", "tail", "grep", "ls", "wc", "diff"}
            
            base_cmd = parts[0].split("/")[-1]
            if base_cmd not in path_commands:
                # For other commands, we still check for obvious path traversal attempts
                # but allow them to pass (they might not be file operations)
                for arg in parts[1:]:
                    if self._is_path_traversal_attempt(arg, cwd_resolved, workspace_resolved):
                        return f"Path traversal attempt detected in command argument: {arg}"
                return None
            
            # For path commands, validate all arguments that look like paths
            i = 1
            while i < len(parts):
                arg = parts[i]
                
                # Skip flags (starting with -)
                if arg.startswith("-"):
                    i += 1
                    # Some flags take values (e.g., -name "pattern")
                    if i < len(parts) and not parts[i].startswith("-"):
                        i += 1
                    continue
                
                # Check if argument looks like a path
                if self._is_path_traversal_attempt(arg, cwd_resolved, workspace_resolved):
                    return f"Path traversal attempt detected: {arg} would access files outside workspace"
                
                i += 1
            
            return None
            
        except Exception as e:
            logger.warning(f"Error validating command paths: {e}")
            # Don't block on validation errors, but log them
            return None
    
    def _is_path_traversal_attempt(self, arg: str, cwd: Path, workspace: Path) -> bool:
        """Check if an argument is a path traversal attempt.
        
        Args:
            arg: Command argument to check
            cwd: Current working directory
            workspace: Workspace root directory
            
        Returns:
            True if this looks like a path traversal attempt
        """
        # Skip non-path arguments
        if not arg or arg.startswith("-"):
            return False
        
        # Check for obvious path traversal patterns
        if ".." in arg:
            try:
                # Resolve the path relative to cwd
                test_path = (cwd / arg).resolve()
                # Check if it's still within workspace
                if not str(test_path).startswith(str(workspace)):
                    return True
            except (ValueError, OSError):
                # If we can't resolve it, it might be malicious
                return True
        
        # Check for absolute paths outside workspace
        if arg.startswith("/"):
            try:
                test_path = Path(arg).resolve()
                if not str(test_path).startswith(str(workspace)):
                    return True
            except (ValueError, OSError):
                return True
        
        return False

    def _set_process_limits(self):
        """Set resource limits for the child process.

        This is called as preexec_fn in subprocess.
        """
        try:
            # Memory limit (virtual memory / address space)
            resource.setrlimit(
                resource.RLIMIT_AS,
                (self.limits.max_memory_bytes, self.limits.max_memory_bytes),
            )

            # CPU time limit
            resource.setrlimit(
                resource.RLIMIT_CPU,
                (self.limits.max_cpu_seconds, self.limits.max_cpu_seconds),
            )

            # File size limit
            resource.setrlimit(
                resource.RLIMIT_FSIZE,
                (self.limits.max_file_size_bytes, self.limits.max_file_size_bytes),
            )

            # Number of processes limit
            resource.setrlimit(
                resource.RLIMIT_NPROC,
                (self.limits.max_processes, self.limits.max_processes),
            )

            # Open files limit
            resource.setrlimit(
                resource.RLIMIT_NOFILE,
                (self.limits.max_open_files, self.limits.max_open_files),
            )

        except (ValueError, resource.error) as e:
            # Log but don't fail - some limits might not be settable
            logger.warning(f"Failed to set some resource limits: {e}")

    def _get_sandboxed_env(self) -> Dict[str, str]:
        """Get environment variables for sandboxed execution.

        Returns:
            Environment dictionary with restricted settings.
        """
        env = os.environ.copy()

        # Set working directory related vars
        env["HOME"] = str(self.workspace_path)
        env["PWD"] = str(self.workspace_path)

        # Python settings
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONHASHSEED"] = "random"
        
        # exec / sandbox safe initialization
        env["OPENBLAS_NUM_THREADS"] = "1"
        env["OMP_NUM_THREADS"] = "1"
        env["MKL_NUM_THREADS"] = "1"

        # Disable pip/npm from installing (even if command gets through)
        env["PIP_NO_INPUT"] = "1"
        env["npm_config_ignore_scripts"] = "true"

        # Matplotlib backend for headless operation
        env["MPLBACKEND"] = "Agg"

        # Limit Node.js memory
        env["NODE_OPTIONS"] = f"--max-old-space-size={self.limits.max_memory_mb}"

        return env

    def _wrap_command_for_isolation(self, command: str) -> str:
        """Wrap command for network isolation if enabled.

        Args:
            command: Original command.

        Returns:
            Wrapped command with network isolation.
        """
        if not self.network_isolated:
            return command

        # Check if unshare is available (Linux only)
        if sys.platform != "linux":
            logger.warning("Network isolation is only supported on Linux")
            return command

        # Use unshare to create a new network namespace
        # --net: new network namespace (no network access)
        # --map-root-user: map root user for unprivileged unshare
        # Note: This requires user namespaces to be enabled
        return f"unshare --net --map-root-user -- {command}"

    async def execute(
        self,
        command: str,
        working_dir: str = "/",
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> CommandResult:
        """Execute a command in the sandbox.

        Args:
            command: Command to execute.
            working_dir: Working directory relative to workspace root.
            timeout: Timeout in seconds. If None, uses default.
            env: Additional environment variables.

        Returns:
            CommandResult with execution details.
        """
        import time

        start_time = time.time()

        # Validate command against whitelist
        allowed, error_msg = self.whitelist.is_command_allowed(command)
        if not allowed:
            return CommandResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                execution_time=0,
                error=error_msg,
            )

        # Resolve working directory
        # Handle None case (use workspace root)
        if working_dir is None or working_dir == "":
            working_dir = "/"

        if working_dir.startswith("/"):
            working_dir = working_dir[1:]

        if working_dir and working_dir != ".":
            cwd = self.workspace_path / working_dir
        else:
            cwd = self.workspace_path

        # Ensure working directory exists and is within workspace
        if not cwd.exists():
            return CommandResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                execution_time=0,
                error=f"Working directory does not exist: /{working_dir}",
            )
        
        # Verify working directory is within workspace (prevent path traversal)
        try:
            cwd_resolved = cwd.resolve()
            workspace_resolved = self.workspace_path.resolve()
            if not str(cwd_resolved).startswith(str(workspace_resolved)):
                logger.warning(
                    f"Path traversal attempt detected: {cwd_resolved} outside {workspace_resolved}"
                )
                return CommandResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="",
                    execution_time=0,
                    error="Working directory outside workspace is not allowed",
                )
        except Exception as e:
            logger.error(f"Error validating working directory: {e}")
            return CommandResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                execution_time=0,
                error="Failed to validate working directory",
            )

        # Validate paths in command arguments to prevent path traversal
        path_validation_error = self._validate_command_paths(command, cwd)
        if path_validation_error:
            return CommandResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                execution_time=0,
                error=path_validation_error,
            )

        # Prepare environment
        exec_env = self._get_sandboxed_env()
        if env:
            exec_env.update(env)

        # Apply timeout
        effective_timeout = timeout if timeout is not None else self.default_timeout
        effective_timeout = min(effective_timeout, 300)  # Max 5 minutes

        # Wrap command for network isolation
        wrapped_command = self._wrap_command_for_isolation(command)

        try:
            # Create subprocess with resource limits
            proc = await asyncio.create_subprocess_shell(
                wrapped_command,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=exec_env,
                preexec_fn=self._set_process_limits if sys.platform != "win32" else None,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError:
                # Kill the process and all children
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass

                return CommandResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="",
                    execution_time=time.time() - start_time,
                    timed_out=True,
                    error=f"Command timed out after {effective_timeout} seconds",
                )

            execution_time = time.time() - start_time

            return CommandResult(
                success=proc.returncode == 0,
                exit_code=proc.returncode or 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                execution_time=execution_time,
            )

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return CommandResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                execution_time=time.time() - start_time,
                error=f"Execution failed: {type(e).__name__}",
            )

    def format_result(self, result: CommandResult) -> str:
        """Format command result for display.

        Args:
            result: Command execution result.

        Returns:
            Formatted string for display.
        """
        lines = []

        if result.error:
            lines.append(f"❌ Error: {result.error}")
            return "\n".join(lines)

        if result.timed_out:
            lines.append(f"⏰ Command timed out after {result.execution_time:.1f}s")
            return "\n".join(lines)

        if result.success:
            lines.append(f"✅ Command completed successfully (exit code: {result.exit_code})")
        else:
            lines.append(f"❌ Command failed (exit code: {result.exit_code})")

        lines.append(f"⏱️ Execution time: {result.execution_time:.3f}s")
        lines.append("")

        if result.stdout.strip():
            lines.append("**stdout:**")
            lines.append("```")
            # Truncate if too long
            stdout = result.stdout.strip()
            if len(stdout) > 10000:
                stdout = stdout[:10000] + "\n... (truncated)"
            lines.append(stdout)
            lines.append("```")

        if result.stderr.strip():
            lines.append("")
            lines.append("**stderr:**")
            lines.append("```")
            stderr = result.stderr.strip()
            if len(stderr) > 5000:
                stderr = stderr[:5000] + "\n... (truncated)"
            lines.append(stderr)
            lines.append("```")

        return "\n".join(lines)


