"""MCP Filesystem Server.

A Model Context Protocol server that provides secure access to the filesystem.
"""

__version__ = "0.1.0"

try:
    # Importing server (and FastMCP) is optional for library-style imports.
    # Unit tests and some environments may not have the runtime dependencies installed.
    from .server import mcp  # type: ignore
except ModuleNotFoundError:
    mcp = None  # type: ignore


def main() -> None:
    """Main entry point for the package."""
    if mcp is None:
        raise RuntimeError(
            "MCP server runtime dependencies are not installed (failed to import 'mcp_filesystem.server'). "
            "Install the full package dependencies to run the server."
        )
    try:
        mcp.run()
    except KeyboardInterrupt:
        import sys

        print("\nShutting down...", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        import sys

        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


__all__ = ["mcp", "main"]
