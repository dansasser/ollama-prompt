#!/usr/bin/env python3
"""
Tests for directory syntax expansion in file references.

Tests cover:
- @./dir/ - List directory contents
- @./dir/:list - Explicit list operation
- @./dir/:tree - Directory tree
- @./dir/:search:pattern - Search in directory
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ollama_prompt.cli import (
    expand_file_refs_in_prompt,
    list_directory,
    get_directory_tree,
    search_directory
)


class TestDirectoryListing:
    """Test directory listing operations."""

    def test_list_directory_basic(self, tmp_path):
        """Test basic directory listing."""
        # Create test structure
        (tmp_path / "file1.txt").write_text("content1", encoding="utf-8")
        (tmp_path / "file2.py").write_text("content2", encoding="utf-8")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested", encoding="utf-8")

        result = list_directory(".", repo_root=str(tmp_path))

        assert result["ok"] is True
        assert "[DIR]" in result["content"]
        assert "subdir" in result["content"]
        assert "[FILE]" in result["content"]
        assert "file1.txt" in result["content"]

    def test_list_directory_empty(self, tmp_path):
        """Test listing empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = list_directory("empty", repo_root=str(tmp_path))

        assert result["ok"] is True
        assert "empty" in result["content"].lower()

    def test_list_directory_not_found(self, tmp_path):
        """Test listing non-existent directory."""
        result = list_directory("nonexistent", repo_root=str(tmp_path))

        assert result["ok"] is False
        assert "error" in result


class TestDirectoryTree:
    """Test directory tree operations."""

    def test_tree_basic(self, tmp_path):
        """Test basic directory tree."""
        # Create test structure
        (tmp_path / "root.txt").write_text("root", encoding="utf-8")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "child.txt").write_text("child", encoding="utf-8")
        deep = subdir / "deep"
        deep.mkdir()
        (deep / "leaf.txt").write_text("leaf", encoding="utf-8")

        result = get_directory_tree(".", repo_root=str(tmp_path), max_depth=3)

        assert result["ok"] is True
        assert "subdir" in result["content"]
        assert "child.txt" in result["content"]
        assert "deep" in result["content"]

    def test_tree_depth_limit(self, tmp_path):
        """Test tree respects depth limit."""
        # Create deep structure
        current = tmp_path
        for i in range(5):
            current = current / f"level{i}"
            current.mkdir()
            (current / f"file{i}.txt").write_text(f"content{i}", encoding="utf-8")

        result = get_directory_tree(".", repo_root=str(tmp_path), max_depth=2)

        assert result["ok"] is True
        assert "level0" in result["content"]
        assert "level1" in result["content"]
        # level2 should be at depth limit, level3+ may not appear fully


class TestDirectorySearch:
    """Test directory search operations."""

    def test_search_basic(self, tmp_path):
        """Test basic search."""
        (tmp_path / "file1.py").write_text("def hello():\n    print('world')", encoding="utf-8")
        (tmp_path / "file2.py").write_text("def goodbye():\n    return None", encoding="utf-8")

        result = search_directory(".", "hello", repo_root=str(tmp_path))

        assert result["ok"] is True
        assert "hello" in result["content"]
        assert "file1.py" in result["content"]

    def test_search_no_matches(self, tmp_path):
        """Test search with no matches."""
        (tmp_path / "file.txt").write_text("nothing here", encoding="utf-8")

        result = search_directory(".", "nonexistent_pattern_xyz", repo_root=str(tmp_path))

        assert result["ok"] is True
        assert "No matches" in result["content"]

    def test_search_multiple_files(self, tmp_path):
        """Test search across multiple files."""
        (tmp_path / "a.py").write_text("TODO: fix this", encoding="utf-8")
        (tmp_path / "b.py").write_text("TODO: and this", encoding="utf-8")
        (tmp_path / "c.py").write_text("no todos here", encoding="utf-8")

        result = search_directory(".", "TODO", repo_root=str(tmp_path))

        assert result["ok"] is True
        assert "a.py" in result["content"]
        assert "b.py" in result["content"]


class TestExpandFileRefsWithDirectories:
    """Test expand_file_refs_in_prompt with directory syntax."""

    def test_trailing_slash_lists_directory(self, tmp_path):
        """Test @./dir/ lists directory."""
        (tmp_path / "test.txt").write_text("content", encoding="utf-8")
        subdir = tmp_path / "mydir"
        subdir.mkdir()
        (subdir / "file.py").write_text("code", encoding="utf-8")

        prompt = "List this: @./mydir/"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        assert "DIRECTORY:" in result
        assert "file.py" in result

    def test_explicit_list_operation(self, tmp_path):
        """Test @./dir/:list explicitly lists directory."""
        subdir = tmp_path / "src"
        subdir.mkdir()
        (subdir / "main.py").write_text("code", encoding="utf-8")

        prompt = "Show: @./src/:list"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        assert "DIRECTORY:" in result
        assert "main.py" in result

    def test_tree_operation(self, tmp_path):
        """Test @./dir/:tree shows tree."""
        subdir = tmp_path / "project"
        subdir.mkdir()
        (subdir / "app.py").write_text("app", encoding="utf-8")
        nested = subdir / "lib"
        nested.mkdir()
        (nested / "utils.py").write_text("utils", encoding="utf-8")

        prompt = "Tree: @./project/:tree"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        assert "TREE:" in result
        assert "project" in result

    def test_search_operation(self, tmp_path):
        """Test @./dir/:search:pattern searches."""
        subdir = tmp_path / "code"
        subdir.mkdir()
        (subdir / "file.py").write_text("def my_function():\n    pass", encoding="utf-8")

        prompt = "Find: @./code/:search:my_function"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        assert "SEARCH:" in result
        assert "my_function" in result

    def test_search_requires_pattern(self, tmp_path):
        """Test @./dir/:search: without pattern shows error."""
        subdir = tmp_path / "code"
        subdir.mkdir()

        # :search: without a pattern should show an error
        prompt = "Find: @./code/:search:"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        # Should surface a clear error when :search: has no pattern
        assert "ERROR: :search requires a pattern" in result

    def test_file_still_works(self, tmp_path):
        """Test regular file reference still works."""
        (tmp_path / "readme.md").write_text("# Hello", encoding="utf-8")

        prompt = "Read: @./readme.md"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        assert "FILE:" in result
        assert "# Hello" in result

    def test_mixed_file_and_directory(self, tmp_path):
        """Test prompt with both file and directory references."""
        (tmp_path / "config.json").write_text('{"key": "value"}', encoding="utf-8")
        subdir = tmp_path / "src"
        subdir.mkdir()
        (subdir / "app.py").write_text("print('app')", encoding="utf-8")

        prompt = "Config: @./config.json and source: @./src/"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        assert "FILE: ./config.json" in result
        assert "DIRECTORY: ./src" in result


class TestDirectorySecurityValidation:
    """Test security validation for directory operations."""

    def test_path_traversal_blocked(self, tmp_path):
        """Test path traversal is blocked."""
        result = list_directory("../../../etc", repo_root=str(tmp_path))

        # Should fail due to path traversal
        assert result["ok"] is False

    def test_outside_repo_blocked(self, tmp_path):
        """Test access outside repo root is blocked."""
        outside = tmp_path.parent / "outside_test"
        outside.mkdir(exist_ok=True)

        try:
            result = list_directory(str(outside), repo_root=str(tmp_path))
            assert result["ok"] is False
        finally:
            outside.rmdir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
