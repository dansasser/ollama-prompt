#!/usr/bin/env python3
import ollama
import argparse
import json
import os
import re

# Read up to this many bytes from referenced files to avoid blowing prompts.
DEFAULT_MAX_FILE_BYTES = 200_000

def safe_join_repo(repo_root, path):
    """Join path to repo_root and prevent path traversal outside repo_root."""
    # Allow absolute paths but enforce they reside inside repo_root
    if os.path.isabs(path):
        target = os.path.abspath(path)
    else:
        target = os.path.abspath(os.path.join(repo_root, path))
    repo_root_abs = os.path.abspath(repo_root)
    if not target.startswith(repo_root_abs):
        raise ValueError(f"path outside repo root: {path}")
    return target

def read_file_snippet(path, repo_root=".", max_bytes=DEFAULT_MAX_FILE_BYTES):
    """Safely read a file (bounded) and return its contents or an error string."""
    try:
        fp = safe_join_repo(repo_root, path)
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(max_bytes)
        # If file truncated, indicate that to the model so it doesn't assume full file.
        if os.path.getsize(fp) > len(content):
            content += "\n\n[TRUNCATED: file larger than max_bytes]\n"
        return {"ok": True, "path": path, "content": content}
    except Exception as e:
        return {"ok": False, "path": path, "error": str(e)}

def expand_file_refs_in_prompt(prompt, repo_root=".", max_bytes=DEFAULT_MAX_FILE_BYTES):
    """
    Find file-reference tokens in the prompt of the form @<path> and replace them
    with the file contents (bounded) wrapped in clear delimiters.

    Rules:
    - Token syntax: @<path-without-spaces>, e.g. @./README.md, @src/foo.py, @/absolute/path.md
    - If reading fails, an error note is inserted instead of silently dropping it.
    - Avoid replacing email-like @user tokens by requiring a path-like string (contains '/' or starts with ./ ../ or /).
    """
    # Regex: @ followed by a path-like token (no whitespace). Require either a slash or starting with ./ or ../ or /
    pattern = re.compile(r'@(?P<path>(?:\.\.[/\\]|\.[/\\]|[/\\])[^\s@]+|[^\s@]*[/\\][^\s@]+)')

    def _repl(m):
        path = m.group("path")
        res = read_file_snippet(path, repo_root=repo_root, max_bytes=max_bytes)
        if not res["ok"]:
            return f"\n\n--- FILE: {path} (ERROR: {res['error']}) ---\n"
        # Wrap with explicit markers so model can clearly see file boundaries.
        return (
            f"\n\n--- FILE: {path} START ---\n"
            f"{res['content']}\n"
            f"--- FILE: {path} END ---\n\n"
        )

    expanded = pattern.sub(_repl, prompt)
    return expanded

def main():
    parser = argparse.ArgumentParser(description="Send a prompt to local Ollama and get full verbose JSON response (just like PowerShell). Supports file refs like @./this-file.md which are inlined from the local repo before sending to the model.")
    parser.add_argument('--prompt', help="Prompt to send to the model. Use @path tokens to inline files (e.g. '@./README.md Explain this file'). Not required for utility commands.")
    parser.add_argument('--model', default="deepseek-v3.1:671b-cloud", help="Model name")
    parser.add_argument('--temperature', type=float, default=0.1, help="Sampling temperature")
    parser.add_argument('--max_tokens', type=int, default=2048, help="Max tokens for response")
    parser.add_argument('--repo-root', default='.', help="Repository root used to resolve @file references (default: current directory).")
    parser.add_argument('--max-file-bytes', type=int, default=DEFAULT_MAX_FILE_BYTES, help="Max bytes to read from each referenced file to avoid excessive prompts.")
    parser.add_argument('--think', action='store_true', help='Enable thinking mode for supported models')

    # Session management flags
    session_group = parser.add_argument_group('session management', 'Manage conversation context across multiple prompts')
    session_group.add_argument('--session-id', type=str, help='Continue existing session by ID')
    session_group.add_argument('--no-session', action='store_true', help='Run in stateless mode (no session stored)')
    session_group.add_argument('--max-context-tokens', type=int, help='Override max context tokens for this session (default: 64000)')

    # Utility command flags
    utility_group = parser.add_argument_group('session utilities', 'Manage stored sessions')
    utility_group.add_argument('--list-sessions', action='store_true', help='List all stored sessions and exit')
    utility_group.add_argument('--purge', type=int, metavar='DAYS', help='Remove sessions older than DAYS and exit')
    utility_group.add_argument('--session-info', type=str, metavar='ID', help='Show details for session ID and exit')

    args = parser.parse_args()

    # Argument validation
    if args.session_id and args.no_session:
        parser.error("--session-id and --no-session are mutually exclusive")

    # Check if utility command was requested
    utility_commands = [args.list_sessions, args.purge, args.session_info]
    if any(utility_commands):
        # Utility commands don't require --prompt
        if not args.prompt:
            # Make --prompt optional for utility commands by setting empty default
            args.prompt = None
        # Route to utility command handler
        from .session_utils import handle_utility_command
        handle_utility_command(args)
        return

    # If not a utility command, --prompt is required
    if not args.prompt:
        parser.error("--prompt is required for normal operation")

    # Expand file references like @./path/to/file before calling the model.
    try:
        prompt_with_files = expand_file_refs_in_prompt(args.prompt, repo_root=args.repo_root, max_bytes=args.max_file_bytes)
    except Exception as e:
        print(json.dumps({"error": f"failed to expand file refs: {e}"}))
        return

    options = {
        "temperature": args.temperature,
        "num_predict": args.max_tokens
    }

    if args.think:
        options['think'] = True

    result = ollama.generate(
        model=args.model,
        prompt=prompt_with_files,
        options=options,
        stream=False
    )

    # Convert Pydantic to dict (matches PowerShell's ConvertTo-Json)
    result_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    print(json.dumps(result_dict, indent=2))


if __name__ == "__main__":
    main()