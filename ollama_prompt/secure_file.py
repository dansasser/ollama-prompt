#!/usr/bin/env python3
"""
Secure file reading with TOCTOU protection.

Security features:
- Opens file FIRST, then validates (eliminates TOCTOU race condition)
- Blocks symlinks at open time (O_NOFOLLOW on Unix)
- Validates file type (rejects device files, FIFOs, sockets)
- Cross-platform support (Windows + Unix)
- Optional audit logging
"""

import os
import stat
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable

# Configure audit logger
audit_logger = logging.getLogger("ollama_prompt.file_audit")

# Default maximum bytes to read
DEFAULT_MAX_FILE_BYTES = 200_000


def _is_regular_file(mode: int) -> bool:
    """Check if file mode indicates a regular file."""
    return stat.S_ISREG(mode)


def _get_open_flags() -> int:
    """Get platform-appropriate open flags for secure file reading."""
    flags = os.O_RDONLY

    # On Unix, add O_NOFOLLOW to block symlinks at open time
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW

    # On Unix, add O_NOCTTY to prevent terminal hijacking
    if hasattr(os, 'O_NOCTTY'):
        flags |= os.O_NOCTTY

    # On Unix, add O_NONBLOCK to prevent blocking on FIFOs/pipes
    if hasattr(os, 'O_NONBLOCK'):
        flags |= os.O_NONBLOCK

    return flags


def _resolve_fd_path(fd: int) -> Optional[str]:
    """
    Get the real path of an open file descriptor.

    This is used for TOCTOU-safe path validation - we validate
    the path AFTER opening, using the actual opened file.

    Args:
        fd: Open file descriptor

    Returns:
        Resolved path or None if unavailable
    """
    try:
        # Linux: /proc/self/fd/N
        proc_path = f"/proc/self/fd/{fd}"
        if os.path.exists(proc_path):
            return os.path.realpath(proc_path)

        # macOS/BSD: Use fcntl F_GETPATH (not available in Python stdlib)
        # Fall back to fstat device/inode comparison

        # Windows: Use GetFinalPathNameByHandle via ctypes
        if sys.platform == 'win32':
            return _get_windows_fd_path(fd)

    except (OSError, IOError):
        pass

    return None


def _get_windows_fd_path(fd: int) -> Optional[str]:
    """Get the real path of a file descriptor on Windows."""
    try:
        import ctypes
        from ctypes import wintypes

        # Get handle from fd
        import msvcrt
        handle = msvcrt.get_osfhandle(fd)

        # GetFinalPathNameByHandleW
        kernel32 = ctypes.windll.kernel32
        GetFinalPathNameByHandleW = kernel32.GetFinalPathNameByHandleW
        GetFinalPathNameByHandleW.argtypes = [
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD
        ]
        GetFinalPathNameByHandleW.restype = wintypes.DWORD

        # VOLUME_NAME_DOS = 0x0
        buffer = ctypes.create_unicode_buffer(512)
        result = GetFinalPathNameByHandleW(handle, buffer, 512, 0)

        if result > 0:
            path = buffer.value
            # Remove \\?\ prefix if present
            if path.startswith("\\\\?\\"):
                path = path[4:]
            return path

    except (ImportError, OSError, ValueError):
        pass

    return None


def _validate_path_containment(resolved_path: str, allowed_root: str) -> bool:
    """
    Check if resolved path is contained within allowed root.

    Args:
        resolved_path: Absolute resolved path of the opened file
        allowed_root: Allowed root directory

    Returns:
        True if path is within allowed root
    """
    try:
        # Resolve the allowed root
        root_resolved = os.path.realpath(os.path.abspath(allowed_root))

        # Normalize case on Windows
        if os.name == 'nt':
            root_resolved = os.path.normcase(root_resolved)
            resolved_path = os.path.normcase(resolved_path)

        # Check containment using commonpath
        common = os.path.commonpath([root_resolved, resolved_path])
        return common == root_resolved

    except (ValueError, OSError):
        return False


def secure_open(
    path: str,
    repo_root: str = ".",
    audit: bool = True
) -> Dict[str, Any]:
    """
    Securely open a file with TOCTOU protection.

    Security features:
    1. Opens with O_NOFOLLOW (blocks symlinks at open time on Unix)
    2. Validates file type via fstat (rejects devices, FIFOs, sockets)
    3. Validates path containment AFTER opening (eliminates TOCTOU)

    Args:
        path: Path to file (relative or absolute)
        repo_root: Allowed root directory
        audit: Whether to log access attempts

    Returns:
        Dict with:
        - ok: bool - Whether open succeeded
        - fd: int - File descriptor (if ok=True)
        - resolved_path: str - Resolved path (if ok=True)
        - error: str - Error message (if ok=False)
        - blocked_reason: str - Security reason for block (if applicable)
    """
    fd = None
    resolved_path = None

    try:
        # Step 1: Compute target path (minimal validation)
        if os.path.isabs(path):
            target = os.path.abspath(path)
        else:
            target = os.path.abspath(os.path.join(repo_root, path))

        # Step 2: Open file with security flags
        # This is where symlinks are blocked (O_NOFOLLOW)
        flags = _get_open_flags()

        try:
            fd = os.open(target, flags)
        except OSError as e:
            # Check if it was a symlink block
            if hasattr(os, 'O_NOFOLLOW') and e.errno == 40:  # ELOOP - too many symlinks
                reason = "symlink blocked"
                if audit:
                    audit_logger.warning(
                        f"BLOCKED: {path} -> symlink detected (O_NOFOLLOW)"
                    )
                return {
                    "ok": False,
                    "path": path,
                    "error": f"Symlink not allowed: {path}",
                    "blocked_reason": reason
                }
            raise

        # Step 3: Validate file type via fstat (TOCTOU-safe)
        file_stat = os.fstat(fd)

        if not _is_regular_file(file_stat.st_mode):
            os.close(fd)
            fd = None

            # Determine what type it is for better error message
            if stat.S_ISDIR(file_stat.st_mode):
                file_type = "directory"
            elif stat.S_ISLNK(file_stat.st_mode):
                file_type = "symlink"
            elif stat.S_ISFIFO(file_stat.st_mode):
                file_type = "FIFO/pipe"
            elif stat.S_ISSOCK(file_stat.st_mode):
                file_type = "socket"
            elif stat.S_ISBLK(file_stat.st_mode):
                file_type = "block device"
            elif stat.S_ISCHR(file_stat.st_mode):
                file_type = "character device"
            else:
                file_type = "non-regular file"

            reason = f"invalid file type: {file_type}"
            if audit:
                audit_logger.warning(
                    f"BLOCKED: {path} -> {file_type} not allowed"
                )
            return {
                "ok": False,
                "path": path,
                "error": f"Not a regular file ({file_type}): {path}",
                "blocked_reason": reason
            }

        # Step 4: Get resolved path from FD (TOCTOU-safe)
        resolved_path = _resolve_fd_path(fd)

        # If we can't resolve FD path, fall back to target (less secure but functional)
        if resolved_path is None:
            resolved_path = os.path.realpath(target)

        # Step 5: Validate path containment (TOCTOU-safe since we use FD path)
        if not _validate_path_containment(resolved_path, repo_root):
            os.close(fd)
            fd = None

            reason = "path outside allowed root"
            if audit:
                audit_logger.warning(
                    f"BLOCKED: {path} -> resolved to {resolved_path}, outside {repo_root}"
                )
            return {
                "ok": False,
                "path": path,
                "error": f"Path outside allowed directory: {path}",
                "blocked_reason": reason
            }

        # Success
        if audit:
            audit_logger.info(f"ALLOWED: {path} -> {resolved_path}")

        return {
            "ok": True,
            "fd": fd,
            "path": path,
            "resolved_path": resolved_path,
            "size": file_stat.st_size
        }

    except FileNotFoundError:
        return {
            "ok": False,
            "path": path,
            "error": f"File not found: {path}"
        }
    except PermissionError:
        return {
            "ok": False,
            "path": path,
            "error": f"Permission denied: {path}"
        }
    except Exception as e:
        # Clean up FD on unexpected error
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

        return {
            "ok": False,
            "path": path,
            "error": str(e)
        }


def read_file_secure(
    path: str,
    repo_root: str = ".",
    max_bytes: int = DEFAULT_MAX_FILE_BYTES,
    audit: bool = True
) -> Dict[str, Any]:
    """
    Securely read a file with full TOCTOU protection.

    This is a drop-in replacement for the original read_file_snippet().

    Security features:
    1. Opens with O_NOFOLLOW (blocks symlinks on Unix)
    2. Validates file type (rejects devices, FIFOs, sockets)
    3. Validates containment AFTER opening (eliminates TOCTOU race)
    4. Audit logging of all access attempts

    Args:
        path: Path to file
        repo_root: Allowed root directory
        max_bytes: Maximum bytes to read
        audit: Whether to log access attempts

    Returns:
        Dict with:
        - ok: bool
        - path: str
        - content: str (if ok=True)
        - error: str (if ok=False)
    """
    # Step 1: Securely open the file
    open_result = secure_open(path, repo_root, audit=audit)

    if not open_result["ok"]:
        return {
            "ok": False,
            "path": path,
            "error": open_result["error"]
        }

    fd = open_result["fd"]
    file_size = open_result.get("size", 0)
    fd_closed = False

    try:
        # Step 2: Read content from file descriptor
        # Wrap FD in a file object for convenient reading
        # Note: os.fdopen takes ownership of fd and closes it on exit
        with os.fdopen(fd, "r", encoding="utf-8", errors="ignore") as f:
            fd_closed = True  # fdopen now owns the fd
            content = f.read(max_bytes)

        # Step 3: Add truncation notice if needed
        if file_size > len(content):
            content += "\n\n[TRUNCATED: file larger than max_bytes]\n"

        return {
            "ok": True,
            "path": path,
            "content": content
        }

    except Exception as e:
        # Only close fd if fdopen hasn't taken ownership yet
        if not fd_closed:
            try:
                os.close(fd)
            except OSError:
                pass

        return {
            "ok": False,
            "path": path,
            "error": str(e)
        }


def check_hardlinks(fd: int, warn_threshold: int = 2) -> Optional[str]:
    """
    Check if file has multiple hard links (potential security concern).

    Args:
        fd: Open file descriptor
        warn_threshold: Number of links to trigger warning

    Returns:
        Warning message if hardlinks detected, None otherwise
    """
    try:
        file_stat = os.fstat(fd)
        nlink = file_stat.st_nlink

        if nlink >= warn_threshold:
            return f"File has {nlink} hard links (potential security concern)"

    except OSError:
        pass

    return None


# Convenience function for backward compatibility
def safe_read_file(
    path: str,
    repo_root: str = ".",
    max_bytes: int = DEFAULT_MAX_FILE_BYTES
) -> Dict[str, Any]:
    """
    Backward-compatible wrapper for read_file_secure.

    Same interface as original read_file_snippet().
    """
    return read_file_secure(path, repo_root, max_bytes, audit=True)
