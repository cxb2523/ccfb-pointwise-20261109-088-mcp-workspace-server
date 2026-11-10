"""Security module for MCP filesystem server.

This module handles path validation, normalization, and security checks
to ensure that all file operations are restricted to allowed directories.
"""

import platform
import re
import logging
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple, Union

import anyio
try:
    # Prefer MCP's structured logger when available
    from mcp.server.fastmcp.utilities.logging import get_logger  # type: ignore
except ModuleNotFoundError:
    # Fall back to stdlib logging when MCP runtime isn't installed (e.g., unit tests)
    def get_logger(name: str) -> logging.Logger:  # type: ignore
        return logging.getLogger(name)

logger = get_logger(__name__)

# Force INFO level logging for debugging
logger.setLevel(logging.INFO)


class PathValidator:
    """Security class for validating and normalizing file paths.
    
    Supports virtual root mode where a single allowed directory is presented
    as "/" to the client, hiding the real physical path.
    """

    def __init__(
        self,
        allowed_dirs: List[Union[str, Path]],
        virtual_root: Optional[Path] = None,
    ):
        """Initialize with a list of allowed directories.

        Args:
            allowed_dirs: List of directories that are allowed for file operations.
                          Paths are normalized to absolute paths.
            virtual_root: If set, this directory is presented as "/" to clients.
                          All paths are translated relative to this root.
                          Typically used for session isolation.
        """
        self.allowed_dirs: Set[str] = set()
        self.virtual_root: Optional[Path] = None
        
        # Set up virtual root if provided
        if virtual_root is not None:
            self.virtual_root = Path(virtual_root).expanduser().resolve()
            logger.info(f"Virtual root enabled: {self.virtual_root}")

        # Normalize and validate allowed directories
        for directory in allowed_dirs:
            try:
                # Convert to Path object and resolve to absolute path
                abs_path = Path(directory).expanduser().resolve()

                # Check if it's actually a directory
                if not abs_path.is_dir():
                    logger.warning(
                        f"Allowed path is not a directory: {abs_path}",
                        extra={"path": str(abs_path)},
                    )
                    continue

                # Add to allowed set in normalized form
                self.allowed_dirs.add(self._normalize_case(str(abs_path)))
                logger.debug(f"Added allowed directory: {abs_path}")

            except (PermissionError, FileNotFoundError) as e:
                logger.error(
                    f"Error accessing allowed directory {directory}: {e}",
                    extra={"error": str(e), "path": str(directory)},
                )

        if not self.allowed_dirs:
            logger.warning("No valid allowed directories provided!")

    def _normalize_case(self, path: str) -> str:
        """Normalize path case based on platform.

        On Windows, convert to lowercase for case-insensitive comparison.
        On other platforms, keep the original case.

        Args:
            path: Path to normalize

        Returns:
            Normalized path
        """
        if platform.system() == "Windows":
            return path.lower()
        return path

    async def validate_path(
        self, requested_path: str
    ) -> Tuple[Path, bool]:
        """Validate if a path is within allowed directories.

        If virtual_root is set, the requested_path is treated as a virtual path
        and translated to a real path before validation.

        IMPORTANT: This method ONLY accepts virtual path strings (str).
        Do NOT pass Path objects - this will cause path duplication errors.
        Always use virtual path strings like "/file.txt" or "folder/file.txt".

        Args:
            requested_path: Virtual path string to validate (NOT a Path object)

        Returns:
            Tuple of (resolved_real_path, is_allowed)

        Raises:
            TypeError: If requested_path is not a string
            ValueError: If path is invalid or outside allowed directories
        """
        # Type check: enforce str only
        if not isinstance(requested_path, str):
            raise TypeError(
                f"validate_path expects str (virtual path string), got {type(requested_path).__name__}. "
                f"Do not pass Path objects - use virtual path strings like '/file.txt'. "
                f"Got value: {requested_path}"
            )

        # URL decode the path to handle spaces and special characters.
        #
        # NOTE: We must be careful here:
        # - Some clients incorrectly *store* encoded names on disk (e.g. "new%205.json")
        # - Some clients correctly send encoded paths to refer to a real-space name (e.g. "new%205.json" -> "new 5.json")
        #
        # To be compatible with both, we compute both raw and decoded candidates.
        # If one exists on disk, we prefer the existing one; otherwise default to decoded.
        from urllib.parse import unquote, quote
        requested_path_raw = requested_path
        requested_path_decoded = unquote(requested_path)
        # Legacy compatibility: if a file was mistakenly persisted with URL-encoded characters
        # (e.g. "new%205.json"), a user may still pass the decoded form ("new 5.json").
        # We generate an encoded candidate and prefer it only if it exists.
        requested_path_encoded: Optional[str] = None
        if requested_path_raw == requested_path_decoded:
            encoded = quote(requested_path_raw, safe="/")
            if encoded != requested_path_raw:
                requested_path_encoded = encoded
        
        try:
            logger.info(
                "validate_path: INPUT requested_path_raw=%s, requested_path_decoded=%s, virtual_root=%s",
                requested_path_raw,
                requested_path_decoded,
                self.virtual_root,
            )

            def _to_abs_path(candidate_virtual_path: str) -> Path:
                """Convert a virtual/real candidate path string into an absolute Path following existing rules."""
                if self.virtual_root is not None:
                    real_path = self.virtual_to_real(candidate_virtual_path)
                    try:
                        return real_path.resolve()
                    except (OSError, ValueError):
                        abs_path_local = real_path.absolute()
                        if ".." in str(abs_path_local):
                            try:
                                parent_resolved = abs_path_local.parent.resolve()
                                abs_path_local = parent_resolved / abs_path_local.name
                            except (OSError, ValueError):
                                logger.warning(f"Path contains .. and cannot be resolved: {abs_path_local}")
                                raise ValueError(
                                    "Path traversal not allowed: path contains '..' and cannot be safely resolved"
                                )
                        return abs_path_local

                # No virtual root
                try:
                    return Path(candidate_virtual_path).resolve()
                except (OSError, ValueError):
                    abs_path_local = Path(candidate_virtual_path).absolute()
                    if ".." in str(abs_path_local):
                        try:
                            parent_resolved = abs_path_local.parent.resolve()
                            abs_path_local = parent_resolved / abs_path_local.name
                        except (OSError, ValueError):
                            logger.warning(f"Path contains .. and cannot be resolved: {abs_path_local}")
                            raise ValueError(
                                "Path traversal not allowed: path contains '..' and cannot be safely resolved"
                            )
                    return abs_path_local

            chosen_virtual_path = requested_path_decoded
            chosen_abs_path: Optional[Path] = None
            raw_abs_path: Optional[Path] = None
            decoded_abs_path: Optional[Path] = None
            encoded_abs_path: Optional[Path] = None

            # Try compute both; if decoding introduces traversal, it will raise and we fail fast (safer).
            decoded_abs_path = _to_abs_path(requested_path_decoded)
            if requested_path_raw != requested_path_decoded:
                raw_abs_path = _to_abs_path(requested_path_raw)
            if requested_path_encoded:
                encoded_abs_path = _to_abs_path(requested_path_encoded)

            raw_exists = raw_abs_path.exists() if raw_abs_path is not None else False
            decoded_exists = decoded_abs_path.exists()
            encoded_exists = encoded_abs_path.exists() if encoded_abs_path is not None else False

            # Prefer the path that actually exists.
            # - decoded wins when present (the "correct" representation)
            # - raw wins for truly-encoded-on-disk legacy names when caller passes encoded
            # - encoded wins for legacy names when caller passes decoded
            if decoded_exists:
                chosen_virtual_path = requested_path_decoded
                chosen_abs_path = decoded_abs_path
            elif raw_exists:
                chosen_virtual_path = requested_path_raw
                chosen_abs_path = raw_abs_path
            elif encoded_exists and requested_path_encoded:
                chosen_virtual_path = requested_path_encoded
                chosen_abs_path = encoded_abs_path
            else:
                # For creation/nonexistent targets, default to decoded so new files are created with real characters.
                chosen_virtual_path = requested_path_decoded
                chosen_abs_path = decoded_abs_path

            abs_path = chosen_abs_path
            requested_path = chosen_virtual_path
            logger.info(
                "validate_path: Chosen requested_path=%s, abs_path=%s (raw_exists=%s, decoded_exists=%s, encoded_exists=%s)",
                requested_path,
                abs_path,
                (raw_abs_path.exists() if raw_abs_path is not None else None),
                (decoded_abs_path.exists() if decoded_abs_path is not None else None),
                (encoded_abs_path.exists() if encoded_abs_path is not None else None),
            )

            normalized = self._normalize_case(str(abs_path))

            # Check if path is within allowed directories
            for allowed_dir in self.allowed_dirs:
                if normalized.startswith(allowed_dir):
                    logger.info(f"validate_path: Path ALLOWED, returning {abs_path}")
                    return abs_path, True

            # Handle case where path doesn't exist yet but parent directory does
            if not abs_path.exists():
                parent_path = abs_path.parent
                try:
                    parent_abs = parent_path.resolve()
                    parent_normalized = self._normalize_case(str(parent_abs))

                    for allowed_dir in self.allowed_dirs:
                        if parent_normalized.startswith(allowed_dir):
                            return abs_path, True
                except (FileNotFoundError, PermissionError):
                    pass

            logger.warning(
                f"Access denied - path outside allowed directories: {abs_path}",
                extra={"path": str(abs_path)},
            )
            return abs_path, False

        except (FileNotFoundError, PermissionError) as e:
            logger.error(
                f"Error validating path: {e}",
                extra={"error": str(e), "path": str(requested_path)},
            )
            return Path(requested_path), False

    async def resolve_symlinks(self, path: Path) -> Tuple[Path, bool]:
        """Safely resolve symlinks to ensure target is within allowed directories.

        Args:
            path: Path that might contain symlinks

        Returns:
            Tuple of (resolved_path, is_allowed)
        """
        try:
            # Try to resolve symlinks
            real_path = await anyio.to_thread.run_sync(Path.resolve, path)
            normalized = self._normalize_case(str(real_path))

            # Check if resolved path is within allowed directories
            for allowed_dir in self.allowed_dirs:
                if normalized.startswith(allowed_dir):
                    return real_path, True

            logger.warning(
                f"Access denied - symlink target outside allowed directories: {real_path}",
                extra={"path": str(real_path), "original": str(path)},
            )
            return real_path, False

        except (FileNotFoundError, PermissionError) as e:
            logger.error(
                f"Error resolving symlinks: {e}",
                extra={"error": str(e), "path": str(path)},
            )
            return path, False

    def get_allowed_dirs(self) -> List[str]:
        """Get the list of allowed directories.
        
        If virtual_root is enabled, returns ["/"] instead of actual paths.

        Returns:
            List of allowed directory paths (virtual if virtual_root is set)
        """
        if self.virtual_root is not None:
            return ["/"]
        return sorted(list(self.allowed_dirs))
    
    def virtual_to_real(self, virtual_path: Union[str, Path]) -> Path:
        """Convert a virtual path to a real filesystem path.

        If virtual_root is not set, returns the path as-is.

        Args:
            virtual_path: Path as seen by the client (e.g., "/todo.txt" or "todo.txt")

        Returns:
            Real filesystem path
        """
        if self.virtual_root is None:
            return Path(virtual_path)

        # Normalize the virtual path
        vpath = str(virtual_path)

        logger.info(f"virtual_to_real: INPUT virtual_path={virtual_path}, virtual_root={self.virtual_root}")

        # Handle absolute virtual paths (starting with /)
        if vpath.startswith("/"):
            vpath = vpath[1:]  # Remove leading /

        # Handle empty path (root)
        if not vpath or vpath == ".":
            result = self.virtual_root
            logger.info(f"virtual_to_real: OUTPUT (root) = {result}")
            return result

        # Join with virtual root
        result = self.virtual_root / vpath
        logger.info(f"virtual_to_real: OUTPUT = {result}")
        return result
    
    def real_to_virtual(self, real_path: Union[str, Path], strict: bool = True) -> str:
        """Convert a real filesystem path to a virtual path.

        If virtual_root is not set, returns only the filename to avoid leaking paths.

        Args:
            real_path: Real filesystem path
            strict: If True, raises ValueError when path is not under virtual_root.
                    If False, returns a sanitized placeholder path.

        Returns:
            Virtual path as seen by the client

        Raises:
            ValueError: If strict=True and path is not under virtual_root
        """
        if self.virtual_root is None:
            # WARNING: virtual_root is None - return only filename to avoid path leakage
            logger.warning(
                f"real_to_virtual called with virtual_root=None, returning filename only: {real_path}"
            )
            # Return only the filename as a relative path
            return "/" + Path(real_path).name

        # Use absolute() instead of resolve() to avoid issues with non-existent files
        # resolve() may fail or behave unexpectedly if the file doesn't exist yet
        real = Path(real_path).absolute()
        virtual_root_abs = self.virtual_root.absolute()

        logger.info(f"real_to_virtual: real_path={real_path}, real_abs={real}, virtual_root_abs={virtual_root_abs}")

        try:
            # Get relative path from virtual root
            relative = real.relative_to(virtual_root_abs)
            # Return as absolute virtual path
            result = "/" + str(relative)
            logger.info(f"real_to_virtual: SUCCESS - result={result}")
            return result
        except ValueError as e:
            # Path is not under virtual root - this is a security issue!
            # NEVER expose the real path to the client
            logger.error(
                f"SECURITY: Attempted to expose path outside virtual root: {real_path}, error: {e}",
                extra={"path": str(real_path), "virtual_root": str(self.virtual_root)},
            )
            if strict:
                raise ValueError(
                    "Path conversion failed: path is outside the allowed directory"
                )
            # Return a safe placeholder that doesn't expose any real path info
            return "/[path_not_available]"

    def is_path_allowed(self, path: Union[str, Path]) -> bool:
        """Quick check if a path is within allowed directories.

        Args:
            path: Path to check

        Returns:
            True if path is allowed, False otherwise
        """
        try:
            abs_path = Path(path).expanduser().resolve()
            normalized = self._normalize_case(str(abs_path))

            for allowed_dir in self.allowed_dirs:
                if normalized.startswith(allowed_dir):
                    return True

            return False
        except (FileNotFoundError, PermissionError):
            return False

    async def find_matching_files(
        self,
        root_path: Union[str, Path],
        pattern: str,
        recursive: bool = True,
        exclude_patterns: Optional[List[str]] = None,
    ) -> List[Path]:
        """Find files matching a pattern within allowed directories.

        Args:
            root_path: Starting directory for search
            pattern: Glob pattern to match against filenames
            recursive: Whether to search subdirectories
            exclude_patterns: Optional patterns to exclude

        Returns:
            List of matching file paths

        Raises:
            ValueError: If root_path is outside allowed directories
        """
        abs_path, allowed = await self.validate_path(root_path)
        if not allowed:
            raise ValueError(f"Search path outside allowed directories: {root_path}")

        if not abs_path.is_dir():
            raise ValueError(f"Search path is not a directory: {abs_path}")

        results = []
        exclude_regexes = []

        # Compile exclude patterns if provided
        if exclude_patterns:
            for exclude in exclude_patterns:
                try:
                    exclude_regexes.append(re.compile(exclude))
                except re.error:
                    logger.warning(f"Invalid exclude pattern: {exclude}")

        # Use glob for pattern matching
        glob_pattern = "**/" + pattern if recursive else pattern
        for matched_path in abs_path.glob(glob_pattern):
            # Skip if matched by exclude pattern
            path_str = str(matched_path)
            excluded = False
            for exclude_re in exclude_regexes:
                if exclude_re.search(path_str):
                    excluded = True
                    break

            if not excluded:
                # Verify path is still allowed (e.g., in case of symlinks)
                if self.is_path_allowed(matched_path):
                    results.append(matched_path)

        return results

    def sanitize_error(self, error: Exception, user_path: Optional[str] = None) -> str:
        """Sanitize error message to avoid exposing real filesystem paths.
        
        Args:
            error: The exception to sanitize
            user_path: The user-provided path (virtual path) to use in error message
            
        Returns:
            A sanitized error message that doesn't expose real paths
        """
        error_msg = str(error)
        
        # Remove real path references if virtual root is enabled
        if self.virtual_root:
            virtual_root_str = str(self.virtual_root)
            # Replace any occurrence of the real path with the virtual representation
            error_msg = error_msg.replace(virtual_root_str, "")
            # Also handle normalized variations
            error_msg = error_msg.replace(virtual_root_str.rstrip("/"), "")
            error_msg = error_msg.replace(virtual_root_str.rstrip("\\"), "")
        
        # Remove any allowed directory paths from error messages
        for allowed_dir in self.allowed_dirs:
            error_msg = error_msg.replace(allowed_dir, "")
            error_msg = error_msg.replace(allowed_dir.rstrip("/"), "")
            error_msg = error_msg.replace(allowed_dir.rstrip("\\"), "")
        
        # Clean up double slashes that might result from path removal
        error_msg = re.sub(r"/{2,}", "/", error_msg)
        error_msg = re.sub(r"\\{2,}", "\\", error_msg)
        
        # If user provided a path, use it for clearer messaging
        if user_path and "No such file or directory" in error_msg:
            return f"File not found: {user_path}"
        if user_path and "Permission denied" in error_msg:
            return f"Permission denied: {user_path}"
        if user_path and "Is a directory" in error_msg:
            return f"Is a directory: {user_path}"
        if user_path and "Not a directory" in error_msg:
            return f"Not a directory: {user_path}"
        
        return error_msg.strip()


def sanitize_error_simple(error: Exception, user_path: Optional[str] = None) -> str:
    """Simplified error sanitization without PathValidator context.
    
    Use this when you don't have access to the PathValidator instance.
    
    Args:
        error: The exception to sanitize
        user_path: The user-provided path to use in error message
        
    Returns:
        A sanitized error message
    """
    error_type = type(error).__name__
    
    if isinstance(error, FileNotFoundError):
        if user_path:
            return f"File not found: {user_path}"
        return "File not found"
    
    if isinstance(error, PermissionError):
        if user_path:
            return f"Permission denied: {user_path}"
        return "Permission denied"
    
    if isinstance(error, IsADirectoryError):
        if user_path:
            return f"Is a directory: {user_path}"
        return "Is a directory"
    
    if isinstance(error, NotADirectoryError):
        if user_path:
            return f"Not a directory: {user_path}"
        return "Not a directory"
    
    if isinstance(error, FileExistsError):
        if user_path:
            return f"File already exists: {user_path}"
        return "File already exists"
    
    # For other errors, return the error type without the message
    # to avoid leaking sensitive information
    return f"{error_type}: Operation failed"


class ResponseSanitizer:
    """Security tool to sanitize tool responses and prevent path leakage.
    
    This class provides methods to check and sanitize all tool responses,
    ensuring that no physical paths are leaked to clients.
    """
    
    # Default sensitive path patterns - these should NEVER appear in responses
    DEFAULT_SENSITIVE_PATTERNS: List[str] = [
        "user_data",      # Common user data directory pattern
        "/home/",         # Linux home directories
        "/root/",         # Root home directory
        "/var/",          # System directories
        "/tmp/",          # Temp directories
        "/etc/",          # Config directories
        "/app/",          # Application directories
        "C:\\Users\\",    # Windows user directories
        "C:\\Windows\\",  # Windows system directories
    ]
    
    def __init__(
        self,
        sensitive_patterns: Optional[List[str]] = None,
        additional_patterns: Optional[List[str]] = None,
    ):
        """Initialize the response sanitizer.
        
        Args:
            sensitive_patterns: Custom list of patterns to check (replaces defaults)
            additional_patterns: Additional patterns to add to defaults
        """
        if sensitive_patterns is not None:
            self._patterns = list(sensitive_patterns)
        else:
            self._patterns = list(self.DEFAULT_SENSITIVE_PATTERNS)
        
        if additional_patterns:
            self._patterns.extend(additional_patterns)
        
        # Compile regex patterns for efficient matching
        self._compiled_patterns: List[re.Pattern] = []
        for pattern in self._patterns:
            # Escape special regex characters and make case-insensitive
            escaped = re.escape(pattern)
            try:
                self._compiled_patterns.append(
                    re.compile(escaped, re.IGNORECASE)
                )
            except re.error as e:
                logger.warning(f"Invalid pattern '{pattern}': {e}")
    
    def check_for_sensitive_paths(self, value: Any, path: str = "") -> List[str]:
        """Check a value for sensitive path patterns.
        
        Args:
            value: The value to check (can be str, dict, list, or any type)
            path: The path to this value in the response structure (for logging)
            
        Returns:
            List of found sensitive patterns with their locations
        """
        violations: List[str] = []
        
        if isinstance(value, str):
            for i, pattern in enumerate(self._compiled_patterns):
                if pattern.search(value):
                    violations.append(
                        f"Pattern '{self._patterns[i]}' found at '{path}': {value[:100]}..."
                        if len(value) > 100 else
                        f"Pattern '{self._patterns[i]}' found at '{path}': {value}"
                    )
        
        elif isinstance(value, dict):
            for key, val in value.items():
                child_path = f"{path}.{key}" if path else key
                violations.extend(self.check_for_sensitive_paths(val, child_path))
        
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                child_path = f"{path}[{i}]"
                violations.extend(self.check_for_sensitive_paths(item, child_path))
        
        return violations
    
    def contains_sensitive_path(self, value: Any) -> bool:
        """Quick check if a value contains any sensitive path patterns.
        
        Args:
            value: The value to check
            
        Returns:
            True if any sensitive pattern is found
        """
        return len(self.check_for_sensitive_paths(value)) > 0
    
    def sanitize_response(
        self,
        response: Any,
        replacement: str = "[REDACTED]",
        raise_on_violation: bool = True,
    ) -> Any:
        """Sanitize a response by removing or replacing sensitive paths.
        
        Args:
            response: The response to sanitize
            replacement: String to replace sensitive values with
            raise_on_violation: If True, raise SecurityError on violation
            
        Returns:
            Sanitized response
            
        Raises:
            PathLeakageError: If raise_on_violation=True and sensitive path found
        """
        violations = self.check_for_sensitive_paths(response)
        
        if violations:
            logger.error(
                f"SECURITY: Path leakage detected in response: {violations}"
            )
            
            if raise_on_violation:
                raise PathLeakageError(
                    "Security violation: response contains sensitive path information",
                    violations=violations,
                )
            
            # If not raising, sanitize the response
            return self._sanitize_value(response, replacement)
        
        return response
    
    def _sanitize_value(self, value: Any, replacement: str) -> Any:
        """Recursively sanitize a value by replacing sensitive strings.
        
        Args:
            value: The value to sanitize
            replacement: String to replace sensitive values with
            
        Returns:
            Sanitized value
        """
        if isinstance(value, str):
            result = value
            for pattern in self._compiled_patterns:
                if pattern.search(result):
                    # Replace the entire string if it contains sensitive data
                    return replacement
            return result
        
        elif isinstance(value, dict):
            return {
                k: self._sanitize_value(v, replacement)
                for k, v in value.items()
            }
        
        elif isinstance(value, list):
            return [self._sanitize_value(item, replacement) for item in value]
        
        elif isinstance(value, tuple):
            return tuple(self._sanitize_value(item, replacement) for item in value)
        
        return value
    
    def add_pattern(self, pattern: str) -> None:
        """Add a new sensitive pattern to check.
        
        Args:
            pattern: The pattern string to add
        """
        if pattern not in self._patterns:
            self._patterns.append(pattern)
            try:
                self._compiled_patterns.append(
                    re.compile(re.escape(pattern), re.IGNORECASE)
                )
            except re.error as e:
                logger.warning(f"Invalid pattern '{pattern}': {e}")


class PathLeakageError(Exception):
    """Exception raised when a response contains sensitive path information."""
    
    def __init__(self, message: str, violations: Optional[List[str]] = None):
        super().__init__(message)
        self.violations = violations or []


# Global sanitizer instance - can be configured at startup
_global_sanitizer: Optional[ResponseSanitizer] = None


def get_response_sanitizer() -> ResponseSanitizer:
    """Get the global response sanitizer instance.
    
    Returns:
        The global ResponseSanitizer instance
    """
    global _global_sanitizer
    if _global_sanitizer is None:
        _global_sanitizer = ResponseSanitizer()
    return _global_sanitizer


def configure_response_sanitizer(
    sensitive_patterns: Optional[List[str]] = None,
    additional_patterns: Optional[List[str]] = None,
) -> ResponseSanitizer:
    """Configure the global response sanitizer.
    
    Args:
        sensitive_patterns: Custom list of patterns (replaces defaults)
        additional_patterns: Additional patterns to add to defaults
        
    Returns:
        The configured ResponseSanitizer instance
    """
    global _global_sanitizer
    _global_sanitizer = ResponseSanitizer(
        sensitive_patterns=sensitive_patterns,
        additional_patterns=additional_patterns,
    )
    return _global_sanitizer


def sanitize_tool_response(response: Any, raise_on_violation: bool = True) -> Any:
    """Convenience function to sanitize a tool response.
    
    This should be called before returning any tool response to ensure
    no sensitive paths are leaked.
    
    Args:
        response: The tool response to sanitize
        raise_on_violation: If True, raise error on violation
        
    Returns:
        Sanitized response
        
    Raises:
        PathLeakageError: If raise_on_violation=True and sensitive path found
    """
    return get_response_sanitizer().sanitize_response(
        response, 
        raise_on_violation=raise_on_violation
    )
