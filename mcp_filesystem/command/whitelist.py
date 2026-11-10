"""Command whitelist management for secure command execution."""

import shlex
from typing import Dict, List, Optional, Set, Tuple

from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class CommandWhitelist:
    """Manages command whitelist and validation."""

    # Default allowed commands
    DEFAULT_WHITELIST: Set[str] = {
        # Python
        "python", "python3",
        
        # Node.js
        "node",
        
        # System tools (read-only/safe)
        "ls", "cat", "head", "tail", "grep", "find", "wc",
        "pwd", "echo", "date", "env", "which", "file",
        "sort", "uniq", "diff", "tr", "cut", "awk", "sed",
        
        # Serve (for frontend preview)
        "serve",
    }

    # Commands that have blocked subcommands
    DEFAULT_BLOCKED_SUBCOMMANDS: Dict[str, Set[str]] = {
        "pip": {"install", "uninstall", "download"},
        "pip3": {"install", "uninstall", "download"},
        "npm": {"install", "uninstall", "i", "ci", "add", "remove"},
        "npx": {"install"},
        "yarn": {"add", "remove", "install"},
        "pnpm": {"add", "remove", "install", "i"},
    }

    def __init__(
        self,
        whitelist: Optional[Set[str]] = None,
        blocked_subcommands: Optional[Dict[str, Set[str]]] = None,
    ):
        """Initialize command whitelist.

        Args:
            whitelist: Set of allowed commands. If None, uses DEFAULT_WHITELIST.
            blocked_subcommands: Dict mapping commands to blocked subcommands.
        """
        self.whitelist = whitelist if whitelist is not None else self.DEFAULT_WHITELIST.copy()
        self.blocked_subcommands = (
            blocked_subcommands
            if blocked_subcommands is not None
            else self.DEFAULT_BLOCKED_SUBCOMMANDS.copy()
        )

    def is_command_allowed(self, command: str) -> Tuple[bool, Optional[str]]:
        """Check if a command is allowed.

        Args:
            command: The full command string to check.

        Returns:
            Tuple of (is_allowed, error_message).
            If allowed, error_message is None.
        """
        try:
            # Parse the command
            parts = shlex.split(command)
            if not parts:
                return False, "Empty command"

            # Get the base command (first word, without path)
            base_cmd = parts[0].split("/")[-1]

            # Check if command is in whitelist
            if base_cmd not in self.whitelist:
                return False, f"Command '{base_cmd}' is not allowed. Allowed commands: {', '.join(sorted(self.whitelist))}"

            # Check for blocked subcommands
            if base_cmd in self.blocked_subcommands and len(parts) > 1:
                blocked = self.blocked_subcommands[base_cmd]
                for i, arg in enumerate(parts[1:], 1):
                    # Skip flags (starting with -)
                    if arg.startswith("-"):
                        continue
                    # Check if this is a blocked subcommand
                    if arg in blocked:
                        return False, f"Subcommand '{arg}' is not allowed for '{base_cmd}'. All dependencies are pre-installed."

            return True, None

        except ValueError as e:
            return False, f"Failed to parse command: {e}"

    def add_to_whitelist(self, command: str):
        """Add a command to the whitelist.

        Args:
            command: Command name to add.
        """
        self.whitelist.add(command)
        logger.info(f"Added command to whitelist: {command}")

    def remove_from_whitelist(self, command: str):
        """Remove a command from the whitelist.

        Args:
            command: Command name to remove.
        """
        self.whitelist.discard(command)
        logger.info(f"Removed command from whitelist: {command}")

    def block_subcommand(self, command: str, subcommand: str):
        """Block a subcommand for a specific command.

        Args:
            command: Base command.
            subcommand: Subcommand to block.
        """
        if command not in self.blocked_subcommands:
            self.blocked_subcommands[command] = set()
        self.blocked_subcommands[command].add(subcommand)
        logger.info(f"Blocked subcommand '{subcommand}' for '{command}'")

    def get_whitelist(self) -> List[str]:
        """Get the current whitelist as a sorted list.

        Returns:
            Sorted list of allowed commands.
        """
        return sorted(self.whitelist)


