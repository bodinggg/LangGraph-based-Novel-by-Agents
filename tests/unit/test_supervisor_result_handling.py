"""
TDD Test for supervisor result handling edge case

Error: 'str' object has no attribute 'get'
This happens when supervisor_result is a string instead of dict
"""

import pytest
from unittest.mock import MagicMock
from src.state import NovelState


def make_state(supervisor_result, revision_needed=False, revision_priority="none"):
    """Helper to create mock NovelState with supervisor result"""
    state = MagicMock(spec=NovelState)
    state.supervisor_result = supervisor_result
    state.revision_needed = revision_needed
    state.revision_priority = revision_priority
    return state


class TestCheckRevisionNodeEdgeCases:
    """Tests for check_revision_node edge cases"""

    def test_supervisor_result_is_none(self):
        """When supervisor_result is None, should return write_next"""
        from src.supervisor_node import check_revision_node

        state = make_state(supervisor_result=None, revision_needed=False)
        result = check_revision_node(state)
        assert result == "write_next"

    def test_supervisor_result_is_dict_no_revision_needed(self):
        """When supervisor_result is dict and revision_needed=False, should return write_next"""
        from src.supervisor_node import check_revision_node

        state = make_state(
            supervisor_result={"revision_needed": False, "revision_priority": "none"},
            revision_needed=False
        )
        result = check_revision_node(state)
        assert result == "write_next"

    def test_supervisor_result_is_dict_revision_needed(self):
        """When supervisor_result is dict and revision_needed=True, should return revise"""
        from src.supervisor_node import check_revision_node

        state = make_state(
            supervisor_result={"revision_needed": True, "revision_priority": "high"},
            revision_needed=True
        )
        result = check_revision_node(state)
        assert result == "revise"

    def test_supervisor_result_is_string_should_not_crash(self):
        """When supervisor_result is unexpectedly a string, should not raise 'str' object has no attribute 'get'

        This is the edge case that causes: 'str' object has no attribute 'get'
        """
        from src.supervisor_node import check_revision_node

        state = make_state(supervisor_result="some_string_value")
        # Should not raise AttributeError
        try:
            result = check_revision_node(state)
            # If it returns something reasonable, that's fine
            assert result in ["write_next", "revise"]
        except AttributeError as e:
            if "'str' object has no attribute 'get'" in str(e):
                pytest.fail(f"check_revision_node crashed with: {e}")
            raise
