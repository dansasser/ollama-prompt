#!/usr/bin/env python3
"""Tests for FileChunker module."""

import pytest
from pathlib import Path

from ollama_prompt.file_chunker import FileChunker


class TestFileChunkerInit:
    """Test FileChunker initialization."""

    def test_init(self):
        """Test basic initialization."""
        chunker = FileChunker()
        assert chunker.AUTO_SUMMARY_THRESHOLD == 5 * 1024

    def test_should_summarize_small_file(self):
        """Test that small files don't trigger summarization."""
        chunker = FileChunker()
        small_content = "x" * 1000  # 1KB
        assert chunker.should_summarize(small_content) is False

    def test_should_summarize_large_file(self):
        """Test that large files trigger summarization."""
        chunker = FileChunker()
        large_content = "x" * 10000  # 10KB
        assert chunker.should_summarize(large_content) is True


class TestPythonSummarization:
    """Test Python file summarization."""

    def test_summarize_python_basic(self):
        """Test basic Python summarization."""
        chunker = FileChunker()
        content = '''
import os
import sys

MAX_SIZE = 100
DEBUG = True

def hello(name):
    """Say hello."""
    print(f"Hello {name}")

def goodbye():
    print("Goodbye")

class Greeter:
    """A greeter class."""

    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"Hello {self.name}"
'''
        summary = chunker.summarize_python(content, "test.py")

        assert summary['ok'] is True
        assert summary['type'] == 'python'
        assert summary['path'] == 'test.py'
        assert 'os' in summary['imports']
        assert 'sys' in summary['imports']
        assert len(summary['functions']) == 2
        assert summary['functions'][0]['name'] == 'hello'
        assert summary['functions'][1]['name'] == 'goodbye'
        assert len(summary['classes']) == 1
        assert summary['classes'][0]['name'] == 'Greeter'
        assert len(summary['classes'][0]['methods']) == 2
        assert len(summary['constants']) == 2

    def test_summarize_python_syntax_error(self):
        """Test handling of syntax errors."""
        chunker = FileChunker()
        content = "def broken("  # Invalid syntax
        summary = chunker.summarize_python(content, "broken.py")

        assert summary['ok'] is False
        assert 'error' in summary

    def test_format_python_summary(self):
        """Test formatting Python summary."""
        chunker = FileChunker()
        content = '''
def test_func(a, b):
    pass

class TestClass:
    def method(self):
        pass
'''
        summary = chunker.summarize_python(content, "test.py")
        formatted = chunker.format_summary(summary)

        assert "Language: Python" in formatted
        assert "test_func" in formatted
        assert "TestClass" in formatted
        assert "@test.py:full" in formatted


class TestMarkdownSummarization:
    """Test Markdown file summarization."""

    def test_summarize_markdown_basic(self):
        """Test basic Markdown summarization."""
        chunker = FileChunker()
        content = '''# Main Title

Some intro text.

## Installation

Install instructions here.

## Usage

Usage instructions here.

### Advanced Usage

More details.

## Contributing

How to contribute.
'''
        summary = chunker.summarize_markdown(content, "README.md")

        assert summary['ok'] is True
        assert summary['type'] == 'markdown'
        assert summary['path'] == 'README.md'
        assert len(summary['sections']) == 5
        assert summary['sections'][0]['title'] == 'Main Title'
        assert summary['sections'][0]['level'] == 1
        assert summary['sections'][1]['title'] == 'Installation'
        assert summary['sections'][1]['level'] == 2

    def test_format_markdown_summary(self):
        """Test formatting Markdown summary."""
        chunker = FileChunker()
        content = '''# Title

## Section 1

## Section 2
'''
        summary = chunker.summarize_markdown(content, "doc.md")
        formatted = chunker.format_summary(summary)

        assert "Type: Markdown documentation" in formatted
        assert "Title" in formatted
        assert "Section 1" in formatted
        assert "@doc.md:full" in formatted


class TestGenericSummarization:
    """Test generic file summarization."""

    def test_summarize_generic_javascript(self):
        """Test generic summarization for JS files."""
        chunker = FileChunker()
        content = '''
const MAX_SIZE = 100;

function hello() {
    console.log("Hello");
}

export default function main() {
    hello();
}
'''
        summary = chunker.summarize_generic(content, "test.js")

        assert summary['ok'] is True
        assert summary['type'] == 'generic'
        assert summary['file_type'] == 'JavaScript'
        assert len(summary['structure']) > 0

    def test_format_generic_summary(self):
        """Test formatting generic summary."""
        chunker = FileChunker()
        content = "line1\nline2\nline3"
        summary = chunker.summarize_generic(content, "test.txt")
        formatted = chunker.format_summary(summary)

        assert "Type: Text" in formatted
        assert "@test.txt:full" in formatted


class TestElementExtraction:
    """Test element extraction."""

    def test_extract_python_function(self):
        """Test extracting a Python function."""
        chunker = FileChunker()
        content = '''
def first():
    pass

def target(a, b):
    """Target function."""
    return a + b

def last():
    pass
'''
        result = chunker.extract_element(content, "target", "test.py")

        assert result['ok'] is True
        assert result['element'] == 'target'
        assert result['element_type'] == 'function'
        assert 'def target(a, b):' in result['content']
        assert 'return a + b' in result['content']
        assert 'def first' not in result['content']

    def test_extract_python_class(self):
        """Test extracting a Python class."""
        chunker = FileChunker()
        content = '''
class First:
    pass

class Target:
    """Target class."""

    def __init__(self):
        self.value = 0

    def method(self):
        return self.value

class Last:
    pass
'''
        result = chunker.extract_element(content, "Target", "test.py")

        assert result['ok'] is True
        assert result['element'] == 'Target'
        assert result['element_type'] == 'class'
        assert 'class Target:' in result['content']
        assert 'def method(self):' in result['content']

    def test_extract_element_not_found(self):
        """Test extracting non-existent element."""
        chunker = FileChunker()
        content = "def foo(): pass"
        result = chunker.extract_element(content, "bar", "test.py")

        assert result['ok'] is False
        assert 'not found' in result['error']

    def test_extract_markdown_section(self):
        """Test extracting a Markdown section."""
        chunker = FileChunker()
        content = '''# Title

## Installation

Install like this:
```
pip install foo
```

## Usage

Use like this.

## Contributing

Contribute here.
'''
        result = chunker.extract_element(content, "Installation", "README.md")

        assert result['ok'] is True
        assert result['element'] == 'Installation'
        assert 'pip install foo' in result['content']
        assert 'Use like this' not in result['content']


class TestLineExtraction:
    """Test line range extraction."""

    def test_extract_lines_basic(self):
        """Test basic line extraction."""
        chunker = FileChunker()
        content = "line1\nline2\nline3\nline4\nline5"
        result = chunker.extract_lines(content, 2, 4, "test.txt")

        assert result['ok'] is True
        assert result['content'] == "line2\nline3\nline4"
        assert result['lines'] == "2-4"

    def test_extract_lines_clamp_start(self):
        """Test that start line is clamped to 1."""
        chunker = FileChunker()
        content = "line1\nline2\nline3"
        result = chunker.extract_lines(content, -5, 2, "test.txt")

        assert result['ok'] is True
        assert result['content'] == "line1\nline2"

    def test_extract_lines_clamp_end(self):
        """Test that end line is clamped to file length."""
        chunker = FileChunker()
        content = "line1\nline2\nline3"
        result = chunker.extract_lines(content, 2, 100, "test.txt")

        assert result['ok'] is True
        assert result['content'] == "line2\nline3"

    def test_extract_lines_invalid_range(self):
        """Test error for invalid range (start > end)."""
        chunker = FileChunker()
        content = "line1\nline2\nline3"
        result = chunker.extract_lines(content, 5, 2, "test.txt")

        assert result['ok'] is False
        assert 'Invalid line range' in result['error']


class TestAutoDetection:
    """Test automatic file type detection."""

    def test_summarize_auto_python(self):
        """Test auto-detection for Python files."""
        chunker = FileChunker()
        content = "def foo(): pass"
        summary = chunker.summarize(content, "test.py")
        assert summary['type'] == 'python'

    def test_summarize_auto_markdown(self):
        """Test auto-detection for Markdown files."""
        chunker = FileChunker()
        content = "# Title\n\nContent"
        summary = chunker.summarize(content, "README.md")
        assert summary['type'] == 'markdown'

    def test_summarize_auto_generic(self):
        """Test auto-detection falls back to generic."""
        chunker = FileChunker()
        content = "some text"
        summary = chunker.summarize(content, "test.txt")
        assert summary['type'] == 'generic'


class TestCLIIntegration:
    """Test CLI integration with expand_file_refs_in_prompt."""

    def test_file_ref_with_summary_mode(self, tmp_path):
        """Test :summary mode forces summarization."""
        from ollama_prompt.cli import expand_file_refs_in_prompt

        # Create a small file (under threshold)
        test_file = tmp_path / "small.py"
        test_file.write_text("def hello(): pass", encoding="utf-8")

        prompt = f"Explain: @./small.py:summary"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        assert "(SUMMARY)" in result
        assert "Language: Python" in result

    def test_file_ref_with_full_mode(self, tmp_path):
        """Test :full mode returns full content."""
        from ollama_prompt.cli import expand_file_refs_in_prompt

        # Create a large file (over threshold)
        test_file = tmp_path / "large.py"
        content = "def hello(): pass\n" * 1000  # ~19KB
        test_file.write_text(content, encoding="utf-8")

        prompt = f"Explain: @./large.py:full"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        assert "(FULL)" in result
        assert "def hello(): pass" in result

    def test_file_ref_with_element_extraction(self, tmp_path):
        """Test :element_name extracts specific element."""
        from ollama_prompt.cli import expand_file_refs_in_prompt

        test_file = tmp_path / "module.py"
        test_file.write_text('''
def foo():
    pass

def target_func(x):
    """Target function."""
    return x * 2

def bar():
    pass
''', encoding="utf-8")

        prompt = f"Explain: @./module.py:target_func"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        assert "target_func" in result
        assert "return x * 2" in result
        # Should not include other functions
        assert "def foo" not in result or "module.py:target_func" in result

    def test_file_ref_with_line_range(self, tmp_path):
        """Test :lines:START-END extracts line range."""
        from ollama_prompt.cli import expand_file_refs_in_prompt

        test_file = tmp_path / "data.txt"
        test_file.write_text("line1\nline2\nline3\nline4\nline5\n", encoding="utf-8")

        prompt = f"Show: @./data.txt:lines:2-4"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        assert "(lines 2-4)" in result
        assert "line2" in result
        assert "line3" in result
        assert "line4" in result

    def test_auto_summary_for_large_file(self, tmp_path):
        """Test that large files are auto-summarized."""
        from ollama_prompt.cli import expand_file_refs_in_prompt

        # Create a file over 5KB threshold
        test_file = tmp_path / "big.py"
        content = '''
import os
import sys

def function_one():
    pass

def function_two():
    pass

class MyClass:
    def method(self):
        pass
'''
        # Pad to exceed 5KB
        content += "\n# padding\n" * 500
        test_file.write_text(content, encoding="utf-8")

        prompt = f"Explain: @./big.py"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        assert "(SUMMARY" in result
        assert "Language: Python" in result
        assert "function_one" in result
        assert "MyClass" in result

    def test_small_file_not_summarized(self, tmp_path):
        """Test that small files are not auto-summarized."""
        from ollama_prompt.cli import expand_file_refs_in_prompt

        test_file = tmp_path / "tiny.py"
        test_file.write_text("def hello(): pass", encoding="utf-8")

        prompt = f"Explain: @./tiny.py"
        result = expand_file_refs_in_prompt(prompt, repo_root=str(tmp_path))

        # Should get full content, not summary
        assert "def hello(): pass" in result
        assert "Language: Python" not in result  # Summary marker


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_file(self):
        """Test handling empty file."""
        chunker = FileChunker()
        summary = chunker.summarize("", "empty.py")
        assert summary['ok'] is True
        assert summary['lines'] == 0

    def test_extract_from_empty_file(self):
        """Test extraction from empty file."""
        chunker = FileChunker()
        result = chunker.extract_element("", "foo", "empty.py")
        assert result['ok'] is False

    def test_binary_like_content(self):
        """Test handling of binary-like content."""
        chunker = FileChunker()
        # This should not crash
        content = "\x00\x01\x02\x03"
        summary = chunker.summarize_generic(content, "binary.bin")
        assert summary['ok'] is True
