"""
TDD Phase 2: WriterAgent StoryBible Context Enhancement

RED: Write failing test first
- Test that WriterAgent receives StoryBible context (active_plot_threads, character_arcs, world_state)
- Test that revision feedback includes specific issues from council_node
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.agent import WriterAgent, BaseConfig
from src.state import NovelState
from src.model import CharacterArc, CharacterArcStage, PlotThread, WorldState, NovelOutline, ChapterOutline, VolumeOutline
from src.storage import NovelStorage


def create_test_outline():
    """Create a test novel outline"""
    chapters = [
        ChapterOutline(title="觉醒", summary="林远意外获得芯片能力", key_events=["获得芯片"], characters_involved=["林远"], setting="新京市"),
        ChapterOutline(title="追踪", summary="黑影组织开始追杀", key_events=["追杀开始"], characters_involved=["林远", "苏晴"], setting="新京市"),
        ChapterOutline(title="逃亡", summary="林远与苏晴一起逃亡", key_events=["逃亡"], characters_involved=["林远", "苏晴"], setting="新京市旧城区"),
        ChapterOutline(title="觉醒", summary="林远发现芯片秘密", key_events=["发现秘密"], characters_involved=["林远", "苏晴"], setting="新京市"),
        ChapterOutline(title="追踪", summary="黑影组织追击", key_events=["追击"], characters_involved=["林远", "苏晴"], setting="新京市"),
    ]
    volume = VolumeOutline(
        title="星尘觉醒",
        chapters_range="1-5",
        summary="第一卷",
        theme="成长与觉醒",
        key_turning_points=["林远获得芯片", "苏晴出现", "黑影组织追杀"],
        chapters=chapters
    )
    outline = NovelOutline(
        title="星尘觉醒",
        genre="科幻",
        theme="成长",
        setting="星历2187年 新京市",
        plot_summary="科幻成长故事",
        volumes=[volume],
        chapters=chapters,
        characters=["林远", "苏晴"]
    )
    return outline


def create_mock_characters():
    """Create mock characters (using dict instead of Character model)"""
    return [
        {"name": "林远", "role": "主角", "description": "平凡的工程师，意外获得芯片能力"},
        {"name": "苏晴", "role": "女主", "description": "神秘女子，似乎知道黑影组织的秘密"}
    ]


def create_mock_story_bible():
    """Create StoryBible data that should be passed to WriterAgent"""
    # Character arc - 林远 should be in "觉醒者" stage by chapter 4
    stage1 = CharacterArcStage(
        stage_name="平凡工程师",
        chapter_range="1-3",
        emotional_state="困惑",
        key_moment="意外获得芯片能力"
    )
    stage2 = CharacterArcStage(
        stage_name="觉醒者",
        chapter_range="4-10",
        emotional_state="坚定",
        key_moment="第一次使用芯片能力战斗"
    )
    arc = CharacterArc(
        name="林远",
        arc_stages=[stage1, stage2],
        current_stage_index=1,  # Now in stage 2
        emotional_state="坚定"
    )

    # Plot thread - 黑影组织 should be unresolved
    thread = PlotThread(
        id="黑影组织",
        name="黑影组织之谜",
        status="active",
        setup_chapter=2,
        key_events=["林远获得芯片", "苏晴出现", "黑影组织追杀"],
        foreshadow="揭示黑影组织与芯片的关联"
    )

    # World state - current location
    world_state = WorldState(
        chapter_index=3,
        location="新京市·旧城区",
        time="星历2187年·深夜",
        active_factions=["黑影组织", "城市安全局"],
        description="林远被迫逃亡中"
    )

    return {
        "character_arcs": [arc],
        "plot_threads": [thread],
        "world_states": [world_state]
    }


class TestWriterAgentStoryBibleContext:
    """Test that WriterAgent receives StoryBible context"""

    @pytest.fixture
    def writer_agent(self):
        """Create WriterAgent with mock model manager"""
        mock_manager = MagicMock()
        mock_manager.generate.return_value = '{"title": "测试章节", "content": "生成的章节内容"}'
        config = BaseConfig(max_new_tokens=3000, temperature=0.7, top_p=0.9, min_chapters=10, volume=1, master_outline=True)
        return WriterAgent(model_manager=mock_manager, config=config)

    @pytest.fixture
    def novel_state_with_storybible(self):
        """Create NovelState with StoryBible data"""
        outline = create_test_outline()
        story_bible_data = create_mock_story_bible()

        # Create storage mock
        storage = MagicMock(spec=NovelStorage)

        state = NovelState(
            user_intent="创作一部科幻小说",
            min_chapters=50,
            validated_outline=outline,
            validated_characters=[],  # Empty characters list
            current_chapter_index=4,  # Writing chapter 4
            raw_current_chapter="",  # Empty - we're generating new content
            novel_storage=storage,
            # Add council decision for revision context
            council_decision={
                "decision": "revise",
                "reasoning": "角色弧线推进过快，需要更多内心描写",
                "affected_agents": ["CharacterArcAgent"]
            }
        )
        # Attach story bible data as if loaded from storage
        state._story_bible_data = story_bible_data
        return state

    def test_writer_prompt_includes_character_arcs(self, writer_agent, novel_state_with_storybible):
        """Test that the prompt sent to LLM includes character arc information

        RED: This should FAIL until we implement StoryBible context enhancement
        """
        # Capture the prompt that would be sent to LLM
        captured_messages = []

        def mock_generate(messages, config=None, **kwargs):
            captured_messages.extend(messages)
            return '{"title": "测试章节", "content": "生成的章节内容"}'

        writer_agent.model_manager.generate = mock_generate

        # Call write_chapter
        result = writer_agent.write_chapter(novel_state_with_storybible)

        # Check that the prompt includes character arc info
        full_prompt = "\n".join([m.get("content", "") if isinstance(m, dict) else str(m) for m in captured_messages])

        # This assertion will FAIL until we implement context enhancement
        assert "林远" in full_prompt, "Prompt should include character name"
        assert "觉醒者" in full_prompt, "Prompt should include current character arc stage"
        assert "坚定" in full_prompt, "Prompt should include character's emotional state"

    def test_writer_prompt_includes_active_plot_threads(self, writer_agent, novel_state_with_storybible):
        """Test that the prompt includes active plot threads

        RED: This should FAIL until we implement StoryBible context enhancement
        """
        captured_messages = []

        def mock_generate(messages, config=None, **kwargs):
            captured_messages.extend(messages)
            return '{"title": "测试章节", "content": "生成的章节内容"}'

        writer_agent.model_manager.generate = mock_generate

        result = writer_agent.write_chapter(novel_state_with_storybible)

        full_prompt = "\n".join([m.get("content", "") if isinstance(m, dict) else str(m) for m in captured_messages])

        # This assertion will FAIL until we implement context enhancement
        assert "黑影组织" in full_prompt, "Prompt should include plot thread ID"
        assert "active" in full_prompt.lower() or "进行中" in full_prompt, "Prompt should indicate plot thread status"

    def test_writer_prompt_includes_world_state(self, writer_agent, novel_state_with_storybible):
        """Test that the prompt includes world state information

        RED: This should FAIL until we implement StoryBible context enhancement
        """
        captured_messages = []

        def mock_generate(messages, config=None, **kwargs):
            captured_messages.extend(messages)
            return '{"title": "测试章节", "content": "生成的章节内容"}'

        writer_agent.model_manager.generate = mock_generate

        result = writer_agent.write_chapter(novel_state_with_storybible)

        full_prompt = "\n".join([m.get("content", "") if isinstance(m, dict) else str(m) for m in captured_messages])

        # This assertion will FAIL until we implement context enhancement
        assert "新京市" in full_prompt, "Prompt should include location"
        assert "深夜" in full_prompt or "星历2187" in full_prompt, "Prompt should include time context"

    def test_revision_feedback_includes_specific_issues(self, writer_agent):
        """Test that revision feedback includes specific issues from council_node

        RED: This should FAIL until we implement revision context passing
        """
        # Create state with council revision decision
        outline = create_test_outline()

        # Create mock storage
        mock_storage = MagicMock(spec=NovelStorage)
        mock_storage.load_characters.return_value = [
            MagicMock(name="林远", personality="坚韧", goals=["揭开芯片秘密"]),
            MagicMock(name="苏晴", personality="神秘", goals=["躲避黑影组织"])
        ]
        mock_storage.load_outline.return_value = outline
        mock_storage.load_chapter.return_value = MagicMock(content="前一章的内容...")
        mock_storage.load_entity.return_value = None

        revision_state = NovelState(
            user_intent="创作一部科幻小说",
            min_chapters=50,
            validated_outline=outline,
            validated_characters=[],  # Empty to avoid validation issues
            current_chapter_index=4,
            raw_current_chapter="这是需要修改的章节内容...",
            novel_storage=mock_storage,
            council_decision={
                "decision": "revise",
                "reasoning": "角色弧线推进过快，从'困惑'直接跳到'坚定'缺乏过渡",
                "affected_agents": ["CharacterArcAgent"],
                "specific_issue": "林远的情感转变需要至少一个关键事件来支撑"
            },
            revision_needed=True,
            revision_priority="high",
            revision_notes="角色弧线需要更多过渡"
        )

        captured_messages = []

        def mock_generate(messages, config=None, **kwargs):
            captured_messages.extend(messages)
            return "修改后的章节内容"

        writer_agent.model_manager.generate = mock_generate

        result = writer_agent.write_chapter(revision_state)

        full_prompt = "\n".join([m.get("content", "") if isinstance(m, dict) else str(m) for m in captured_messages])

        # This assertion will FAIL until we implement revision context passing
        assert "角色弧线" in full_prompt or "CharacterArc" in full_prompt, "Prompt should include revision topic"
        assert "林远" in full_prompt, "Prompt should reference the specific character"


class TestWriterAgentRevisionContext:
    """Test WriterAgent handles revision context properly"""

    @pytest.fixture
    def writer_agent(self):
        mock_manager = MagicMock()
        mock_manager.generate.return_value = '{"title": "测试章节", "content": "生成的章节内容"}'
        config = BaseConfig(max_new_tokens=3000, temperature=0.7, top_p=0.9, min_chapters=10, volume=1, master_outline=True)
        return WriterAgent(model_manager=mock_manager, config=config)

    def test_revision_state_includes_council_feedback(self, writer_agent):
        """Test that when council_decision is present, it's included in the prompt

        RED: This should FAIL until we implement council feedback passing
        """
        outline = create_test_outline()

        # Create mock storage
        mock_storage = MagicMock(spec=NovelStorage)
        mock_storage.load_characters.return_value = [
            MagicMock(name="林远", personality="坚韧", goals=["揭开芯片秘密"]),
            MagicMock(name="苏晴", personality="神秘", goals=["躲避黑影组织"])
        ]
        mock_storage.load_outline.return_value = outline
        mock_storage.load_chapter.return_value = MagicMock(content="前一章的内容...")
        mock_storage.load_entity.return_value = None

        state = NovelState(
            user_intent="创作一部科幻小说",
            min_chapters=50,
            validated_outline=outline,
            validated_characters=[],  # Empty to avoid validation issues
            current_chapter_index=4,
            raw_current_chapter="",  # Empty for new generation
            novel_storage=mock_storage,
            # Council decision with specific feedback
            council_decision={
                "decision": "revise",
                "reasoning": "一致性问题：时间线从'深夜'跳到'黎明'缺少过渡",
                "affected_agents": ["ConsistencyAgent"]
            }
        )

        captured_messages = []

        def mock_generate(messages, config=None, **kwargs):
            captured_messages.extend(messages)
            return '{"title": "测试章节", "content": "生成的章节内容"}'

        writer_agent.model_manager.generate = mock_generate

        result = writer_agent.write_chapter(state)

        full_prompt = "\n".join([m.get("content", "") if isinstance(m, dict) else str(m) for m in captured_messages])

        # Should include the specific issue from council
        assert "深夜" in full_prompt or "时间线" in full_prompt, "Prompt should include consistency issue details"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])