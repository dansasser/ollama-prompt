#!/usr/bin/env python3
"""
Session management for persistent conversation context.

Handles:
- Auto-creating sessions on first prompt
- Loading existing sessions by ID
- JSON message storage with dual caching
- Smart context pruning when approaching token limits
- Session updates after each exchange
"""
import json
import uuid
import os
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List

from .session_db import SessionDatabase
from .models import SessionData


class SessionManager:
    """
    Manages conversation sessions with persistent context.

    Responsibilities:
    - Session creation and retrieval
    - Context preparation with pruning
    - Session updates with JSON message storage
    - Dual storage: JSON in history_json + cached plain text in context
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize SessionManager with database.

        Args:
            db_path: Path to database file (optional, uses default if not provided)
        """
        self.db = SessionDatabase(db_path)

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        model_name: Optional[str] = None,
        max_context_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Get existing session or create new one.

        Args:
            session_id: Session ID to load (if None, creates new session)
            model_name: Model name for new session
            max_context_tokens: Max context tokens (overrides default)
            system_prompt: System prompt for new session

        Returns:
            Tuple of (session_dict, is_new)
            - session_dict: Session data as dictionary
            - is_new: True if session was newly created, False if loaded

        Raises:
            ValueError: If session_id provided but not found in database
        """
        if session_id:
            # Try to load existing session
            session = self.db.get_session(session_id)
            if not session:
                raise ValueError(f"Session not found: {session_id}")

            # Update last_used timestamp
            self.db.update_session(session_id, {
                'last_used': datetime.now().isoformat()
            })

            return session, False

        # Create new session with auto-generated ID
        new_session_id = str(uuid.uuid4())

        # Get max_context_tokens from env or use default
        if max_context_tokens is None:
            max_context_tokens = int(os.getenv('OLLAMA_PROMPT_MAX_CONTEXT_TOKENS', '64000'))

        session_data = {
            'session_id': new_session_id,
            'context': '',
            'max_context_tokens': max_context_tokens,
            'history_json': json.dumps({'messages': []}),
            'model_name': model_name,
            'system_prompt': system_prompt
        }

        created_id = self.db.create_session(session_data)
        created_session = self.db.get_session(created_id)

        return created_session, True

    def prepare_prompt(self, session: Dict[str, Any], user_prompt: str) -> str:
        """
        Prepare prompt with session context prepended.

        Logic:
        1. Check if context is near token limit
        2. If yes, prune oldest messages from history_json
        3. Rebuild cached plain text from pruned history
        4. Prepend context to user_prompt

        Args:
            session: Session dictionary from database
            user_prompt: User's new prompt

        Returns:
            Full prompt with context prepended
        """
        # Load session data model for token estimation
        session_data = SessionData.from_dict(session)

        # Check if pruning is needed (90% threshold)
        if session_data.is_context_near_limit(threshold=0.9):
            # Prune and rebuild context
            session = self._prune_and_rebuild_context(session)

        # Get current context (may be empty for new sessions)
        context = session.get('context', '')

        # Prepend system prompt if exists
        if session.get('system_prompt'):
            full_prompt = f"{session['system_prompt']}\n\n{context}\n\nUser: {user_prompt}"
        elif context:
            full_prompt = f"{context}\n\nUser: {user_prompt}"
        else:
            full_prompt = f"User: {user_prompt}"

        return full_prompt

    def update_session(
        self,
        session: Dict[str, Any],
        user_prompt: str,
        assistant_response: str
    ) -> None:
        """
        Update session with new exchange.

        Logic:
        1. Reload session from DB to get latest state
        2. Parse history_json to list of messages
        3. Append user message with timestamp and token estimate
        4. Append assistant message with timestamp and token estimate
        5. Serialize back to history_json
        6. Rebuild cached plain text in context field
        7. Save to database

        Args:
            session: Session dictionary
            user_prompt: User's prompt (without context)
            assistant_response: Model's response
        """
        session_id = session['session_id']

        # Reload session from database to get latest state
        current_session = self.db.get_session(session_id)
        if not current_session:
            raise ValueError(f"Session not found: {session_id}")

        # Parse existing history
        history = json.loads(current_session.get('history_json', '{"messages": []}'))
        messages = history.get('messages', [])

        # Create timestamp
        timestamp = datetime.now().isoformat()

        # Estimate tokens (4 chars = 1 token, minimum 1 token for non-empty strings)
        user_tokens = max(1, len(user_prompt) // 4) if user_prompt else 0
        assistant_tokens = max(1, len(assistant_response) // 4) if assistant_response else 0

        # Append new messages
        messages.append({
            'role': 'user',
            'content': user_prompt,
            'timestamp': timestamp,
            'tokens': user_tokens
        })

        messages.append({
            'role': 'assistant',
            'content': assistant_response,
            'timestamp': timestamp,
            'tokens': assistant_tokens
        })

        # Check if pruning is needed after adding new messages
        max_tokens = current_session.get('max_context_tokens', 64000)
        total_tokens = sum(msg.get('tokens', 0) for msg in messages)

        # Prune if over 90% of limit
        if total_tokens > (max_tokens * 0.9):
            target_tokens = int(max_tokens * 0.8)  # Prune to 80%

            # Remove oldest messages until under target
            while total_tokens > target_tokens and len(messages) > 2:
                removed = messages.pop(0)
                total_tokens -= removed.get('tokens', 0)

                # If there's an assistant message after the user message, remove it too
                if messages and messages[0].get('role') == 'assistant':
                    removed = messages.pop(0)
                    total_tokens -= removed.get('tokens', 0)

        # Serialize back to JSON
        history['messages'] = messages
        history_json = json.dumps(history)

        # Rebuild cached plain text from messages
        cached_context = self._build_context_from_messages(messages)

        # Update database
        self.db.update_session(session_id, {
            'history_json': history_json,
            'context': cached_context,
            'last_used': timestamp
        })

    def _prune_and_rebuild_context(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prune oldest messages when approaching token limit.

        Strategy:
        1. Parse history_json
        2. Calculate total tokens
        3. Remove oldest messages until under 80% of max_context_tokens
        4. Rebuild cached context from remaining messages
        5. Update session dict (not saved to DB yet)

        Args:
            session: Session dictionary

        Returns:
            Updated session dictionary with pruned context
        """
        max_tokens = session.get('max_context_tokens', 64000)
        target_tokens = int(max_tokens * 0.8)  # Prune to 80%

        # Parse history
        history = json.loads(session.get('history_json', '{"messages": []}'))
        messages = history.get('messages', [])

        if not messages:
            return session

        # Calculate current total tokens
        total_tokens = sum(msg.get('tokens', 0) for msg in messages)

        # Prune from the start (oldest messages) if over target
        while total_tokens > target_tokens and len(messages) > 2:
            # Remove oldest exchange (user + assistant pair)
            removed = messages.pop(0)
            total_tokens -= removed.get('tokens', 0)

            # If there's an assistant message after the user message, remove it too
            if messages and messages[0].get('role') == 'assistant':
                removed = messages.pop(0)
                total_tokens -= removed.get('tokens', 0)

        # Rebuild history and context
        history['messages'] = messages
        session['history_json'] = json.dumps(history)
        session['context'] = self._build_context_from_messages(messages)

        return session

    def _build_context_from_messages(self, messages: List[Dict[str, Any]]) -> str:
        """
        Build cached plain text context from message list.

        Format:
        User: <content>
        Assistant: <content>
        User: <content>
        Assistant: <content>

        Args:
            messages: List of message dictionaries

        Returns:
            Plain text context string
        """
        context_lines = []

        for msg in messages:
            role = msg.get('role', 'unknown').capitalize()
            content = msg.get('content', '')
            context_lines.append(f"{role}: {content}")

        return '\n\n'.join(context_lines)

    def close(self):
        """Close database connection."""
        self.db.close()
