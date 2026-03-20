"""Tests for Markdown → Telegram MarkdownV2 conversion."""

import pytest

from ccbot.markdown_v2 import (
    _escape_mdv2,
    _split_table_row,
    convert_markdown,
    convert_markdown_tables,
)
from ccbot.transcript_parser import TranscriptParser

EXP_START = TranscriptParser.EXPANDABLE_QUOTE_START
EXP_END = TranscriptParser.EXPANDABLE_QUOTE_END


class TestEscapeMdv2:
    @pytest.mark.parametrize(
        "input_text,expected",
        [
            (
                "_*[]()~>#+\\-=|{}.!",
                "\\_\\*\\[\\]\\(\\)\\~\\>\\#\\+\\\\\\-\\=\\|\\{\\}\\.\\!",
            ),
            ("hello world 123", "hello world 123"),
            ("", ""),
        ],
        ids=["special-chars", "alphanumeric-unchanged", "empty-string"],
    )
    def test_escape(self, input_text: str, expected: str) -> None:
        assert _escape_mdv2(input_text) == expected


class TestConvertMarkdown:
    def test_plain_text(self) -> None:
        result = convert_markdown("hello world")
        assert "hello world" in result

    def test_bold(self) -> None:
        result = convert_markdown("**bold text**")
        assert "*bold text*" in result
        assert "**bold text**" not in result

    def test_code_block_preserved(self) -> None:
        result = convert_markdown("```python\nprint('hi')\n```")
        assert "```" in result
        assert "print" in result

    def test_expandable_quote_sentinels(self) -> None:
        text = f"{EXP_START}quoted content{EXP_END}"
        result = convert_markdown(text)
        assert EXP_START not in result
        assert EXP_END not in result
        assert ">quoted content||" in result

    def test_mixed_text_and_expandable_quote(self) -> None:
        text = f"before {EXP_START}inside quote{EXP_END} after"
        result = convert_markdown(text)
        assert EXP_START not in result
        assert EXP_END not in result
        assert ">inside quote||" in result
        assert "before" in result
        assert "after" in result


class TestTableConversion:
    def test_split_table_row(self) -> None:
        cells = _split_table_row("| Name | Age | City |")
        assert cells == ["Name", "Age", "City"]

    def test_split_table_row_escaped_pipe(self) -> None:
        cells = _split_table_row("| a\\|b | c |")
        assert cells == ["a|b", "c"]

    def test_simple_table(self) -> None:
        table = "| Name | Value |\n|------|-------|\n| foo  | bar   |\n| baz  | qux   |"
        result = convert_markdown_tables(table)
        assert "**Name**: foo" in result
        assert "**Value**: bar" in result
        assert "**Name**: baz" in result

    def test_table_with_missing_cells(self) -> None:
        table = "| A | B | C |\n|---|---|---|\n| 1 | 2 |"
        result = convert_markdown_tables(table)
        assert "**A**: 1" in result
        assert "**C**: —" in result

    def test_no_table_passthrough(self) -> None:
        text = "Just plain text\nNo tables here"
        result = convert_markdown_tables(text)
        assert result == text

    def test_table_in_convert_markdown(self) -> None:
        table = "| Col1 | Col2 |\n|------|------|\n| a    | b    |"
        result = convert_markdown(table)
        assert "Col1" in result
        assert "Col2" in result
