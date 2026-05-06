"""Tests for SupervisorNode closed-loop revision (new WritingSupervisor architecture)"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any

from src.state import NovelState


class TestNovelStateRevisionFields:
    """Test NovelState has required revision fields"""

    def test_novel_state_has_revision_fields(self):
        """Verify NovelState has revision_context, supervisor_recheck_count, max_revision_loops"""
        state = NovelState(
            user_intent="测试",
            min_chapters=10
        )

        assert hasattr(state, 'revision_context')
        assert hasattr(state, 'supervisor_recheck_count')
        assert hasattr(state, 'max_revision_loops')
        assert state.revision_context is None
        assert state.supervisor_recheck_count == 0
        assert state.max_revision_loops == 3


class TestRevisionContextInState:
    """Test revision context handling in NovelState"""

    def test_revision_context_default_is_none(self):
        """Test revision_context defaults to None"""
        state = NovelState(user_intent="测试")
        assert state.revision_context is None

    def test_revision_notes_default_is_empty(self):
        """Test revision_notes defaults to empty string"""
        state = NovelState(user_intent="测试")
        assert state.revision_notes == ""

    def test_revision_needed_default_is_false(self):
        """Test revision_needed defaults to False"""
        state = NovelState(user_intent="测试")
        assert state.revision_needed is False

    def test_revision_priority_default_is_none(self):
        """Test revision_priority defaults to 'none'"""
        state = NovelState(user_intent="测试")
        assert state.revision_priority == "none"


class TestSupervisorResultHandling:
    """Test supervisor_result handling"""

    def test_supervisor_result_in_state(self):
        """Test supervisor_result field exists in NovelState"""
        state = NovelState(user_intent="测试")
        assert hasattr(state, 'supervisor_result')
        assert state.supervisor_result is None

    def test_supervisor_result_dict_format(self):
        """Test supervisor_result can store a dict"""
        state = NovelState(user_intent="测试")
        state.supervisor_result = {
            "revision_needed": True,
            "revision_priority": "high",
            "revision_notes": "时间线不一致",
            "quality_score": 7.0
        }

        assert state.supervisor_result["revision_needed"] is True
        assert state.supervisor_result["revision_priority"] == "high"


class TestWritingSupervisorRevisionFlow:
    """Test revision flow with WritingSupervisor"""

    def test_review_result_has_revision_info(self):
        """Test ReviewResult contains revision information"""
        from src.multi_agent import ReviewResult
        from src.multi_agent.types import Suggestion, CheckCategory, Priority

        result = ReviewResult(
            chapter_index=1,
            needs_revision=True,
            suggestions=[
                Suggestion(
                    category=CheckCategory.CONSISTENCY,
                    priority=Priority.HIGH,
                    issue="时间线不一致",
                    location="第3段",
                    current_text="2019年",
                    suggested_change="2020年"
                )
            ],
            reasoning="发现一致性问题",
            execution_time=1.0,
            quality_score=6.5
        )

        assert result.needs_revision is True
        assert len(result.suggestions) == 1
        assert result.suggestions[0].priority == Priority.HIGH

    def test_review_result_no_revision(self):
        """Test ReviewResult when no revision needed"""
        from src.multi_agent import ReviewResult

        result = ReviewResult(
            chapter_index=1,
            needs_revision=False,
            suggestions=[],
            reasoning="章节质量良好",
            execution_time=0.8,
            quality_score=9.0
        )

        assert result.needs_revision is False
        assert len(result.suggestions) == 0
        assert result.quality_score == 9.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])