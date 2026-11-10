"""Preview usage tracking with LRU cache management."""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, fields

from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PreviewUsage:
    """Usage statistics for a preview."""
    
    url: str
    subdomain: Optional[str] = None
    port: Optional[int] = None  # optional for single-port mode
    directory: Optional[str] = None  # virtual directory (e.g. "/", "/dist") for restore
    entry: Optional[str] = None
    workspace_name: Optional[str] = None
    user_id: Optional[str] = None
    chat_id: Optional[str] = None
    created_at: float = 0.0
    last_accessed_at: float = 0.0
    access_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "PreviewUsage":
        # Backward compatibility:
        # - tolerate missing fields
        # - tolerate extra/unknown fields (older schema versions)
        normalized = dict(data or {})
        normalized.setdefault("port", None)
        normalized.setdefault("directory", None)
        normalized.setdefault("entry", None)
        allowed = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in normalized.items() if k in allowed}
        return cls(**filtered)


class PreviewUsageTracker:
    """Tracks preview usage and manages LRU cache."""
    
    def __init__(self, storage_path: Path):
        """Initialize usage tracker.
        
        Args:
            storage_path: Path to JSON file for persistent storage
        """
        self.storage_path = storage_path
        self._usage_data: Dict[str, PreviewUsage] = {}  # Key: subdomain or port (as string)
        self._load()
    
    def _load(self):
        """Load usage data from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._usage_data = {
                        key: PreviewUsage.from_dict(usage_dict)
                        for key, usage_dict in data.items()
                    }
                logger.info(f"Loaded {len(self._usage_data)} preview usage records")
            except Exception as e:
                logger.warning(f"Failed to load usage data: {e}")
                self._usage_data = {}
        else:
            self._usage_data = {}
    
    def _save(self):
        """Save usage data to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                key: usage.to_dict()
                for key, usage in self._usage_data.items()
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save usage data: {e}")
    
    def register_preview(
        self,
        url: str,
        subdomain: Optional[str],
        port: Optional[int],
        workspace_name: Optional[str] = None,
        user_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        directory: Optional[str] = None,
        entry: Optional[str] = None,
    ):
        """Register a new preview or update existing one.
        
        If the preview already exists (by subdomain or port), preserve existing
        statistics (access_count, last_accessed_at, created_at).
        
        Args:
            url: Preview URL
            subdomain: Subdomain (if using wildcard domain)
            port: Port number
            workspace_name: Workspace name
            user_id: User ID
            chat_id: Chat ID
        """
        key = subdomain if subdomain else (str(port) if port is not None else None)
        if not key:
            logger.warning("Cannot register preview without subdomain or port")
            return
        
        # Check if preview already exists
        existing_usage = self._usage_data.get(key)
        
        if existing_usage:
            # If workspace_name doesn't match, this is a conflict - don't update
            if existing_usage.workspace_name and workspace_name and existing_usage.workspace_name != workspace_name:
                logger.warning(
                    f"Subdomain {key} already used by workspace {existing_usage.workspace_name}, "
                    f"cannot assign to {workspace_name}. This should not happen if subdomain reuse logic is correct."
                )
                # Don't update - let the caller handle this by generating a new subdomain
                return
            
            # Update existing preview, but preserve statistics
            existing_usage.url = url
            existing_usage.directory = directory
            existing_usage.entry = entry
            existing_usage.workspace_name = workspace_name
            existing_usage.user_id = user_id
            existing_usage.chat_id = chat_id
            # Preserve: created_at, last_accessed_at, access_count
            self._save()
            logger.debug(f"Updated existing preview: {key} -> {url} (preserved stats: count={existing_usage.access_count})")
        else:
            # Create new preview
            now = time.time()
            usage = PreviewUsage(
                url=url,
                subdomain=subdomain,
                port=port,
                directory=directory,
                entry=entry,
                workspace_name=workspace_name,
                user_id=user_id,
                chat_id=chat_id,
                created_at=now,
                last_accessed_at=now,
                access_count=0,
            )
            self._usage_data[key] = usage
            self._save()
            logger.debug(f"Registered new preview: {key} -> {url}")
    
    def record_access(self, subdomain: Optional[str] = None, port: Optional[int] = None):
        """Record that a preview URL was accessed.
        
        Args:
            subdomain: Subdomain (if using wildcard domain)
            port: Port number (if not using subdomain)
        """
        key = subdomain if subdomain else (str(port) if port is not None else None)
        if not key or key not in self._usage_data:
            logger.warning(f"Preview not found for access record: {key}")
            return
        
        usage = self._usage_data[key]
        usage.last_accessed_at = time.time()
        usage.access_count += 1
        self._save()
        logger.debug(f"Recorded access for {key}: count={usage.access_count}")
    
    def unregister_preview(self, subdomain: Optional[str] = None, port: Optional[int] = None):
        """Unregister a preview (when it's stopped).
        
        Args:
            subdomain: Subdomain (if using wildcard domain)
            port: Port number (if not using subdomain)
        """
        key = subdomain if subdomain else (str(port) if port is not None else None)
        if key and key in self._usage_data:
            del self._usage_data[key]
            self._save()
            logger.debug(f"Unregistered preview: {key}")
    
    def get_lru_preview(self) -> Optional[Tuple[str, PreviewUsage]]:
        """Get the least recently used preview.

        If you pass a set of keys, this only considers those keys (useful for
        finding the LRU among currently-active previews).
        
        Returns:
            Tuple of (key, PreviewUsage) or None if no previews exist
        """
        if not self._usage_data:
            return None
        
        # Find preview with oldest last_accessed_at
        lru_key = min(self._usage_data.keys(), key=lambda k: self._usage_data[k].last_accessed_at)
        return (lru_key, self._usage_data[lru_key])

    def get_lru_preview_for_keys(self, keys: set) -> Optional[Tuple[str, PreviewUsage]]:
        """Get the least recently used preview restricted to a key set."""
        if not keys:
            return None
        candidates = [k for k in keys if k in self._usage_data]
        if not candidates:
            return None
        lru_key = min(candidates, key=lambda k: self._usage_data[k].last_accessed_at)
        return (lru_key, self._usage_data[lru_key])
    
    def get_all_previews(self) -> List[PreviewUsage]:
        """Get all registered previews.
        
        Returns:
            List of PreviewUsage objects
        """
        return list(self._usage_data.values())
    
    def get_preview_by_key(self, key: str) -> Optional[PreviewUsage]:
        """Get preview by key (subdomain or port).
        
        Args:
            key: Subdomain or port as string
            
        Returns:
            PreviewUsage or None
        """
        return self._usage_data.get(key)
    
    def get_preview_by_workspace_name(self, workspace_name: Optional[str]) -> Optional[PreviewUsage]:
        """Get the most recently accessed preview for a workspace.
        
        Args:
            workspace_name: Workspace name
            
        Returns:
            PreviewUsage or None
        """
        if not workspace_name:
            return None
        
        # Find all previews for this workspace
        workspace_previews = [
            usage for usage in self._usage_data.values()
            if usage.workspace_name == workspace_name and usage.subdomain
        ]
        
        if not workspace_previews:
            return None
        
        # Return the most recently accessed one
        return max(workspace_previews, key=lambda u: u.last_accessed_at or u.created_at or 0.0)
    
    def cleanup_stale_previews(self, active_ports: set, active_subdomains: set):
        """Remove previews that are no longer active.
        
        Args:
            active_ports: Set of active port numbers
            active_subdomains: Set of active subdomains
        """
        keys_to_remove = []
        for key, usage in self._usage_data.items():
            if usage.subdomain:
                if usage.subdomain not in active_subdomains:
                    keys_to_remove.append(key)
            else:
                if usage.port not in active_ports:
                    keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._usage_data[key]
            logger.debug(f"Cleaned up stale preview: {key}")
        
        if keys_to_remove:
            self._save()
