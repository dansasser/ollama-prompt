"""
Data models for session management.

Defines the structure and validation for session data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SessionData:
    """
    Data model for a session.

    Attributes:
        session_id: Unique session identifier (UUID)
        context: Conversation context (accumulated prompt/response history)
        created_at: ISO timestamp of session creation
        last_used: ISO timestamp of last session access
        max_context_tokens: Maximum tokens allowed in context
        history_json: Optional JSON string of full conversation history
        metadata_json: Optional JSON string for additional metadata
        model_name: Model name used for this session
        system_prompt: Optional system prompt for the session
    """

    session_id: str
    context: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: str = field(default_factory=lambda: datetime.now().isoformat())
    max_context_tokens: int = 64000
    history_json: Optional[str] = None
    metadata_json: Optional[str] = None
    model_name: Optional[str] = None
    system_prompt: Optional[str] = None

    def to_dict(self) -> dict:
        """
        Convert session data to dictionary for database storage.

        Returns:
            dict: Dictionary representation of session data
        """
        return {
            "session_id": self.session_id,
            "context": self.context,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "max_context_tokens": self.max_context_tokens,
            "history_json": self.history_json,
            "metadata_json": self.metadata_json,
            "model_name": self.model_name,
            "system_prompt": self.system_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionData":
        """
        Create SessionData instance from dictionary.

        Args:
            data: Dictionary containing session fields

        Returns:
            SessionData: New instance populated from dictionary
        """
        return cls(
            session_id=data["session_id"],
            context=data.get("context", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_used=data.get("last_used", datetime.now().isoformat()),
            max_context_tokens=data.get("max_context_tokens", 64000),
            history_json=data.get("history_json"),
            metadata_json=data.get("metadata_json"),
            model_name=data.get("model_name"),
            system_prompt=data.get("system_prompt"),
        )

    def update_last_used(self):
        """Update the last_used timestamp to current time."""
        self.last_used = datetime.now().isoformat()

    def estimate_tokens(self) -> int:
        """
        Estimate number of tokens in current context.

        Uses simple heuristic: ~4 characters per token.

        Returns:
            int: Estimated token count
        """
        return len(self.context) // 4

    def is_context_near_limit(self, threshold: float = 0.9) -> bool:
        """
        Check if context is approaching token limit.

        Args:
            threshold: Percentage of max_context_tokens to consider "near" (default: 0.9 = 90%)

        Returns:
            bool: True if context is at or above threshold
        """
        current_tokens = self.estimate_tokens()
        limit = self.max_context_tokens * threshold
        return current_tokens >= limit
