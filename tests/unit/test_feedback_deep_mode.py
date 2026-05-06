"""
TDD Tests for check_chapter_feedback_deep_mode_node

Tests the routing logic:
1. gradio_mode=True + evaluation_mode=deep -> returns deep_skip
2. gradio_mode=True + evaluation_mode=fast -> returns success
3. gradio_mode=False + evaluation_mode=deep + action=success -> returns deep_skip
4. gradio_mode=False + evaluation_mode=fast + action=success -> returns success
5. gradio_mode=False + has error -> returns failure
6. gradio_mode=False + action=retry -> returns retry
7. gradio_mode=False + action=None -> returns based on evaluation_mode
"""

import pytest
from unittest.mock import MagicMock, patch
from src.state import NovelState


def make_state(gradio_mode: bool = False, evaluation_mode: str = "deep",
               chapter_feedback_error: str = None, chapter_feedback_action: str = "success") -> NovelState:
    """Helper to create a mock NovelState"""
    state = MagicMock(spec=NovelState)
    state.gradio_mode = gradio_mode
    state.evaluation_mode = evaluation_mode
    state.chapter_feedback_error = chapter_feedback_error
    state.chapter_feedback_action = chapter_feedback_action
    return state


class TestCheckChapterFeedbackDeepModeNode:
    """Tests for check_chapter_feedback_deep_mode_node function"""

    def test_gradio_mode_deep_returns_deep_skip(self):
        """gradio_mode=True + evaluation_mode=deep should return deep_skip"""
        from src.feedback_nodes import check_chapter_feedback_deep_mode_node

        state = make_state(gradio_mode=True, evaluation_mode="deep")
        result = check_chapter_feedback_deep_mode_node(state)
        assert result == "deep_skip"

    def test_gradio_mode_fast_returns_success(self):
        """gradio_mode=True + evaluation_mode=fast should return success"""
        from src.feedback_nodes import check_chapter_feedback_deep_mode_node

        state = make_state(gradio_mode=True, evaluation_mode="fast")
        result = check_chapter_feedback_deep_mode_node(state)
        assert result == "success"

    def test_non_gradio_deep_mode_action_success_returns_deep_skip(self):
        """gradio_mode=False + evaluation_mode=deep + action=success -> deep_skip"""
        from src.feedback_nodes import check_chapter_feedback_deep_mode_node

        state = make_state(gradio_mode=False, evaluation_mode="deep",
                          chapter_feedback_action="success")
        result = check_chapter_feedback_deep_mode_node(state)
        assert result == "deep_skip"

    def test_non_gradio_fast_mode_action_success_returns_success(self):
        """gradio_mode=False + evaluation_mode=fast + action=success -> success"""
        from src.feedback_nodes import check_chapter_feedback_deep_mode_node

        state = make_state(gradio_mode=False, evaluation_mode="fast",
                          chapter_feedback_action="success")
        result = check_chapter_feedback_deep_mode_node(state)
        assert result == "success"

    def test_has_error_returns_failure(self):
        """When chapter_feedback_error is set, should return failure"""
        from src.feedback_nodes import check_chapter_feedback_deep_mode_node

        state = make_state(gradio_mode=False, evaluation_mode="deep",
                          chapter_feedback_error="Some error occurred")
        result = check_chapter_feedback_deep_mode_node(state)
        assert result == "failure"

    def test_action_retry_returns_retry(self):
        """When action=retry, should return retry"""
        from src.feedback_nodes import check_chapter_feedback_deep_mode_node

        state = make_state(gradio_mode=False, evaluation_mode="deep",
                          chapter_feedback_action="retry")
        result = check_chapter_feedback_deep_mode_node(state)
        assert result == "retry"

    def test_action_none_deep_mode_returns_deep_skip(self):
        """When action=None and evaluation_mode=deep, should return deep_skip"""
        from src.feedback_nodes import check_chapter_feedback_deep_mode_node

        state = make_state(gradio_mode=False, evaluation_mode="deep",
                          chapter_feedback_action=None)
        result = check_chapter_feedback_deep_mode_node(state)
        assert result == "deep_skip"

    def test_action_none_fast_mode_returns_success(self):
        """When action=None and evaluation_mode=fast, should return success"""
        from src.feedback_nodes import check_chapter_feedback_deep_mode_node

        state = make_state(gradio_mode=False, evaluation_mode="fast",
                          chapter_feedback_action=None)
        result = check_chapter_feedback_deep_mode_node(state)
        assert result == "success"

    def test_unknown_action_returns_failure(self):
        """When action is unknown (not success/retry), should return failure"""
        from src.feedback_nodes import check_chapter_feedback_deep_mode_node

        state = make_state(gradio_mode=False, evaluation_mode="deep",
                          chapter_feedback_action="unknown_action")
        result = check_chapter_feedback_deep_mode_node(state)
        assert result == "failure"
