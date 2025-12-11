#!/usr/bin/env python3
"""
FileChunker - Smart file summarization for context window optimization.

This module provides intelligent file summarization that reduces token usage
by 90%+ while preserving navigability and key structural information.

Supports:
- Python files (AST-based extraction)
- Markdown files (section-based parsing)
- Generic text files (line-count fallback)
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


class FileChunker:
    """
    Intelligent file chunking and summarization.

    Provides methods to:
    - Generate structured summaries of code/text files
    - Extract specific elements (functions, classes) by name
    - Extract line ranges
    - Format summaries for model consumption
    """

    # File size threshold for auto-summarization (5KB)
    AUTO_SUMMARY_THRESHOLD = 5 * 1024

    def __init__(self):
        """Initialize the FileChunker."""
        pass

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def should_summarize(self, content: str) -> bool:
        """
        Determine if content should be auto-summarized based on size.

        Args:
            content: File content

        Returns:
            True if file exceeds AUTO_SUMMARY_THRESHOLD
        """
        return len(content.encode('utf-8')) > self.AUTO_SUMMARY_THRESHOLD

    def summarize(self, content: str, path: str) -> Dict[str, Any]:
        """
        Generate a structured summary of file content.

        Automatically detects file type and uses appropriate summarizer.

        Args:
            content: File content
            path: File path (used for type detection)

        Returns:
            Summary dict with structure information
        """
        path_lower = path.lower()

        if path_lower.endswith('.py'):
            return self.summarize_python(content, path)
        elif path_lower.endswith(('.md', '.markdown')):
            return self.summarize_markdown(content, path)
        else:
            return self.summarize_generic(content, path)

    def extract_element(self, content: str, element_name: str, path: str) -> Dict[str, Any]:
        """
        Extract a specific function or class from file content.

        Args:
            content: File content
            element_name: Name of function/class to extract
            path: File path

        Returns:
            Dict with extracted content or error
        """
        if path.lower().endswith('.py'):
            return self._extract_python_element(content, element_name, path)
        elif path.lower().endswith(('.md', '.markdown')):
            return self._extract_markdown_section(content, element_name, path)
        else:
            return {
                'ok': False,
                'path': path,
                'error': f"Element extraction not supported for this file type"
            }

    def extract_lines(self, content: str, start: int, end: int, path: str) -> Dict[str, Any]:
        """
        Extract a range of lines from file content.

        Args:
            content: File content
            start: Start line (1-indexed, inclusive)
            end: End line (1-indexed, inclusive)
            path: File path

        Returns:
            Dict with extracted lines or error
        """
        lines = content.splitlines()
        total_lines = len(lines)

        # Validate range
        if start < 1:
            start = 1
        if end > total_lines:
            end = total_lines
        if start > end:
            return {
                'ok': False,
                'path': path,
                'error': f"Invalid line range: {start}-{end} (file has {total_lines} lines)"
            }

        # Extract lines (convert to 0-indexed)
        extracted = lines[start - 1:end]

        return {
            'ok': True,
            'path': path,
            'content': '\n'.join(extracted),
            'lines': f"{start}-{end}",
            'total_lines': total_lines
        }

    def format_summary(self, summary: Dict[str, Any]) -> str:
        """
        Format a summary dict as readable text for the model.

        Args:
            summary: Summary dict from summarize_*() methods

        Returns:
            Formatted string suitable for model context
        """
        if not summary.get('ok', True):
            return f"[Error: {summary.get('error', 'Unknown error')}]"

        file_type = summary.get('type', 'unknown')

        if file_type == 'python':
            return self._format_python_summary(summary)
        elif file_type == 'markdown':
            return self._format_markdown_summary(summary)
        else:
            return self._format_generic_summary(summary)

    # =========================================================================
    # PYTHON SUMMARIZATION
    # =========================================================================

    def summarize_python(self, content: str, path: str) -> Dict[str, Any]:
        """
        Generate structured summary of Python file using AST parsing.

        Args:
            content: Python source code
            path: File path

        Returns:
            Summary dict with imports, classes, functions, constants
        """
        lines = content.splitlines()

        try:
            tree = ast.parse(content)

            summary = {
                'ok': True,
                'type': 'python',
                'path': path,
                'lines': len(lines),
                'size_bytes': len(content.encode('utf-8')),
                'imports': self._extract_imports(tree),
                'classes': self._extract_classes(tree),
                'functions': self._extract_top_level_functions(tree),
                'constants': self._extract_constants(tree),
            }

            return summary

        except SyntaxError as e:
            return {
                'ok': False,
                'type': 'python',
                'path': path,
                'error': f"Syntax error at line {e.lineno}: {e.msg}"
            }

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import statements from AST."""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                imports.append(module)

        # Dedupe and limit
        return list(dict.fromkeys(imports))[:15]

    def _extract_classes(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract class definitions with their methods."""
        classes = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.append({
                            'name': item.name,
                            'line': item.lineno,
                            'args': self._get_function_args(item)
                        })

                classes.append({
                    'name': node.name,
                    'line_start': node.lineno,
                    'line_end': node.end_lineno,
                    'bases': [self._get_name(base) for base in node.bases],
                    'methods': methods
                })

        return classes

    def _extract_top_level_functions(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract top-level function definitions."""
        functions = []

        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    'name': node.name,
                    'line_start': node.lineno,
                    'line_end': node.end_lineno,
                    'args': self._get_function_args(node),
                    'decorators': [self._get_name(d) for d in node.decorator_list]
                })

        return functions

    def _extract_constants(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract module-level constants (UPPER_CASE assignments)."""
        constants = []

        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        # Get value preview
                        value_preview = self._get_value_preview(node.value)
                        constants.append({
                            'name': target.id,
                            'line': node.lineno,
                            'value': value_preview
                        })

        return constants[:15]  # Limit to 15

    def _get_function_args(self, node: ast.FunctionDef) -> str:
        """Get function arguments as string."""
        args = []

        for arg in node.args.args:
            args.append(arg.arg)

        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")

        return ', '.join(args)

    def _get_name(self, node: ast.AST) -> str:
        """Get name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_name(node.func)
        else:
            return str(type(node).__name__)

    def _get_value_preview(self, node: ast.AST) -> str:
        """Get preview of constant value."""
        if isinstance(node, ast.Constant):
            val = repr(node.value)
            return val[:50] + '...' if len(val) > 50 else val
        elif isinstance(node, ast.List):
            return f"[...] ({len(node.elts)} items)"
        elif isinstance(node, ast.Dict):
            return f"{{...}} ({len(node.keys)} keys)"
        else:
            return "<complex>"

    def _extract_python_element(self, content: str, element_name: str, path: str) -> Dict[str, Any]:
        """Extract a specific function or class from Python source."""
        lines = content.splitlines()

        try:
            tree = ast.parse(content)

            # Search for the element
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if node.name == element_name:
                        start_line = node.lineno - 1
                        end_line = node.end_lineno

                        extracted = '\n'.join(lines[start_line:end_line])

                        return {
                            'ok': True,
                            'path': path,
                            'element': element_name,
                            'element_type': 'class' if isinstance(node, ast.ClassDef) else 'function',
                            'content': extracted,
                            'lines': f"{node.lineno}-{node.end_lineno}"
                        }

            return {
                'ok': False,
                'path': path,
                'error': f"Element '{element_name}' not found in file"
            }

        except SyntaxError as e:
            return {
                'ok': False,
                'path': path,
                'error': f"Syntax error: {e}"
            }

    def _format_python_summary(self, summary: Dict[str, Any]) -> str:
        """Format Python summary as readable text."""
        lines = [
            f"Language: Python",
            f"Size: {summary['lines']} lines, {summary['size_bytes'] / 1024:.1f} KB",
            "",
            "Structure:"
        ]

        # Imports
        if summary.get('imports'):
            imports_str = ', '.join(summary['imports'][:10])
            if len(summary['imports']) > 10:
                imports_str += f" (+{len(summary['imports']) - 10} more)"
            lines.append(f"  Imports: {imports_str}")

        # Classes
        if summary.get('classes'):
            lines.append("  Classes:")
            for cls in summary['classes']:
                bases = f"({', '.join(cls['bases'])})" if cls['bases'] else ""
                lines.append(f"    - {cls['name']}{bases} (lines {cls['line_start']}-{cls['line_end']})")
                for method in cls['methods'][:10]:
                    lines.append(f"        .{method['name']}({method['args']})")
                if len(cls['methods']) > 10:
                    lines.append(f"        ... +{len(cls['methods']) - 10} more methods")

        # Functions
        if summary.get('functions'):
            lines.append("  Functions:")
            for func in summary['functions'][:15]:
                decorators = f"@{', @'.join(func['decorators'])} " if func['decorators'] else ""
                lines.append(f"    - {decorators}{func['name']}({func['args']}) (lines {func['line_start']}-{func['line_end']})")
            if len(summary['functions']) > 15:
                lines.append(f"    ... +{len(summary['functions']) - 15} more functions")

        # Constants
        if summary.get('constants'):
            lines.append("  Constants:")
            for const in summary['constants'][:10]:
                lines.append(f"    - {const['name']} = {const['value']}")

        # Usage hints
        lines.extend([
            "",
            f"To see full content: @{summary['path']}:full",
            f"To see specific element: @{summary['path']}:element_name"
        ])

        return '\n'.join(lines)

    # =========================================================================
    # MARKDOWN SUMMARIZATION
    # =========================================================================

    def summarize_markdown(self, content: str, path: str) -> Dict[str, Any]:
        """
        Generate structured summary of Markdown file.

        Args:
            content: Markdown content
            path: File path

        Returns:
            Summary dict with sections and metadata
        """
        lines = content.splitlines()
        sections = []
        current_section = None

        # Parse headers to build section structure
        header_pattern = re.compile(r'^(#{1,6})\s+(.+)$')

        for i, line in enumerate(lines):
            match = header_pattern.match(line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()

                if current_section:
                    current_section['line_end'] = i
                    sections.append(current_section)

                current_section = {
                    'level': level,
                    'title': title,
                    'line_start': i + 1
                }

        # Close last section
        if current_section:
            current_section['line_end'] = len(lines)
            sections.append(current_section)

        # Extract key topics (first 200 chars of each section)
        topics = []
        for section in sections[:10]:
            start = section['line_start']
            end = min(start + 5, section['line_end'])
            section_text = ' '.join(lines[start:end])
            # Extract keywords
            words = re.findall(r'\b[a-zA-Z]{4,}\b', section_text.lower())
            topics.extend(words[:5])

        return {
            'ok': True,
            'type': 'markdown',
            'path': path,
            'lines': len(lines),
            'size_bytes': len(content.encode('utf-8')),
            'sections': sections,
            'topics': list(dict.fromkeys(topics))[:20]
        }

    def _extract_markdown_section(self, content: str, section_name: str, path: str) -> Dict[str, Any]:
        """Extract a specific section from Markdown by header name."""
        lines = content.splitlines()
        header_pattern = re.compile(r'^(#{1,6})\s+(.+)$')

        in_section = False
        section_level = 0
        section_lines = []

        for i, line in enumerate(lines):
            match = header_pattern.match(line)

            if match:
                level = len(match.group(1))
                title = match.group(2).strip()

                if in_section:
                    # Check if we've hit a same-level or higher header
                    if level <= section_level:
                        break

                # Check if this is the section we want
                if title.lower() == section_name.lower() or section_name.lower() in title.lower():
                    in_section = True
                    section_level = level

            if in_section:
                section_lines.append(line)

        if section_lines:
            return {
                'ok': True,
                'path': path,
                'element': section_name,
                'element_type': 'section',
                'content': '\n'.join(section_lines)
            }
        else:
            return {
                'ok': False,
                'path': path,
                'error': f"Section '{section_name}' not found"
            }

    def _format_markdown_summary(self, summary: Dict[str, Any]) -> str:
        """Format Markdown summary as readable text."""
        lines = [
            f"Type: Markdown documentation",
            f"Size: {summary['lines']} lines, {summary['size_bytes'] / 1024:.1f} KB",
            "",
            "Sections:"
        ]

        for i, section in enumerate(summary['sections'][:20], 1):
            indent = "  " * (section['level'] - 1)
            lines.append(f"  {i}. {indent}{section['title']} (lines {section['line_start']}-{section['line_end']})")

        if len(summary['sections']) > 20:
            lines.append(f"  ... +{len(summary['sections']) - 20} more sections")

        if summary.get('topics'):
            lines.extend([
                "",
                f"Key topics: {', '.join(summary['topics'][:15])}"
            ])

        lines.extend([
            "",
            f"To see full content: @{summary['path']}:full",
            f"To see specific section: @{summary['path']}:section_name"
        ])

        return '\n'.join(lines)

    # =========================================================================
    # GENERIC SUMMARIZATION
    # =========================================================================

    def summarize_generic(self, content: str, path: str) -> Dict[str, Any]:
        """
        Generate basic summary for non-Python, non-Markdown files.

        Args:
            content: File content
            path: File path

        Returns:
            Summary dict with basic metadata
        """
        lines = content.splitlines()

        # Detect file type from extension
        ext = Path(path).suffix.lower()
        file_type = {
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.jsx': 'React JSX',
            '.tsx': 'React TSX',
            '.java': 'Java',
            '.go': 'Go',
            '.rs': 'Rust',
            '.c': 'C',
            '.cpp': 'C++',
            '.h': 'C Header',
            '.hpp': 'C++ Header',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.sh': 'Shell Script',
            '.bash': 'Bash Script',
            '.yaml': 'YAML',
            '.yml': 'YAML',
            '.json': 'JSON',
            '.xml': 'XML',
            '.html': 'HTML',
            '.css': 'CSS',
            '.sql': 'SQL',
            '.txt': 'Text',
        }.get(ext, 'Unknown')

        # Simple structure detection
        structure = []

        # Look for common patterns
        function_patterns = [
            (r'^\s*def\s+(\w+)', 'function'),
            (r'^\s*class\s+(\w+)', 'class'),
            (r'^\s*function\s+(\w+)', 'function'),
            (r'^\s*const\s+(\w+)\s*=', 'constant'),
            (r'^\s*export\s+(default\s+)?(function|class|const)\s+(\w+)', 'export'),
        ]

        for i, line in enumerate(lines[:500]):  # Limit scanning
            for pattern, item_type in function_patterns:
                match = re.match(pattern, line)
                if match:
                    name = match.group(1) if match.lastindex == 1 else match.group(match.lastindex)
                    structure.append({
                        'type': item_type,
                        'name': name,
                        'line': i + 1
                    })
                    break

        return {
            'ok': True,
            'type': 'generic',
            'file_type': file_type,
            'path': path,
            'lines': len(lines),
            'size_bytes': len(content.encode('utf-8')),
            'structure': structure[:30]
        }

    def _format_generic_summary(self, summary: Dict[str, Any]) -> str:
        """Format generic summary as readable text."""
        lines = [
            f"Type: {summary.get('file_type', 'Unknown')}",
            f"Size: {summary['lines']} lines, {summary['size_bytes'] / 1024:.1f} KB",
        ]

        if summary.get('structure'):
            lines.extend(["", "Structure detected:"])
            for item in summary['structure'][:20]:
                lines.append(f"  - {item['type']}: {item['name']} (line {item['line']})")
            if len(summary['structure']) > 20:
                lines.append(f"  ... +{len(summary['structure']) - 20} more items")

        lines.extend([
            "",
            f"To see full content: @{summary['path']}:full",
            f"To see specific lines: @{summary['path']}:lines:START-END"
        ])

        return '\n'.join(lines)
