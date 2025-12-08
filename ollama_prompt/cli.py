#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys

import ollama
# Import secure file reading (TOCTOU-safe, symlink-blocking)
# Now using llm-filesystem-tools package for production-ready security
from llm_fs_tools import (DEFAULT_MAX_FILE_BYTES, create_directory_tools,
                          read_file_secure)

# Maximum prompt size to prevent ReDoS and resource exhaustion
MAX_PROMPT_SIZE = 10_000_000  # 10MB


def validate_model_name(model: str) -> str:
    """
    Validate model name format to prevent injection attacks.

    Args:
        model: Model name to validate

    Returns:
        str: Validated model name

    Raises:
        ValueError: If model name format is invalid
    """
    if not model:
        raise ValueError("Model name cannot be empty")

    # SECURITY: Allow only safe characters for model names
    # Format: alphanumeric, dots, hyphens, underscores, colons (for tags)
    if not re.match(r"^[a-zA-Z0-9._:-]+$", model):
        raise ValueError(
            f"Invalid model name format: '{model}'. "
            "Only alphanumeric characters, dots, hyphens, underscores, and colons are allowed."
        )

    # Prevent excessively long model names
    MAX_MODEL_NAME_LENGTH = 100
    if len(model) > MAX_MODEL_NAME_LENGTH:
        raise ValueError(
            f"Model name too long: {len(model)} characters (maximum {MAX_MODEL_NAME_LENGTH})"
        )

    return model


def safe_join_repo(repo_root, path):
    """Join path to repo_root and prevent path traversal outside repo_root."""
    # Allow absolute paths but enforce they reside inside repo_root
    if os.path.isabs(path):
        target = os.path.abspath(path)
    else:
        target = os.path.abspath(os.path.join(repo_root, path))

    # Resolve and normalize both paths
    try:
        repo_root_resolved = os.path.realpath(os.path.abspath(repo_root))
        target_resolved = os.path.realpath(target)

        # On Windows, normalize case for comparison
        if os.name == "nt":
            repo_root_resolved = os.path.normcase(repo_root_resolved)
            target_resolved = os.path.normcase(target_resolved)

        # Use commonpath to verify containment
        common = os.path.commonpath([repo_root_resolved, target_resolved])
        if common != repo_root_resolved:
            raise ValueError(f"path outside repo root: {path}")
    except (ValueError, OSError) as e:
        # Propagate path resolution errors
        raise ValueError(f"path outside repo root: {path}") from e

    return target


def read_file_snippet(path, repo_root=".", max_bytes=DEFAULT_MAX_FILE_BYTES):
    """
    Safely read a file (bounded) and return its contents or an error string.

    SECURITY: Uses TOCTOU-safe file reading with:
    - Symlink blocking at open time (O_NOFOLLOW on Unix)
    - File type validation (rejects devices, FIFOs, sockets)
    - Path containment validated AFTER opening (eliminates race condition)
    - Audit logging of all file access attempts
    """
    return read_file_secure(path, repo_root, max_bytes, audit=True)


def list_directory(path, repo_root="."):
    """
    List directory contents securely.

    Args:
        path: Directory path to list (relative to repo_root)
        repo_root: Repository root for security validation

    Returns:
        Dict with ok, path, content (formatted listing) or error
    """
    try:
        # Resolve path relative to repo_root
        abs_repo = os.path.abspath(repo_root)
        if path in (".", "./", ".\\"):
            target_dir = abs_repo
        else:
            # Strip leading ./ or .\ prefix
            if path.startswith("./"):
                clean_path = path[2:]
            elif path.startswith(".\\"):
                clean_path = path[2:]
            else:
                clean_path = path
            target_dir = os.path.join(abs_repo, clean_path)

        tools = create_directory_tools(abs_repo)
        result = tools.list_directory(target_dir)

        if result["success"]:
            entries = result["data"]["entries"]
            # Format as readable listing
            lines = []
            for entry in sorted(
                entries, key=lambda e: (e["type"] != "directory", e["name"])
            ):
                if entry["type"] == "directory":
                    lines.append(f"  [DIR]  {entry['name']}/")
                else:
                    size = entry.get("size", 0)
                    lines.append(f"  [FILE] {entry['name']} ({size} bytes)")

            content = (
                f"Directory: {path}\n" + "\n".join(lines)
                if lines
                else f"Directory: {path}\n  (empty)"
            )
            return {"ok": True, "path": path, "content": content}
        else:
            return {
                "ok": False,
                "path": path,
                "error": result.get("error", "Unknown error"),
            }
    except Exception as e:
        return {"ok": False, "path": path, "error": str(e)}


def get_directory_tree(path, repo_root=".", max_depth=3):
    """
    Get hierarchical directory tree securely.

    Args:
        path: Directory path for tree root (relative to repo_root)
        repo_root: Repository root for security validation
        max_depth: Maximum recursion depth

    Returns:
        Dict with ok, path, content (formatted tree) or error
    """
    try:
        # Resolve path relative to repo_root
        abs_repo = os.path.abspath(repo_root)
        if path in (".", "./", ".\\"):
            target_dir = abs_repo
        else:
            # Strip leading ./ or .\ prefix
            if path.startswith("./"):
                clean_path = path[2:]
            elif path.startswith(".\\"):
                clean_path = path[2:]
            else:
                clean_path = path
            target_dir = os.path.join(abs_repo, clean_path)

        tools = create_directory_tools(abs_repo)
        result = tools.get_directory_tree(target_dir, max_depth=max_depth)

        if result["success"]:
            # Format tree recursively
            def format_tree(node, prefix="", is_last=True):
                lines = []
                connector = "`-- " if is_last else "|-- "
                name = node["name"]
                if node["type"] == "directory":
                    name += "/"

                lines.append(f"{prefix}{connector}{name}")

                if "children" in node and node["children"]:
                    children = sorted(
                        node["children"],
                        key=lambda c: (c["type"] != "directory", c["name"]),
                    )
                    for i, child in enumerate(children):
                        is_child_last = i == len(children) - 1
                        extension = "    " if is_last else "|   "
                        lines.extend(
                            format_tree(child, prefix + extension, is_child_last)
                        )

                return lines

            tree_data = result["data"]
            tree_lines = [f"{tree_data['name']}/"]
            if "children" in tree_data and tree_data["children"]:
                children = sorted(
                    tree_data["children"],
                    key=lambda c: (c["type"] != "directory", c["name"]),
                )
                for i, child in enumerate(children):
                    is_last = i == len(children) - 1
                    tree_lines.extend(format_tree(child, "", is_last))

            content = "\n".join(tree_lines)
            return {"ok": True, "path": path, "content": content}
        else:
            return {
                "ok": False,
                "path": path,
                "error": result.get("error", "Unknown error"),
            }
    except Exception as e:
        return {"ok": False, "path": path, "error": str(e)}


def search_directory(path, pattern, repo_root=".", max_results=50):
    """
    Search for pattern in files within directory.

    Args:
        path: Directory path to search in (relative to repo_root)
        pattern: Regex pattern to search for
        repo_root: Repository root for security validation
        max_results: Maximum number of results

    Returns:
        Dict with ok, path, content (formatted results) or error
    """
    try:
        # Resolve path relative to repo_root
        abs_repo = os.path.abspath(repo_root)
        if path in (".", "./", ".\\"):
            target_dir = abs_repo
        else:
            # Strip leading ./ or .\ prefix
            if path.startswith("./"):
                clean_path = path[2:]
            elif path.startswith(".\\"):
                clean_path = path[2:]
            else:
                clean_path = path
            target_dir = os.path.join(abs_repo, clean_path)

        tools = create_directory_tools(abs_repo)
        result = tools.search_codebase(pattern, target_dir, max_results=max_results)

        if result["success"]:
            matches = result["data"]["matches"]
            if not matches:
                content = f"Search: '{pattern}' in {path}\n  No matches found."
            else:
                lines = [f"Search: '{pattern}' in {path} ({len(matches)} matches)"]
                for match in matches:
                    file_path = match.get("file", "unknown")
                    line_num = match.get("line", "?")
                    line_text = match.get("content", "").strip()
                    lines.append(f"  {file_path}:{line_num}: {line_text}")
                content = "\n".join(lines)

            return {"ok": True, "path": path, "content": content}
        else:
            return {
                "ok": False,
                "path": path,
                "error": result.get("error", "Unknown error"),
            }
    except Exception as e:
        return {"ok": False, "path": path, "error": str(e)}


def expand_file_refs_in_prompt(prompt, repo_root=".", max_bytes=DEFAULT_MAX_FILE_BYTES):
    """
    Find file/directory reference tokens in the prompt and replace them
    with contents wrapped in clear delimiters.

    File syntax:
    - @./path/to/file.py - Read file contents
    - @src/foo.py - Read file contents

    Directory syntax:
    - @./dir/ or @./dir/:list - List directory contents
    - @./dir/:tree - Show directory tree (depth=3)
    - @./dir/:search:PATTERN - Search for pattern in directory

    Rules:
    - If reading fails, an error note is inserted instead of silently dropping it.
    - Avoid replacing email-like @user tokens by requiring a path-like string.

    Raises:
        ValueError: If prompt exceeds maximum allowed size
    """
    # SECURITY: Prevent ReDoS and resource exhaustion with size limit
    if len(prompt) > MAX_PROMPT_SIZE:
        raise ValueError(
            f"Prompt too large: {len(prompt)} bytes (maximum {MAX_PROMPT_SIZE} bytes)"
        )

    # Pattern matches: @./ or @../ or @/ followed by valid path characters
    # Now also captures optional :command:arg suffixes for directory operations
    # Excludes: whitespace, @, and common sentence-ending punctuation (?!,;)
    pattern = re.compile(r"@((?:\.\.?[/\\]|[/\\])[^\s@?!,;]+)")

    def _repl(m):
        full_ref = m.group(1)

        # Check for directory operation syntax: path/:command or path/:command:arg
        # First, handle :search:pattern (must check before :tree/:list)
        if ":search:" in full_ref:
            parts = full_ref.split(":search:", 1)
            dir_path = parts[0].rstrip("/\\")
            search_pattern = parts[1] if len(parts) > 1 else ""
            if not search_pattern:
                return f"\n\n--- DIRECTORY: {dir_path} (ERROR: :search requires a pattern) ---\n"
            res = search_directory(dir_path, search_pattern, repo_root=repo_root)
            label = f"SEARCH: '{search_pattern}' in {dir_path}"

        elif full_ref.endswith(":tree"):
            dir_path = full_ref[:-5].rstrip("/\\")  # Remove :tree
            res = get_directory_tree(dir_path, repo_root=repo_root)
            label = f"TREE: {dir_path}"

        elif full_ref.endswith(":list"):
            dir_path = full_ref[:-5].rstrip("/\\")  # Remove :list
            res = list_directory(dir_path, repo_root=repo_root)
            label = f"DIRECTORY: {dir_path}"

        elif full_ref.endswith("/") or full_ref.endswith("\\"):
            # Trailing slash = directory listing
            dir_path = full_ref.rstrip("/\\")
            res = list_directory(dir_path, repo_root=repo_root)
            label = f"DIRECTORY: {dir_path}"

        else:
            # Regular file reference
            path = full_ref
            res = read_file_snippet(path, repo_root=repo_root, max_bytes=max_bytes)
            label = f"FILE: {path}"

        if not res["ok"]:
            return f"\n\n--- {label} (ERROR: {res['error']}) ---\n"

        # Wrap with explicit markers so model can clearly see boundaries
        return (
            f"\n\n--- {label} START ---\n"
            f"{res['content']}\n"
            f"--- {label} END ---\n\n"
        )

    expanded = pattern.sub(_repl, prompt)
    return expanded


def main():
    parser = argparse.ArgumentParser(
        description="Send a prompt to local Ollama and get full verbose JSON response (just like PowerShell). Supports file refs like @./this-file.md which are inlined from the local repo before sending to the model."
    )
    parser.add_argument(
        "--prompt",
        help="Prompt to send to the model. Use @path tokens to inline files (e.g. '@./README.md Explain this file'). Not required for utility commands.",
    )
    parser.add_argument(
        "--model", default="deepseek-v3.1:671b-cloud", help="Model name"
    )
    parser.add_argument(
        "--temperature", type=float, default=0.1, help="Sampling temperature"
    )
    parser.add_argument(
        "--max_tokens", type=int, default=2048, help="Max tokens for response"
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used to resolve @file references (default: current directory).",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=DEFAULT_MAX_FILE_BYTES,
        help="Max bytes to read from each referenced file to avoid excessive prompts.",
    )
    parser.add_argument(
        "--think", action="store_true", help="Enable thinking mode for supported models"
    )

    # Session management flags
    session_group = parser.add_argument_group(
        "session management", "Manage conversation context across multiple prompts"
    )
    session_group.add_argument(
        "--session-id", type=str, help="Continue existing session by ID"
    )
    session_group.add_argument(
        "--no-session",
        action="store_true",
        help="Run in stateless mode (no session stored)",
    )
    session_group.add_argument(
        "--max-context-tokens",
        type=int,
        help="Override max context tokens for this session (default: 64000)",
    )

    # Utility command flags
    utility_group = parser.add_argument_group(
        "session utilities", "Manage stored sessions"
    )
    utility_group.add_argument(
        "--list-sessions", action="store_true", help="List all stored sessions and exit"
    )
    utility_group.add_argument(
        "--purge",
        type=int,
        metavar="DAYS",
        help="Remove sessions older than DAYS and exit",
    )
    utility_group.add_argument(
        "--session-info",
        type=str,
        metavar="ID",
        help="Show details for session ID and exit",
    )

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

    # Validate model name to prevent injection attacks
    try:
        args.model = validate_model_name(args.model)
    except ValueError as e:
        parser.error(str(e))

    # Expand file references like @./path/to/file before calling the model.
    try:
        prompt_with_files = expand_file_refs_in_prompt(
            args.prompt, repo_root=args.repo_root, max_bytes=args.max_file_bytes
        )
    except Exception as e:
        print(
            json.dumps({"error": f"failed to expand file refs: {e}"}), file=sys.stderr
        )
        sys.exit(1)

    # Session management
    session = None
    session_manager = None
    if not args.no_session:
        from .session_manager import SessionManager

        session_manager = SessionManager()

        try:
            # Get or create session
            session, is_new = session_manager.get_or_create_session(
                session_id=args.session_id,
                model_name=args.model,
                max_context_tokens=args.max_context_tokens,
            )

            # Prepare prompt with session context
            prompt_with_context = session_manager.prepare_prompt(
                session, prompt_with_files
            )
        except Exception as e:
            print(
                json.dumps({"error": f"session management failed: {e}"}),
                file=sys.stderr,
            )
            if session_manager:
                session_manager.close()
            sys.exit(1)
    else:
        # Stateless mode - no session
        prompt_with_context = prompt_with_files

    options = {"temperature": args.temperature, "num_predict": args.max_tokens}

    if args.think:
        options["think"] = True

    result = ollama.generate(
        model=args.model, prompt=prompt_with_context, options=options, stream=False
    )

    # Update session after response
    if session_manager and session:
        try:
            session_manager.update_session(
                session, prompt_with_files, result["response"]
            )
        except Exception as e:
            print(
                json.dumps({"error": f"failed to update session: {e}"}), file=sys.stderr
            )
        finally:
            session_manager.close()

    # Convert Pydantic to dict (matches PowerShell's ConvertTo-Json)
    result_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)

    # Add session_id to output if session was used
    if session:
        result_dict["session_id"] = session["session_id"]

    print(json.dumps(result_dict, indent=2))


if __name__ == "__main__":
    main()
