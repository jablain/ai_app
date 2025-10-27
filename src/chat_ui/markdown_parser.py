"""
Simple markdown parser that applies GTK TextTags
Supports: bold, italic, code, headers, code blocks, lists
"""

import re


class MarkdownParser:
    """Parse markdown and apply formatting to TextBuffer"""

    def __init__(self, text_buffer):
        self.buffer = text_buffer

    def parse_and_format(self, text):
        """Parse markdown text and apply formatting"""
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

    def _handle_code_block(self, lines, start_idx):
        """Handle fenced code blocks"""
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

    def _handle_header(self, line):
        """Handle header lines"""
        match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if not match:
            self._insert_text(line + "\n")
            return

        level = len(match.group(1))
        text = match.group(2)

        tag_name = f"h{level}"
        end_iter = self.buffer.get_end_iter()
        self.buffer.insert_with_tags_by_name(end_iter, text + "\n", tag_name)

    def _handle_list_item(self, line):
        """Handle list items"""
        # Remove bullet and clean up
        text = re.sub(r"^[\s]*[-*+]\s+", "• ", line)

        end_iter = self.buffer.get_end_iter()
        self.buffer.insert_with_tags_by_name(end_iter, text + "\n", "list")

    def _handle_inline_formatting(self, line):
        """Handle inline formatting (bold, italic, code)"""
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

    def _insert_text(self, text):
        """Insert plain text"""
        end_iter = self.buffer.get_end_iter()
        self.buffer.insert(end_iter, text)

    def _insert_tagged_text(self, text, tag_name):
        """Insert text with a specific tag"""
        end_iter = self.buffer.get_end_iter()
        self.buffer.insert_with_tags_by_name(end_iter, text, tag_name)
