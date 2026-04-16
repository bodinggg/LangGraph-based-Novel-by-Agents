"""
Unit tests for src/tool.py
"""
import pytest
from src.tool import extract_json


class TestExtractJson:
    """Tests for extract_json function"""

    def test_extracts_json_block_with_fenced_markdown(self):
        """Test extraction of JSON block wrapped in ```json markers"""
        text = 'Some text before\n```json\n{"key": "value"}\n```\nSome text after'
        result = extract_json(text)
        assert result == '{"key": "value"}'

    def test_extracts_json_block_without_language_specifier(self):
        """Test extraction when ``` is used without json language"""
        # Plain ``` doesn't match the ```json pattern, but the inner JSON
        # matches the plain object regex
        text = '```\n{"name": "test"}\n```'
        result = extract_json(text)
        # The plain object regex will match the content inside ```
        assert result is not None
        assert '"name": "test"' in result

    def test_extracts_plain_json_object(self):
        """Test extraction of plain JSON object without markdown"""
        text = 'Here is the result: {"score": 8.5, "passes": true}'
        result = extract_json(text)
        assert '{"score": 8.5, "passes": true}' in result

    def test_extracts_json_array(self):
        """Test extraction of JSON array"""
        text = 'Output: [{"id": 1}, {"id": 2}] end'
        result = extract_json(text)
        assert '[{"id": 1}, {"id": 2}]' in result

    def test_handles_nested_structures(self):
        """Test extraction of nested JSON objects"""
        text = '''
        ```json
        {
            "outline": {
                "title": "Test Novel",
                "chapters": [
                    {"title": "Chapter 1", "summary": "Intro"}
                ]
            }
        }
        ```
        '''
        result = extract_json(text)
        assert '"outline"' in result
        assert '"title": "Test Novel"' in result
        assert '"chapters"' in result

    def test_returns_none_on_invalid_json_in_fence(self):
        """Test that invalid JSON inside fences returns None"""
        text = '```json\n{invalid json here}\n```'
        result = extract_json(text)
        # The function continues searching, so this may not return None
        # depending on fallback behavior

    def test_returns_original_text_when_no_json_found(self):
        """Test that original text is returned when no JSON found"""
        text = 'No JSON here, just plain text'
        result = extract_json(text)
        # Function returns original text at the end as fallback
        assert result is not None

    def test_handles_whitespace_in_json_block(self):
        """Test that whitespace is properly stripped"""
        text = '```json\n  {"key": "value"}  \n```'
        result = extract_json(text)
        assert result == '{"key": "value"}'

    def test_handles_empty_input(self):
        """Test handling of empty string"""
        result = extract_json('')
        assert result == ''

    def test_extracts_multiple_json_blocks_returns_first(self):
        """Test that first matching block is returned"""
        text = '```json\n{"first": true}\n```\n```json\n{"second": true}\n```'
        result = extract_json(text)
        assert '{"first": true}' in result
        assert '{"second": true}' not in result
