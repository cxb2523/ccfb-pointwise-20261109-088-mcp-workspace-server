from contextvars import ContextVar
from typing import Dict, Optional, Tuple

# Context variable to store the current session/chat ID
# This allows us to access the chat ID inside tool implementations
chat_id_var: ContextVar[Optional[str]] = ContextVar("chat_id", default=None)

# Context variable to store the user ID
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)

# Context variable to store the session ID (set in connect_sse)
session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)

# Global mapping from session_id to (user_id, chat_id)
# This is populated by POST /messages requests and read by tools
# Key: session_id (str), Value: (user_id, chat_id) tuple
_session_info_map: Dict[str, Tuple[Optional[str], Optional[str]]] = {}


def set_session_info(session_id: str, user_id: Optional[str], chat_id: Optional[str]):
    """Register user_id and chat_id for a given session_id."""
    _session_info_map[session_id] = (user_id, chat_id)


def get_session_info(session_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Get the (user_id, chat_id) associated with a session_id."""
    return _session_info_map.get(session_id, (None, None))


def get_workspace_name(user_id: Optional[str], chat_id: Optional[str]) -> Optional[str]:
    """
    Generate workspace directory name based on user_id and chat_id.
    
    Rules:
    - Both user_id and chat_id: "{user_id}_{chat_id}"
    - Only user_id: "{user_id}"
    - Only chat_id: "{chat_id}"
    - Neither: None (use default/global mode)
    """
    if user_id and chat_id:
        return f"{user_id}_{chat_id}"
    elif user_id:
        return user_id
    elif chat_id:
        return chat_id
    else:
        return None


# Legacy compatibility
def set_session_chat_id(session_id: str, chat_id: str):
    """Register a chat_id for a given session_id (legacy compatibility)."""
    existing_user_id, _ = _session_info_map.get(session_id, (None, None))
    _session_info_map[session_id] = (existing_user_id, chat_id)


def get_chat_id_for_session(session_id: str) -> Optional[str]:
    """Get the chat_id associated with a session_id (legacy compatibility)."""
    _, chat_id = _session_info_map.get(session_id, (None, None))
    return chat_id
