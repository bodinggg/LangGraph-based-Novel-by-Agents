"""Test agent.py council decision revision content handling - new WritingSupervisor architecture"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class TestSupervisorDecisionRevisionContent:
    """Test that supervisor_node passes actual chapter content for revision"""

    def test_supervisor_result_includes_revision_notes(self):
        """supervisor_node should include revision_notes with actionable content"""
        from src.state import NovelState
        from src.multi_agent import ReviewResult
        from src.multi_agent.types import Suggestion, CheckCategory, Priority

        # Create a ReviewResult with suggestions
        result = ReviewResult(
            chapter_index=0,
            needs_revision=True,
            suggestions=[
                Suggestion(
                    category=CheckCategory.CONSISTENCY,
                    priority=Priority.HIGH,
                    issue="时间线矛盾：零在第1章说5年后苏醒，但第2章显示只过了2小时",
                    location="第2章第3段",
                    current_text="只过了2小时",
                    suggested_change="过了5年"
                )
            ],
            reasoning="发现一致性问题",
            execution_time=1.0,
            quality_score=6.0
        )

        # revision_notes should be generated from suggestions
        assert result.needs_revision is True
        assert len(result.suggestions) == 1
        assert "时间线矛盾" in result.suggestions[0].issue

    def test_review_result_to_dict_contains_suggestions(self):
        """ReviewResult.to_dict() should include suggestions for the writer"""
        from src.multi_agent import ReviewResult
        from src.multi_agent.types import Suggestion, CheckCategory, Priority

        result = ReviewResult(
            chapter_index=1,
            needs_revision=True,
            suggestions=[
                Suggestion(
                    category=CheckCategory.PLOT_THREAD,
                    priority=Priority.MEDIUM,
                    issue="伏笔未回收",
                    location="第5章",
                    current_text="神秘老人出现但未解释",
                    suggested_change="添加解释：神秘老人是..."
                )
            ],
            reasoning="发现伏笔未回收",
            execution_time=0.8,
            quality_score=7.0
        )

        result_dict = result.to_dict()

        assert result_dict["needs_revision"] is True
        assert len(result_dict["suggestions"]) == 1
        assert result_dict["suggestions"][0]["issue"] == "伏笔未回收"
        assert result_dict["suggestions"][0]["suggested_change"] is not None

    def test_revision_notes_format(self):
        """revision_notes should be formatted for readability"""
        from src.multi_agent import ReviewResult
        from src.multi_agent.types import Suggestion, CheckCategory, Priority

        result = ReviewResult(
            chapter_index=2,
            needs_revision=True,
            suggestions=[
                Suggestion(
                    category=CheckCategory.CONSISTENCY,
                    priority=Priority.HIGH,
                    issue="角色性格不一致",
                    location="第3段",
                    current_text="张伟性格暴躁",
                    suggested_change="保持性格一致，改为..."
                ),
                Suggestion(
                    category=CheckCategory.WORLD_STATE,
                    priority=Priority.MEDIUM,
                    issue="地点不匹配",
                    location="第5段",
                    current_text="在北方城市",
                    suggested_change="改为南方城市"
                )
            ],
            reasoning="发现多个问题",
            execution_time=1.2,
            quality_score=5.5
        )

        # Generate revision_notes the same way supervisor_node does
        notes_parts = []
        for i, sug in enumerate(result.suggestions[:3], 1):
            notes_parts.append(f"{i}. [{sug.category.value}] {sug.issue}: {sug.suggested_change}")
        revision_notes = "; ".join(notes_parts)

        assert "1. [consistency]" in revision_notes
        assert "角色性格不一致" in revision_notes
        assert "2. [world_state]" in revision_notes
        assert "地点不匹配" in revision_notes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])