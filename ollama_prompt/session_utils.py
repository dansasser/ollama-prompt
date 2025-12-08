#!/usr/bin/env python3
"""
Session utility commands for managing stored sessions.
"""
import json

from .session_db import SessionDatabase


def handle_utility_command(args):
    """
    Route utility commands to appropriate handlers.

    Args:
        args: Parsed command-line arguments
    """
    if args.list_sessions:
        list_sessions()
    elif args.purge is not None:
        purge_sessions(args.purge)
    elif args.session_info:
        show_session_info(args.session_info)


def list_sessions():
    """
    List all stored sessions with basic information.

    Output format:
    {
      "sessions": [
        {
          "session_id": "abc-123",
          "model_name": "deepseek-v3.1:671b-cloud",
          "created_at": "2025-10-28T10:30:00",
          "last_used": "2025-10-28T14:45:00",
          "message_count": 5,
          "context_tokens": 1250
        },
        ...
      ],
      "total": 3
    }
    """
    try:
        db = SessionDatabase()
        all_sessions = db.list_all_sessions()

        sessions_info = []
        for session in all_sessions:
            # Count messages if history_json exists
            message_count = 0
            if session.get("history_json"):
                try:
                    history = json.loads(session["history_json"])
                    message_count = len(history.get("messages", []))
                except (json.JSONDecodeError, KeyError):
                    pass

            # Estimate tokens from context
            context_tokens = len(session.get("context", "")) // 4

            sessions_info.append(
                {
                    "session_id": session["session_id"],
                    "model_name": session.get("model_name", "unknown"),
                    "created_at": session["created_at"],
                    "last_used": session["last_used"],
                    "message_count": message_count,
                    "context_tokens": context_tokens,
                }
            )

        output = {"sessions": sessions_info, "total": len(sessions_info)}

        print(json.dumps(output, indent=2))

    except Exception as e:
        print(json.dumps({"error": f"Failed to list sessions: {e}"}))


def purge_sessions(days):
    """
    Remove sessions older than specified number of days.

    Args:
        days (int): Remove sessions not used in this many days

    Output format:
    {
      "removed": 5,
      "message": "Removed 5 sessions older than 30 days"
    }
    """
    try:
        db = SessionDatabase()
        removed_count = db.purge_sessions(days)

        output = {
            "removed": removed_count,
            "message": f"Removed {removed_count} sessions older than {days} days",
        }

        print(json.dumps(output, indent=2))

    except Exception as e:
        print(json.dumps({"error": f"Failed to purge sessions: {e}"}))


def show_session_info(session_id):
    """
    Show detailed information for a specific session.

    Args:
        session_id (str): Session ID to query

    Output format:
    {
      "session_id": "abc-123",
      "model_name": "deepseek-v3.1:671b-cloud",
      "created_at": "2025-10-28T10:30:00",
      "last_used": "2025-10-28T14:45:00",
      "max_context_tokens": 64000,
      "context_tokens": 1250,
      "context_usage_percent": 1.95,
      "message_count": 5,
      "messages": [
        {"role": "user", "content": "...", "timestamp": "...", "tokens": 123},
        {"role": "assistant", "content": "...", "timestamp": "...", "tokens": 456}
      ],
      "system_prompt": "You are a helpful assistant",
      "metadata": {...}
    }
    """
    try:
        db = SessionDatabase()
        session = db.get_session(session_id)

        if not session:
            print(json.dumps({"error": f"Session not found: {session_id}"}))
            return

        # Parse history_json if exists
        messages = []
        if session.get("history_json"):
            try:
                history = json.loads(session["history_json"])
                messages = history.get("messages", [])
            except (json.JSONDecodeError, KeyError):
                pass

        # Calculate context usage
        context_tokens = len(session.get("context", "")) // 4
        max_tokens = session.get("max_context_tokens", 64000)
        context_usage_percent = (
            (context_tokens / max_tokens) * 100 if max_tokens > 0 else 0
        )

        # Parse metadata if exists
        metadata = {}
        if session.get("metadata_json"):
            try:
                metadata = json.loads(session["metadata_json"])
            except (json.JSONDecodeError, KeyError):
                pass

        output = {
            "session_id": session["session_id"],
            "model_name": session.get("model_name", "unknown"),
            "created_at": session["created_at"],
            "last_used": session["last_used"],
            "max_context_tokens": max_tokens,
            "context_tokens": context_tokens,
            "context_usage_percent": round(context_usage_percent, 2),
            "message_count": len(messages),
            "messages": messages,
            "system_prompt": session.get("system_prompt"),
            "metadata": metadata,
        }

        print(json.dumps(output, indent=2))

    except Exception as e:
        print(json.dumps({"error": f"Failed to get session info: {e}"}))
