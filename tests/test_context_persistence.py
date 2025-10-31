#!/usr/bin/env python3
"""
Integration tests for session context persistence.

Tests cover:
1. Session auto-creation on first prompt
2. Session continuation with --session-id
3. Context persistence across multiple exchanges
4. JSON message storage format
5. Cached plain text accuracy
6. Context pruning when approaching limits
"""
import os
import sys
import tempfile
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ollama_prompt.session_manager import SessionManager
from ollama_prompt.session_db import SessionDatabase


def test_auto_create_session():
    """Test that sessions are auto-created when session_id is None."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        manager = SessionManager(db_path)

        # Get or create session (no session_id provided)
        session, is_new = manager.get_or_create_session(
            model_name='test-model',
            max_context_tokens=1000
        )

        assert is_new is True, "Session should be newly created"
        assert session['session_id'] is not None, "Session should have ID"
        assert session['model_name'] == 'test-model', "Model name should be set"
        assert session['max_context_tokens'] == 1000, "Max tokens should be set"

        manager.close()
        print("[OK] Auto-create session works")

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_load_existing_session():
    """Test that existing sessions can be loaded by ID."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        manager = SessionManager(db_path)

        # Create session
        session1, _is_new1 = manager.get_or_create_session(
            model_name='test-model',
            max_context_tokens=1000
        )
        session_id = session1['session_id']

        # Load same session
        session2, is_new2 = manager.get_or_create_session(
            session_id=session_id
        )

        assert is_new2 is False, "Session should not be newly created"
        assert session2['session_id'] == session_id, "Session IDs should match"

        manager.close()
        print("[OK] Load existing session works")

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_json_message_storage():
    """Test that messages are stored in JSON format."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        manager = SessionManager(db_path)

        # Create session
        session, _ = manager.get_or_create_session(model_name='test-model')

        # Update with exchange
        manager.update_session(
            session,
            "What is 2+2?",
            "2+2 equals 4."
        )

        # Close manager to ensure commit
        manager.close()

        # Load updated session
        db = SessionDatabase(db_path)
        updated_session = db.get_session(session['session_id'])

        # Parse history_json
        history = json.loads(updated_session['history_json'])
        messages = history['messages']

        assert len(messages) == 2, "Should have 2 messages (user + assistant)"
        assert messages[0]['role'] == 'user', "First message should be user"
        assert messages[0]['content'] == "What is 2+2?", "User content should match"
        assert messages[1]['role'] == 'assistant', "Second message should be assistant"
        assert messages[1]['content'] == "2+2 equals 4.", "Assistant content should match"

        # Check token estimates exist
        assert 'tokens' in messages[0], "User message should have token estimate"
        assert 'tokens' in messages[1], "Assistant message should have token estimate"

        # Check timestamps exist
        assert 'timestamp' in messages[0], "User message should have timestamp"
        assert 'timestamp' in messages[1], "Assistant message should have timestamp"

        db.close()
        manager.close()
        print("[OK] JSON message storage works")

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_cached_plain_text():
    """Test that context field contains cached plain text."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        manager = SessionManager(db_path)

        # Create session
        session, _ = manager.get_or_create_session(model_name='test-model')

        # Update with exchange
        manager.update_session(
            session,
            "Hello",
            "Hi there!"
        )

        # Close manager to ensure commit
        manager.close()

        # Load updated session
        db = SessionDatabase(db_path)
        updated_session = db.get_session(session['session_id'])

        # Check cached context
        context = updated_session['context']
        assert 'User: Hello' in context, "Context should contain user message"
        assert 'Assistant: Hi there!' in context, "Context should contain assistant message"

        db.close()
        manager.close()
        print("[OK] Cached plain text works")

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_prepare_prompt_with_context():
    """Test that prepare_prompt prepends session context."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        manager = SessionManager(db_path)

        # Create session and add context
        session, _ = manager.get_or_create_session(model_name='test-model')
        manager.update_session(session, "First question", "First answer")

        # Close manager to ensure commit
        manager.close()

        # Reload session to get updated context
        manager = SessionManager(db_path)
        db = SessionDatabase(db_path)
        updated_session = db.get_session(session['session_id'])

        # Prepare new prompt with context
        full_prompt = manager.prepare_prompt(updated_session, "Second question")

        assert 'User: First question' in full_prompt, "Should include previous user message"
        assert 'Assistant: First answer' in full_prompt, "Should include previous assistant message"
        assert 'User: Second question' in full_prompt, "Should include new user message"

        db.close()
        manager.close()
        print("[OK] Prepare prompt with context works")

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_context_pruning():
    """Test that context is pruned when approaching token limit."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        manager = SessionManager(db_path)

        # Create session with very small token limit
        session, _ = manager.get_or_create_session(
            model_name='test-model',
            max_context_tokens=100  # Very small for testing
        )

        # Add many exchanges to exceed limit
        for i in range(10):
            manager.update_session(
                session,
                f"Question {i}: " + ("x" * 50),  # Make it long
                f"Answer {i}: " + ("y" * 50)
            )

        # Close manager to ensure commit
        manager.close()

        # Reload session
        db = SessionDatabase(db_path)
        updated_session = db.get_session(session['session_id'])

        # Parse history to count messages
        history = json.loads(updated_session['history_json'])
        messages = history['messages']

        # Should have pruned some messages
        assert len(messages) < 20, "Should have pruned old messages (started with 20)"

        # Estimate tokens in context
        context_tokens = len(updated_session['context']) // 4
        assert context_tokens <= 100, f"Context should be under limit, got {context_tokens} tokens"

        db.close()
        manager.close()
        print(f"[OK] Context pruning works (pruned to {len(messages)} messages, {context_tokens} tokens)")

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_multiple_exchanges():
    """Test multiple exchanges maintain conversation history."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        manager = SessionManager(db_path)

        # Create session
        session, _ = manager.get_or_create_session(model_name='test-model')

        # Simulate conversation
        exchanges = [
            ("Hello", "Hi!"),
            ("How are you?", "I'm doing well, thanks!"),
            ("What's 2+2?", "4")
        ]

        for user_msg, assistant_msg in exchanges:
            manager.update_session(session, user_msg, assistant_msg)

        # Close manager to ensure commit
        manager.close()

        # Reload and verify
        db = SessionDatabase(db_path)
        updated_session = db.get_session(session['session_id'])

        history = json.loads(updated_session['history_json'])
        messages = history['messages']

        assert len(messages) == 6, "Should have 6 messages (3 exchanges)"

        # Verify order
        assert messages[0]['content'] == "Hello"
        assert messages[1]['content'] == "Hi!"
        assert messages[2]['content'] == "How are you?"
        assert messages[3]['content'] == "I'm doing well, thanks!"
        assert messages[4]['content'] == "What's 2+2?"
        assert messages[5]['content'] == "4"

        db.close()
        manager.close()
        print("[OK] Multiple exchanges work")

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def main():
    """Run all context persistence tests."""
    print("Running Context Persistence Tests...")
    print("-" * 60)

    tests = [
        test_auto_create_session,
        test_load_existing_session,
        test_json_message_storage,
        test_cached_plain_text,
        test_prepare_prompt_with_context,
        test_context_pruning,
        test_multiple_exchanges,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {test_func.__name__}: {e}")
            failed += 1

    print("-" * 60)
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
    else:
        print("\n[OK] All context persistence tests passed!")
        sys.exit(0)


if __name__ == '__main__':
    main()
