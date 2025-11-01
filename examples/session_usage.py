#!/usr/bin/env python3
"""
Session Management Examples for ollama-prompt

This file demonstrates practical use cases for session management:
1. Multi-turn conversations
2. Code review across multiple files
3. Iterative problem solving
4. Session management and cleanup
"""

import subprocess
import json
import sys
from pathlib import Path


def run_ollama_prompt(prompt, session_id=None, no_session=False, model="deepseek-v3.1:671b-cloud"):
    """
    Helper function to run ollama-prompt and return parsed JSON output.

    Args:
        prompt: The prompt to send
        session_id: Optional session ID to continue conversation
        no_session: If True, run in stateless mode
        model: Model to use (default: deepseek-v3.1:671b-cloud)

    Returns:
        dict: Parsed JSON response from ollama-prompt
    """
    cmd = ["ollama-prompt", "--prompt", prompt, "--model", model]

    if session_id:
        cmd.extend(["--session-id", session_id])
    if no_session:
        cmd.append("--no-session")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running ollama-prompt: {e.stderr}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        return None


def example_1_multi_turn_conversation():
    """
    Example 1: Multi-turn conversation with automatic context.

    Demonstrates:
    - Auto-creation of sessions
    - Using session_id to continue conversation
    - Context preservation across multiple exchanges
    """
    print("=" * 60)
    print("Example 1: Multi-Turn Conversation")
    print("=" * 60)

    # First question - creates new session
    print("\n[1] Asking: Who wrote Romeo and Juliet?")
    response1 = run_ollama_prompt("Who wrote Romeo and Juliet?")

    if not response1:
        return

    session_id = response1.get('session_id')
    print(f"[OK] Session created: {session_id}")
    print(f"[OK] Response: {response1['response'][:100]}...")

    # Second question - uses context from first
    print(f"\n[2] Asking: When was he born? (session: {session_id})")
    response2 = run_ollama_prompt("When was he born?", session_id=session_id)

    if response2:
        print(f"[OK] Response: {response2['response'][:100]}...")
        print("[OK] Model understood 'he' refers to Shakespeare from previous context!")

    # Third question - continues conversation
    print(f"\n[3] Asking: What other plays did he write? (session: {session_id})")
    response3 = run_ollama_prompt("What other plays did he write?", session_id=session_id)

    if response3:
        print(f"[OK] Response: {response3['response'][:150]}...")
        print("[OK] Full conversation history maintained across 3 exchanges!")

    print(f"\n[OK] Example 1 complete. Session ID: {session_id}")


def example_2_code_review_session():
    """
    Example 2: Code review across multiple files with shared context.

    Demonstrates:
    - Using @file references
    - Maintaining code review context
    - Cross-file analysis
    """
    print("\n" + "=" * 60)
    print("Example 2: Code Review Session")
    print("=" * 60)

    # Note: This example assumes you have Python files to review
    # Adjust paths as needed for your environment

    # Start code review
    print("\n[1] Starting code review session...")
    response1 = run_ollama_prompt(
        "I'm starting a code review. Please analyze the following Python module for security issues and best practices."
    )

    if not response1:
        print("[SKIP] Skipping example - ollama-prompt not available")
        return

    session_id = response1.get('session_id')
    print(f"[OK] Review session created: {session_id}")

    # Review specific file (if it exists)
    example_file = Path("ollama_prompt/cli.py")
    if example_file.exists():
        print(f"\n[2] Reviewing {example_file}...")
        response2 = run_ollama_prompt(
            f"@./{example_file} Review this file for potential issues.",
            session_id=session_id
        )

        if response2:
            print(f"[OK] Review complete: {response2['response'][:150]}...")

    print(f"\n[OK] Example 2 complete. Session ID: {session_id}")


def example_3_iterative_problem_solving():
    """
    Example 3: Iterative problem solving with refinement.

    Demonstrates:
    - Building on previous answers
    - Refining solutions iteratively
    - Context helping with follow-up questions
    """
    print("\n" + "=" * 60)
    print("Example 3: Iterative Problem Solving")
    print("=" * 60)

    # Initial problem
    print("\n[1] Asking: How do I sort a list in Python?")
    response1 = run_ollama_prompt("How do I sort a list in Python?")

    if not response1:
        return

    session_id = response1.get('session_id')
    print(f"[OK] Initial answer received (session: {session_id})")
    print(f"[OK] Response: {response1['response'][:100]}...")

    # Refine with constraints
    print(f"\n[2] Refining: What if I need it case-insensitive? (session: {session_id})")
    response2 = run_ollama_prompt(
        "What if I need the sort to be case-insensitive?",
        session_id=session_id
    )

    if response2:
        print(f"[OK] Refined answer: {response2['response'][:100]}...")

    # Add more requirements
    print(f"\n[3] Adding requirement: And handle numbers? (session: {session_id})")
    response3 = run_ollama_prompt(
        "And what if my list contains both strings and numbers?",
        session_id=session_id
    )

    if response3:
        print(f"[OK] Final solution: {response3['response'][:150]}...")
        print("[OK] Solution evolved iteratively with full context!")

    print(f"\n[OK] Example 3 complete. Session ID: {session_id}")


def example_4_session_management():
    """
    Example 4: Session management utilities.

    Demonstrates:
    - Listing sessions
    - Getting session info
    - Cleaning up old sessions
    """
    print("\n" + "=" * 60)
    print("Example 4: Session Management")
    print("=" * 60)

    # List all sessions
    print("\n[1] Listing all sessions...")
    result = subprocess.run(
        ["ollama-prompt", "--list-sessions"],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )

    if result.returncode == 0:
        sessions = json.loads(result.stdout)
        print(f"[OK] Found {sessions['total']} sessions")

        if sessions['total'] > 0:
            # Show info for first session
            first_session = sessions['sessions'][0]
            session_id = first_session['session_id']

            print(f"\n[2] Getting info for session: {session_id}")
            result = subprocess.run(
                ["ollama-prompt", "--session-info", session_id],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )

            if result.returncode == 0:
                info = json.loads(result.stdout)
                print(f"[OK] Session has {info['message_count']} messages")
                print(f"[OK] Using {info['context_tokens']} tokens ({info['context_usage_percent']:.1f}% of limit)")

    # Demonstrate cleanup (commented out to avoid deleting sessions)
    print("\n[3] Session cleanup (example - not executed):")
    print("    ollama-prompt --purge 30  # Remove sessions older than 30 days")

    print("\n[OK] Example 4 complete.")


def example_5_stateless_mode():
    """
    Example 5: Stateless mode for one-off queries.

    Demonstrates:
    - Using --no-session flag
    - When stateless mode is appropriate
    - No database overhead
    """
    print("\n" + "=" * 60)
    print("Example 5: Stateless Mode")
    print("=" * 60)

    # Quick lookup that doesn't need context
    print("\n[1] Quick lookup (no session)...")
    response = run_ollama_prompt(
        "What is the capital of France?",
        no_session=True
    )

    if response:
        print(f"[OK] Response: {response['response'][:100]}...")
        print("[OK] No session_id in response - no database storage!")
        assert 'session_id' not in response, "Stateless mode should not create session"

    # Another independent query
    print("\n[2] Another quick query (no session)...")
    response2 = run_ollama_prompt(
        "What is 2+2?",
        no_session=True
    )

    if response2:
        print(f"[OK] Response: {response2['response'][:100]}...")
        print("[OK] Independent query - no context from previous question")

    print("\n[OK] Example 5 complete. No sessions created!")


def main():
    """Run all examples."""
    print("\n")
    print("#" * 60)
    print("# ollama-prompt Session Management Examples")
    print("#" * 60)
    print("\nThese examples demonstrate practical session management use cases.")
    print("Make sure ollama-prompt is installed and Ollama server is running.")
    print("\n")

    try:
        # Run all examples
        example_1_multi_turn_conversation()
        example_2_code_review_session()
        example_3_iterative_problem_solving()
        example_4_session_management()
        example_5_stateless_mode()

        print("\n" + "#" * 60)
        print("# All examples completed successfully!")
        print("#" * 60)
        print("\nFor more information, see:")
        print("  - docs/sessions/session-management.md - Comprehensive guide")
        print("  - README.md - Quick start and overview")

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Examples stopped by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
