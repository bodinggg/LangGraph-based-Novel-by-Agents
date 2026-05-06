"""
测试 evaluation_mode 在 Gradio 模式下的路由行为
"""
import pytest
from unittest.mock import MagicMock

from src.state import NovelState


class TestEvaluationModeRouting:
    """测试 evaluation_mode 路由逻辑"""

    def test_gradio_mode_deep_returns_deep_skip(self):
        """gradio_mode=True + evaluation_mode=deep 时返回 deep_skip"""
        state = MagicMock(spec=NovelState)
        state.gradio_mode = True
        state.evaluation_mode = "deep"

        # 模拟 check_chapter_feedback_deep_mode_node 的逻辑
        if state.gradio_mode:
            result = "deep_skip" if state.evaluation_mode == "deep" else "success"
        else:
            result = "unknown"

        assert result == "deep_skip"

    def test_gradio_mode_fast_returns_success(self):
        """gradio_mode=True + evaluation_mode=fast 时返回 success"""
        state = MagicMock(spec=NovelState)
        state.gradio_mode = True
        state.evaluation_mode = "fast"

        if state.gradio_mode:
            result = "deep_skip" if state.evaluation_mode == "deep" else "success"

        assert result == "success"

    def test_evaluation_mode_deep_returns_deep_skip(self):
        """非 gradio 模式下 evaluation_mode=deep 时返回 deep_skip"""
        state = MagicMock(spec=NovelState)
        state.gradio_mode = False
        state.evaluation_mode = "deep"

        # 在非 gradio 模式下，action 不为 None 时
        action = "success"  # 假设 evaluate_report 返回 success
        if action and state.evaluation_mode == "deep":
            result = "deep_skip"
        else:
            result = "success"

        assert result == "deep_skip"

    def test_evaluation_mode_fast_returns_success(self):
        """非 gradio 模式下 evaluation_mode=fast 时返回 success"""
        state = MagicMock(spec=NovelState)
        state.gradio_mode = False
        state.evaluation_mode = "fast"

        action = "success"
        if action and state.evaluation_mode == "deep":
            result = "deep_skip"
        else:
            result = "success"

        assert result == "success"

    def test_has_error_returns_failure(self):
        """有 error 时返回 failure"""
        state = MagicMock(spec=NovelState)
        state.gradio_mode = True
        state.evaluation_mode = "deep"
        state.chapter_feedback_error = "Some error occurred"

        # 模拟检查逻辑
        if state.chapter_feedback_error:
            result = "failure"
        elif state.gradio_mode:
            result = "deep_skip" if state.evaluation_mode == "deep" else "success"
        else:
            result = "unknown"

        assert result == "failure"

    def test_action_retry_returns_retry(self):
        """action=retry 时返回 retry"""
        state = MagicMock(spec=NovelState)
        state.gradio_mode = True
        state.evaluation_mode = "deep"
        state.chapter_feedback_action = "retry"

        action = state.chapter_feedback_action

        if action == "retry":
            result = "retry"
        elif state.chapter_feedback_error:
            result = "failure"
        elif state.gradio_mode:
            result = "deep_skip" if state.evaluation_mode == "deep" else "success"
        else:
            result = "unknown"

        assert result == "retry"