#!/usr/bin/env python3
"""
Integration tests for CLI argument parsing and utility commands.

Tests cover:
1. Session flag parsing (--session-id, --no-session, --max-context-tokens)
2. Utility command routing (--list-sessions, --purge, --session-info)
3. Argument validation (mutual exclusivity)
4. Help output
"""
import subprocess
import json
import sys
import os
import tempfile


def run_cli(*args):
    """
    Run ollama-prompt CLI with given arguments.

    Returns:
        tuple: (return_code, stdout, stderr)
    """
    # Use the installed ollama-prompt command directly
    # This works better than python -m since the package is installed
    cmd = ['ollama-prompt'] + list(args)

    # Create isolated temp database for each test run
    temp_dir = tempfile.mkdtemp()
    temp_db_path = os.path.join(temp_dir, 'test_sessions.db')

    # Set up environment with isolated DB path
    env = os.environ.copy()
    env['OLLAMA_PROMPT_DB_PATH'] = temp_db_path

    # Run from current directory with isolated environment
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        env=env
    )
    return result.returncode, result.stdout, result.stderr


def test_help_output():
    """Test that --help shows all session flags."""
    returncode, stdout, stderr = run_cli('--help')

    assert returncode == 0, f"--help should succeed, got: {stderr}"
    assert '--session-id' in stdout, "Help should show --session-id flag"
    assert '--no-session' in stdout, "Help should show --no-session flag"
    assert '--max-context-tokens' in stdout, "Help should show --max-context-tokens flag"
    assert '--list-sessions' in stdout, "Help should show --list-sessions flag"
    assert '--purge' in stdout, "Help should show --purge flag"
    assert '--session-info' in stdout, "Help should show --session-info flag"
    assert 'session management' in stdout.lower(), "Help should show session management group"
    assert 'session utilities' in stdout.lower(), "Help should show session utilities group"

    print("[OK] Help output contains all session flags")


def test_list_sessions_utility():
    """Test --list-sessions utility command works without --prompt."""
    returncode, stdout, stderr = run_cli('--list-sessions')

    assert returncode == 0, f"--list-sessions should succeed, got: {stderr}"

    # Parse JSON output
    try:
        output = json.loads(stdout)
        assert 'sessions' in output, "Output should contain 'sessions' key"
        assert 'total' in output, "Output should contain 'total' key"
        assert isinstance(output['sessions'], list), "sessions should be a list"
        assert isinstance(output['total'], int), "total should be an int"
        print(f"[OK] --list-sessions works: {output['total']} sessions found")
    except json.JSONDecodeError as e:
        raise AssertionError(f"Output is not valid JSON: {stdout}") from e


def test_mutual_exclusivity():
    """Test that --session-id and --no-session are mutually exclusive."""
    returncode, stdout, stderr = run_cli(
        '--prompt', 'test',
        '--session-id', 'abc123',
        '--no-session'
    )

    assert returncode != 0, "--session-id and --no-session should be mutually exclusive"
    assert 'mutually exclusive' in stderr.lower(), f"Error message should mention mutual exclusivity, got: {stderr}"

    print("[OK] Mutual exclusivity validation works")


def test_prompt_required_for_normal_operation():
    """Test that --prompt is required when not using utility commands."""
    returncode, stdout, stderr = run_cli('--model', 'deepseek-v3.1:671b-cloud')

    assert returncode != 0, "--prompt should be required for normal operation"
    assert 'required' in stderr.lower() or 'prompt' in stderr.lower(), \
        f"Error should mention prompt is required, got: {stderr}"

    print("[OK] --prompt requirement validation works")


def test_prompt_not_required_for_utility_commands():
    """Test that --prompt is NOT required when using utility commands."""
    # --list-sessions should work without --prompt
    returncode, stdout, stderr = run_cli('--list-sessions')
    assert returncode == 0, f"--list-sessions should work without --prompt, got: {stderr}"

    print("[OK] Utility commands work without --prompt")


def test_session_id_flag_parsing():
    """Test that --session-id flag is parsed correctly."""
    # This test just checks parsing - it won't actually run the model
    # since we don't want to make real API calls in tests

    # We can't fully test this without mocking ollama.generate(),
    # but we can at least verify the flag is accepted without errors
    # by checking help or using utility commands

    returncode, stdout, stderr = run_cli('--help')
    assert returncode == 0, "Help should work"
    assert '--session-id SESSION_ID' in stdout, "--session-id should accept SESSION_ID argument"

    print("[OK] --session-id flag parsing looks correct")


def test_max_context_tokens_flag_parsing():
    """Test that --max-context-tokens flag is parsed correctly."""
    returncode, stdout, stderr = run_cli('--help')
    assert returncode == 0, "Help should work"
    assert '--max-context-tokens MAX_CONTEXT_TOKENS' in stdout, \
        "--max-context-tokens should accept MAX_CONTEXT_TOKENS argument"

    print("[OK] --max-context-tokens flag parsing looks correct")


def test_purge_flag_format():
    """Test that --purge flag accepts DAYS argument."""
    returncode, stdout, stderr = run_cli('--help')
    assert returncode == 0, "Help should work"
    assert '--purge DAYS' in stdout, "--purge should accept DAYS argument"

    print("[OK] --purge flag format looks correct")


def test_session_info_flag_format():
    """Test that --session-info flag accepts ID argument."""
    returncode, stdout, stderr = run_cli('--help')
    assert returncode == 0, "Help should work"
    assert '--session-info ID' in stdout, "--session-info should accept ID argument"

    print("[OK] --session-info flag format looks correct")


def main():
    """Run all CLI integration tests."""
    print("Running CLI Integration Tests...")
    print("-" * 60)

    tests = [
        test_help_output,
        test_list_sessions_utility,
        test_mutual_exclusivity,
        test_prompt_required_for_normal_operation,
        test_prompt_not_required_for_utility_commands,
        test_session_id_flag_parsing,
        test_max_context_tokens_flag_parsing,
        test_purge_flag_format,
        test_session_info_flag_format,
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
        print("\n[OK] All CLI integration tests passed!")
        sys.exit(0)


if __name__ == '__main__':
    main()
