"""Type definitions for Kalibr SDK"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class FileUpload:
    """Represents an uploaded file"""

    filename: str
    content_type: str
    size: int
    content: bytes


class Session:
    """Session management for stateful interactions"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._data: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get session data"""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set session data"""
        self._data[key] = value

    def delete(self, key: str) -> None:
        """Delete session data"""
        self._data.pop(key, None)

    def clear(self) -> None:
        """Clear all session data"""
        self._data.clear()
