"""
Simple markdown parser that applies GTK TextTags
Supports: bold, italic, code, headers, code blocks, lists
"""

from __future__ import annotations

import re


class MarkdownParser:
    """Parse markdown and apply formatting to TextBuffer"""

    def __init__(self, text_buffer: object) -> None:
        """
        Initialize markdown parser

        Args:
            text_buffer: GTK TextBuffer to render into
        """
        self.buffer = text_buffer

    def parse_and_format(self, text: str) -> None:
        """
        Parse markdown text and apply formatting

        Args:
            text: Markdown text to parse
        """
        lines = text.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i]

            # Code block (fenced with ``` or indented)
            if line.strip().startswith("```"):
                i = self._handle_code_block(lines, i)
                continue

            # Headers
            if line.startswith("#"):
                self._handle_header(line)
                i += 1
                continue

            # List items
            if re.match(r"^[\s]*[-*+]\s", line):
                self._handle_list_item(line)
                i += 1
                continue

            # Regular paragraph with inline formatting
            self._handle_inline_formatting(line)
            i += 1

    def _handle_code_block(self, lines: list[str], start_idx: int) -> int:
        """
        Handle fenced code blocks

        Args:
            lines: All lines in the document
            start_idx: Index of opening ```

        Returns:
            Index after closing ```
        """
        start_idx += 1  # Skip opening ```
        code_lines = []

        i = start_idx
        while i < len(lines):
            if lines[i].strip().startswith("```"):
                break
            code_lines.append(lines[i])
            i += 1

        # Insert code block
        code_text = "\n".join(code_lines) + "\n"
        end_iter = self.buffer.get_end_iter()
        self.buffer.insert_with_tags_by_name(end_iter, code_text, "code-block")

        return i + 1  # Skip closing ```

    def _handle_header(self, line: str) -> None:
        """
        Handle header lines

        Args:
            line: Header line (e.g. "## Title")
        """
        match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if not match:
            self._insert_text(line + "\n")
            return

        level = len(match.group(1))
        text = match.group(2)

        tag_name = f"h{level}"
        end_iter = self.buffer.get_end_iter()
        self.buffer.insert_with_tags_by_name(end_iter, text + "\n", tag_name)

    def _handle_list_item(self, line: str) -> None:
        """
        Handle list items

        Args:
            line: List item line (e.g. "- Item")
        """
        # Remove bullet and clean up
        text = re.sub(r"^[\s]*[-*+]\s+", "• ", line)

        end_iter = self.buffer.get_end_iter()
        self.buffer.insert_with_tags_by_name(end_iter, text + "\n", "list")

    def _handle_inline_formatting(self, line: str) -> None:
        """
        Handle inline formatting (bold, italic, code)

        Args:
            line: Line with potential inline formatting
        """
        if not line.strip():
            self._insert_text("\n")
            return

        # Pattern matching order matters!
        # Match bold (**text**), italic (*text*), code (`text`)

        pos = 0
        while pos < len(line):
            # Try to match formatting patterns

            # Bold: **text**
            bold_match = re.match(r"\*\*(.+?)\*\*", line[pos:])
            if bold_match:
                self._insert_tagged_text(bold_match.group(1), "bold")
                pos += bold_match.end()
                continue

            # Code: `text`
            code_match = re.match(r"`(.+?)`", line[pos:])
            if code_match:
                self._insert_tagged_text(code_match.group(1), "code")
                pos += code_match.end()
                continue

            # Italic: *text* (but not ** which is bold)
            italic_match = re.match(r"\*([^*]+?)\*", line[pos:])
            if italic_match:
                self._insert_tagged_text(italic_match.group(1), "italic")
                pos += italic_match.end()
                continue

            # No match, insert plain character
            self._insert_text(line[pos])
            pos += 1

        # End of line
        self._insert_text("\n")

    def _insert_text(self, text: str) -> None:
        """
        Insert plain text

        Args:
            text: Text to insert
        """
        end_iter = self.buffer.get_end_iter()
        self.buffer.insert(end_iter, text)

    def _insert_tagged_text(self, text: str, tag_name: str) -> None:
        """
        Insert text with a specific tag

        Args:
            text: Text to insert
            tag_name: Name of the tag to apply
        """
        end_iter = self.buffer.get_end_iter()
        self.buffer.insert_with_tags_by_name(end_iter, text, tag_name)
