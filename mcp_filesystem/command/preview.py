"""Frontend preview server management."""

import asyncio
import os
import random
import string
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.server.fastmcp.utilities.logging import get_logger
from starlette.responses import FileResponse, JSONResponse, Response

from .preview_usage import PreviewUsageTracker, PreviewUsage

logger = get_logger(__name__)

# Global usage tracker (shared across all PreviewManager instances)
_global_usage_tracker: Optional[PreviewUsageTracker] = None


def get_global_usage_tracker(storage_path: Optional[Path] = None) -> PreviewUsageTracker:
    """Get or create the global usage tracker.
    
    Args:
        storage_path: Path to storage file (default: user_data/.preview_usage.json)
        
    Returns:
        PreviewUsageTracker instance
    """
    global _global_usage_tracker
    if _global_usage_tracker is None:
        if storage_path is None:
            # Default to user_data directory
            default_user_data_dir = Path(__file__).parent.parent.parent / "user_data"
            user_data_dir = Path(os.environ.get("MCP_WORKSPACES_DIR", str(default_user_data_dir)))
            storage_path = user_data_dir / ".preview_usage.json"
        _global_usage_tracker = PreviewUsageTracker(storage_path)
    return _global_usage_tracker


class PreviewRoutingMiddleware:
    """ASGI middleware to serve previews in single-port mode based on Host subdomain."""

    def __init__(self, app, config: Optional[Dict[str, Any]] = None):
        self.app = app
        cfg = config or {}
        preview_cfg = cfg.get("preview", {})
        wildcard = preview_cfg.get("wildcard_domain") or ""
        wildcard = wildcard.replace("https://", "").replace("http://", "")
        if wildcard.startswith("*."):
            wildcard = wildcard[2:]
        self.base_domain = wildcard.lstrip(".")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        host = ""
        for name, value in scope.get("headers", []):
            if name == b"host":
                host = value.decode()
                break
        if ":" in host:
            host = host.split(":", 1)[0]

        if self.base_domain and host.endswith(self.base_domain):
            subdomain = host[: -len(self.base_domain)].rstrip(".")
            if subdomain:
                preview_entry = PreviewManager.get_preview_entry(subdomain)
                if preview_entry:
                    response = await self._serve_preview(scope, preview_entry, subdomain)
                    await response(scope, receive, send)
                    return

        await self.app(scope, receive, send)

    async def _serve_preview(self, scope, preview_entry: Dict[str, Any], subdomain: str) -> Response:
        path = scope.get("path", "/")
        rel_path = path.lstrip("/")
        serve_path: Path = preview_entry["serve_path"]
        entry = preview_entry.get("entry") or "index.html"

        target = (serve_path / rel_path).resolve()
        try:
            target.relative_to(serve_path.resolve())
        except ValueError:
            return JSONResponse({"success": False, "error": "Invalid path"}, status_code=403)

        if target.is_dir():
            target = target / entry

        if not target.exists():
            target = (serve_path / entry).resolve()

        if not target.exists():
            return JSONResponse({"success": False, "error": "File not found"}, status_code=404)

        try:
            tracker = get_global_usage_tracker()
            tracker.record_access(subdomain=subdomain)
        except Exception:
            pass

        return FileResponse(target)


@dataclass
class PreviewInfo:
    """Information about an active preview."""

    port: Optional[int]
    directory: Path
    entry: str
    subdomain: Optional[str] = None  # Subdomain for wildcard domain
    process: Optional[asyncio.subprocess.Process] = None  # unused in single-port mode
    url: str = ""
    started_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "port": self.port,
            "directory": str(self.directory),
            "entry": self.entry,
            "url": self.url,
            "started_at": self.started_at,
            # In single-port mode, the main server process serves previews, so a
            # missing subprocess still means the preview is "running".
            "running": True if self.process is None else (self.process.returncode is None),
        }


class PreviewManager:
    """Manages frontend preview servers for sessions."""

    def __init__(
        self,
        workspace_path: Path,
        workspace_name: Optional[str] = None,
        host: str = "0.0.0.0",
        external_host: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        usage_tracker: Optional[PreviewUsageTracker] = None,
    ):
        """Initialize preview manager.

        Args:
            workspace_path: The workspace directory.
            workspace_name: Workspace name for generating subdomain (e.g., "user123_chat456").
            host: Host to bind preview servers to.
            external_host: External hostname for URLs (e.g., for Docker).
            config: Additional configuration.
        """
        self.workspace_path = workspace_path
        self.workspace_name = workspace_name
        self.host = host
        self.external_host = external_host or "localhost"
        self.config = config or {}
        
        # URL generation settings (single-port + wildcard domain routing)
        self.wildcard_domain: Optional[str] = None  # Wildcard domain like "*.proxy.your_domain.com"
        self.use_tls: bool = False  # Whether to use HTTPS/TLS for preview URLs
        self.max_active_previews: Optional[int] = None
        # Default port for URL building (main MCP port)
        try:
            self.default_port = int(os.environ.get("FASTMCP_PORT", "18089"))
        except Exception:
            self.default_port = 18089

        # Override from config
        preview_config = self.config.get("preview", {})
        if preview_config:
            if "external_host" in preview_config:
                self.external_host = preview_config["external_host"]
            if "wildcard_domain" in preview_config:
                self.wildcard_domain = preview_config["wildcard_domain"]
            if "use_tls" in preview_config:
                self.use_tls = bool(preview_config["use_tls"])
            if "max_active_previews" in preview_config:
                try:
                    v = int(preview_config["max_active_previews"])
                    if v > 0:
                        self.max_active_previews = v
                except Exception:
                    self.max_active_previews = None

        # Active preview for this session (only one at a time)
        self.active_preview: Optional[PreviewInfo] = None

        # Track used subdomains globally (class-level) to ensure uniqueness
        PreviewManager._used_subdomains: set = getattr(PreviewManager, "_used_subdomains", set())
        
        # Global mapping: subdomain -> PreviewManager instance (for LRU cleanup)
        PreviewManager._active_previews: Dict[str, "PreviewManager"] = getattr(
            PreviewManager, "_active_previews", {}
        )
        # Host routing map for single-port mode
        PreviewManager._preview_entries: Dict[str, Dict[str, Any]] = getattr(
            PreviewManager, "_preview_entries", {}
        )
        
        # Usage tracker for LRU management
        self.usage_tracker = usage_tracker or get_global_usage_tracker()
        
        # Store workspace info for usage tracking
        self.workspace_name = workspace_name

    def _generate_random_subdomain(self) -> str:
        """Generate a short random subdomain.

        We no longer encode ports in the subdomain: previews are served by the
        main server (single-port), and routing is done via Host header.
        """
        subdomain = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        max_attempts = 10
        attempts = 0
        while subdomain in PreviewManager._used_subdomains and attempts < max_attempts:
            subdomain = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
            attempts += 1
        
        return subdomain

    def _normalize_usage_directory(self, raw_directory: Optional[str], entry: Optional[str] = None) -> str:
        """Normalize stored directory into a virtual directory (e.g. '/', '/dist').

        Backward compatible:
        - If stored as absolute path under workspace_path, convert to relative.
        - If missing/invalid, fall back to '/'.
        """
        if not raw_directory:
            return "/"

        # Already virtual-style
        if raw_directory in ("/", ".", "/.", ""):
            return "/"

        raw_directory = raw_directory.replace("\\", "/")

        # Absolute path stored previously: try to relativize to workspace
        if raw_directory.startswith("/"):
            try:
                rel = Path(raw_directory).resolve().relative_to(self.workspace_path.resolve())
                # If the stored "directory" accidentally includes a file path,
                # convert it to its parent directory.
                if rel.name and rel.suffix:
                    rel = rel.parent
                if entry and rel.name == entry:
                    rel = rel.parent
                rel_str = str(rel).replace("\\", "/").strip("/").strip(".")
                return f"/{rel_str}" if rel_str else "/"
            except Exception:
                return "/"

        # Treat as relative directory under workspace
        rel_path = Path(raw_directory)
        if rel_path.suffix:
            rel_path = rel_path.parent
        if entry and rel_path.name == entry:
            rel_path = rel_path.parent
        rel_str = str(rel_path).replace("\\", "/").strip("/").strip(".")
        return f"/{rel_str}" if rel_str else "/"

    def _build_url(self, port: Optional[int], entry: str, subdomain: Optional[str] = None) -> str:
        """Build the preview URL.

        Preferred pattern (production): `https://{subdomain}.{wildcard_domain}/{entry}`.
        Fallback: `http(s)://{external_host}:{FASTMCP_PORT}/{entry}`.
        """
        if self.wildcard_domain and subdomain:
            domain = self.wildcard_domain.replace("*", subdomain)
            if self.wildcard_domain.startswith("https://"):
                protocol = "https"
            elif self.wildcard_domain.startswith("http://"):
                protocol = "http"
            else:
                protocol = "https" if self.use_tls else "http"
            if not domain.startswith(("http://", "https://")):
                domain = f"{protocol}://{domain}"
            return f"{domain}/{entry.lstrip('/')}"

        protocol = "https" if self.use_tls else "http"
        return f"{protocol}://{self.external_host}:{port or self.default_port}/{entry}"

    @staticmethod
    def get_preview_entry(subdomain: str) -> Optional[Dict[str, Any]]:
        return getattr(PreviewManager, "_preview_entries", {}).get(subdomain)

    async def start_preview(
        self,
        directory: str = "/",
        entry: str = "index.html",
        subdomain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a preview (single-port mode only)."""
        # Reuse existing subdomain for the same session instead of stopping
        reuse_subdomain = None
        if self.active_preview and not subdomain:
            # Same session: reuse the existing subdomain to keep the same URL
            reuse_subdomain = self.active_preview.subdomain
        elif not subdomain and self.workspace_name:
            # If active_preview is None (e.g., after LRU cleanup), try to find existing subdomain from usage_tracker
            existing_usage = self.usage_tracker.get_preview_by_workspace_name(self.workspace_name)
            if existing_usage and existing_usage.subdomain:
                # Check if this subdomain is still available (not used by another workspace)
                existing_entry = PreviewManager._preview_entries.get(existing_usage.subdomain)
                if existing_entry and existing_entry.get("workspace_name") == self.workspace_name:
                    reuse_subdomain = existing_usage.subdomain
                elif not existing_entry:
                    # Subdomain exists in tracker but not in active entries, can reuse
                    reuse_subdomain = existing_usage.subdomain

        directory_rel = (directory or "/").lstrip("/").replace("\\", "/").strip()
        if directory_rel in ("", "."):
            directory_rel = ""

        # Support entry paths like "dist/index.html" by folding them into directory.
        entry_path = (entry or "index.html").lstrip("/").replace("\\", "/")
        if "/" in entry_path:
            entry_dir, entry_name = entry_path.rsplit("/", 1)
            directory_rel = "/".join([p for p in [directory_rel.strip("/"), entry_dir.strip("/")] if p]).strip("/")
            entry = entry_name
        else:
            entry = entry_path

        serve_path = self.workspace_path / directory_rel if directory_rel else self.workspace_path
        if not serve_path.exists() or not serve_path.is_dir():
            return {"success": False, "error": f"Directory does not exist: /{directory_rel}"}

        if not (serve_path / entry).exists():
            for fallback in ["index.html", "index.htm", "default.html"]:
                if (serve_path / fallback).exists():
                    entry = fallback
                    break

        if not subdomain:
            if reuse_subdomain:
                # Reuse existing subdomain for same session
                # Verify it's not being used by another workspace
                existing_entry = PreviewManager._preview_entries.get(reuse_subdomain)
                if existing_entry and existing_entry.get("workspace_name") != self.workspace_name:
                    # Subdomain is being used by another workspace, generate new one
                    logger.warning(
                        f"Subdomain {reuse_subdomain} is used by workspace {existing_entry.get('workspace_name')}, "
                        f"generating new subdomain for {self.workspace_name}"
                    )
                    subdomain = self._generate_random_subdomain()
                else:
                    subdomain = reuse_subdomain
            else:
                # Generate new subdomain for new preview
                subdomain = self._generate_random_subdomain()
        if not subdomain.strip():
            return {"success": False, "error": "Invalid subdomain"}
        
        # Verify subdomain is not already used by another workspace
        existing_entry = PreviewManager._preview_entries.get(subdomain)
        if existing_entry and existing_entry.get("workspace_name") != self.workspace_name:
            # Conflict: subdomain is used by another workspace, generate new one
            logger.warning(
                f"Subdomain {subdomain} conflict detected, generating new subdomain for {self.workspace_name}"
            )
            subdomain = self._generate_random_subdomain()
        
        # Only add to used_subdomains if it's a new subdomain
        if subdomain not in PreviewManager._used_subdomains:
            PreviewManager._used_subdomains.add(subdomain)

        user_id = chat_id = None
        if self.workspace_name and "_" in self.workspace_name:
            parts = self.workspace_name.rsplit("_", 1)
            if len(parts) == 2:
                user_id, chat_id = parts

        if self.max_active_previews is not None:
            active_total = len(getattr(PreviewManager, "_preview_entries", {}))
            while active_total >= self.max_active_previews:
                cleaned = await self._cleanup_lru_preview()
                if not cleaned:
                    return {"success": False, "error": f"Maximum active previews reached ({self.max_active_previews})"}
                active_total = len(getattr(PreviewManager, "_preview_entries", {}))

        virtual_directory = f"/{directory_rel}" if directory_rel else "/"
        url = self._build_url(self.default_port, entry, subdomain)
        PreviewManager._preview_entries[subdomain] = {
            "serve_path": serve_path,
            "entry": entry,
            "workspace_name": self.workspace_name,
        }
        PreviewManager._active_previews[subdomain] = self
        self.active_preview = PreviewInfo(
            port=None,
            directory=serve_path,
            entry=entry,
            subdomain=subdomain,
            process=None,
            url=url,
        )
        self.usage_tracker.register_preview(
            url=url,
            subdomain=subdomain,
            port=None,
            workspace_name=self.workspace_name,
            user_id=user_id,
            chat_id=chat_id,
            directory=virtual_directory,
            entry=entry,
        )
        return {
            "success": True,
            "url": url,
            "directory": virtual_directory,
            "entry": entry,
            "subdomain": subdomain,
            "port": None,
            "message": f"Preview registered at {url}",
        }

    async def stop_preview(self) -> Dict[str, Any]:
        """Stop the active preview (single-port mode)."""
        if not self.active_preview:
            return {"success": True, "message": "No active preview to stop"}

        preview = self.active_preview
        subdomain = preview.subdomain

        if subdomain:
            PreviewManager._used_subdomains.discard(subdomain)
            PreviewManager._preview_entries.pop(subdomain, None)
            PreviewManager._active_previews.pop(subdomain, None)
        self.usage_tracker.unregister_preview(subdomain=subdomain, port=None)
        self.active_preview = None
        return {"success": True, "message": "Preview stopped"}

    def get_status(self) -> Dict[str, Any]:
        """Get the status of the preview server."""
        if not self.active_preview:
            return {"active": False, "message": "No active preview"}
        return {"active": True, **self.active_preview.to_dict()}

    async def _cleanup_lru_preview(self) -> bool:
        """Clean up the least recently used preview mapping.
        
        Returns:
            True if a preview was cleaned up, False otherwise.
        """
        active_keys = set(getattr(PreviewManager, "_preview_entries", {}).keys())
        lru_result = self.usage_tracker.get_lru_preview_for_keys(active_keys)
        if not lru_result:
            if not active_keys:
                return False
            # If tracker is missing records, evict an arbitrary active preview to
            # ensure we can enforce the cap.
            lru_key = next(iter(active_keys))
            logger.info(f"Cleaning up preview mapping without usage record: {lru_key}")
            PreviewManager._used_subdomains.discard(lru_key)
            PreviewManager._preview_entries.pop(lru_key, None)
            PreviewManager._active_previews.pop(lru_key, None)
            self.usage_tracker.unregister_preview(subdomain=lru_key, port=None)
            return True
        
        lru_key, lru_usage = lru_result
        
        preview_manager = PreviewManager._active_previews.get(lru_key)
        if preview_manager and preview_manager.active_preview and preview_manager.active_preview.subdomain == lru_key:
            logger.info(f"Cleaning up LRU preview: {lru_key}")
            await preview_manager.stop_preview()
            return True

        # Fallback: remove mapping directly (ensures active_total decreases)
        logger.info(f"Cleaning up LRU preview mapping directly: {lru_key}")
        PreviewManager._used_subdomains.discard(lru_key)
        PreviewManager._preview_entries.pop(lru_key, None)
        PreviewManager._active_previews.pop(lru_key, None)
        self.usage_tracker.unregister_preview(subdomain=lru_usage.subdomain, port=lru_usage.port)
        if preview_manager and preview_manager.active_preview and preview_manager.active_preview.subdomain == lru_key:
            preview_manager.active_preview = None
        return True

    async def restore_preview_from_usage(
        self,
        usage: "PreviewUsage",
    ) -> bool:
        """Restore a preview mapping (single-port)."""
        if usage.workspace_name != self.workspace_name:
            return False

        entry = usage.entry or "index.html"
        directory = self._normalize_usage_directory(usage.directory, entry=entry)

        # Backward compatibility: some older records stored "entry" as a path
        # (e.g. "dist/index.html") with directory="/".
        entry_path = entry.lstrip("/").replace("\\", "/")
        if "/" in entry_path:
            entry_dir, entry_name = entry_path.rsplit("/", 1)
            if directory.rstrip("/") in ("", "/"):
                directory = f"/{entry_dir}"
            else:
                directory = f"{directory.rstrip('/')}/{entry_dir}"
            entry = entry_name

        if directory.startswith("/"):
            directory_rel = directory[1:]
        else:
            directory_rel = directory
        serve_path = self.workspace_path / directory_rel if directory_rel and directory_rel != "." else self.workspace_path
        if not serve_path.exists() or not serve_path.is_dir():
            return False
        if not (serve_path / entry).exists():
            for fallback in ["index.html", "index.htm", "default.html"]:
                if (serve_path / fallback).exists():
                    entry = fallback
                    break

        result = await self.start_preview(
            directory="/" + directory_rel if directory_rel else "/",
            entry=entry,
            subdomain=usage.subdomain,
        )
        return bool(result.get("success"))

    @staticmethod
    async def restore_all_previews_on_startup(
        workspaces_dir: Path,
        config: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Restore all preview services from JSON file on startup.
        
        This method should be called once when the server starts.
        
        Args:
            workspaces_dir: Directory containing workspace directories
            config: Configuration dictionary
            
        Returns:
            Number of previews successfully restored
        """
        config = config or {}
        preview_config = config.get("preview", {})
        # Get the usage tracker
        usage_tracker = get_global_usage_tracker()
        storage_path = usage_tracker.storage_path
        logger.info(f"Loading preview usage data from: {storage_path}")
        
        # Get all preview usage records
        all_previews = usage_tracker.get_all_previews()
        if not all_previews:
            logger.info("No preview services found in storage, nothing to restore")
            return 0

        # Choose at most 1 preview per workspace (most recently accessed).
        # This matches the current PreviewManager behavior (1 active preview per workspace).
        by_workspace: Dict[str, PreviewUsage] = {}
        missing_workspace = 0
        missing_subdomain = 0
        def _recency(u: PreviewUsage) -> float:
            return float(u.last_accessed_at or u.created_at or 0.0)

        for p in all_previews:
            if not p.workspace_name:
                missing_workspace += 1
                continue
            if not p.subdomain:
                missing_subdomain += 1
                continue
            existing = by_workspace.get(p.workspace_name)
            if not existing or _recency(p) > _recency(existing):
                by_workspace[p.workspace_name] = p

        selected_previews = list(by_workspace.values())
        selected_previews.sort(key=_recency, reverse=True)

        if missing_workspace:
            logger.warning(f"Found {missing_workspace} preview(s) without workspace_name, skipping")
        if missing_subdomain:
            logger.warning(f"Found {missing_subdomain} preview(s) without subdomain, skipping")

        # Apply global max_active_previews cap at restore time
        cap = preview_config.get("max_active_previews")
        try:
            cap = int(cap) if cap is not None else None
            if cap is not None and cap <= 0:
                cap = None
        except Exception:
            cap = None

        if cap is not None and len(selected_previews) > cap:
            skipped = len(selected_previews) - cap
            selected_previews = selected_previews[:cap]
            logger.warning(f"Restore cap reached ({cap}), skipping {skipped} older workspace previews")

        logger.info(f"Found {len(selected_previews)} preview service(s) to restore across {len(by_workspace)} workspace(s)")
        
        restored_count = 0
        failed_count = 0
        skipped_count = 0

        for idx, preview in enumerate(selected_previews, 1):
            workspace_name = preview.workspace_name
            subdomain = preview.subdomain
            url = preview.url
            key_info = f"subdomain {subdomain}" if subdomain else "no-subdomain"

            logger.info(f"[{idx}/{len(selected_previews)}] Restoring preview: {workspace_name} {key_info} -> {url}")
            workspace_path = workspaces_dir / workspace_name
            if not workspace_path.exists():
                logger.warning(f"  ✗ Workspace directory does not exist: {workspace_path}, skipping")
                skipped_count += 1
                continue

            preview_manager = PreviewManager(
                workspace_path=workspace_path,
                workspace_name=workspace_name,
                config=config,
                usage_tracker=usage_tracker,
            )

            try:
                success = await preview_manager.restore_preview_from_usage(preview)
                if success:
                    restored_count += 1
                    logger.info(f"  ✓ Successfully restored preview on {key_info}")
                else:
                    failed_count += 1
                    logger.warning(
                        f"  ✗ Failed to restore preview on {key_info} (directory={preview.directory}, entry={preview.entry})"
                    )
            except Exception as e:
                failed_count += 1
                logger.error(f"  ✗ Error restoring preview on {key_info}: {e}", exc_info=True)
        
        total_processed = restored_count + failed_count + skipped_count
        logger.info(
            f"Restoration summary: {restored_count} restored, {failed_count} failed, {skipped_count} skipped "
            f"(total: {total_processed}/{len(selected_previews)})"
        )
        return restored_count

    async def cleanup(self):
        """Clean up resources (call on shutdown)."""
        await self.stop_preview()
