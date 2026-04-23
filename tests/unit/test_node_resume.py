"""
Tests for node skip logic when resuming from storage
验证断点恢复时节点跳过逻辑
"""
import pytest
from unittest.mock import MagicMock
from src.node import (
    generate_outline_node,
    validate_outline_node,
    generate_characters_node,
    validate_characters_node,
    generate_master_outline_node,
    validate_master_outline_node,
    generate_volume_outline_node,
    validate_volume_outline_node,
)
from src.model import NovelOutline, ChapterOutline, Character, VolumeOutline


@pytest.fixture
def mock_outline_agent():
    agent = MagicMock()
    agent.generate_outline.return_value = '{"title": "测试", "chapters": []}'
    agent.generate_master_outline.return_value = '{"title": "测试", "master_outline": [], "chapters": []}'
    agent.generate_volume_chapters.return_value = '{"chapters": []}'
    return agent


@pytest.fixture
def mock_character_agent():
    agent = MagicMock()
    agent.generate_characters.return_value = '[]'
    return agent


@pytest.fixture
def sample_novel_outline():
    """带分卷的完整大纲"""
    return NovelOutline(
        title="测试小说",
        genre="玄幻",
        theme="测试主题",
        setting="测试世界观",
        plot_summary="测试情节",
        characters=["角色A", "角色B"],
        chapters=[
            ChapterOutline(
                title="第一章 测试",
                summary="测试摘要",
                key_events=["事件1"],
                characters_involved=["角色A"],
                setting="测试场景"
            ),
            ChapterOutline(
                title="第二章 测试",
                summary="测试摘要2",
                key_events=["事件2"],
                characters_involved=["角色B"],
                setting="测试场景2"
            ),
        ],
        master_outline=[
            VolumeOutline(title="卷1", chapters_range="1-1", theme="卷1主题", key_turning_points=["转折1"]),
            VolumeOutline(title="卷2", chapters_range="2-2", theme="卷2主题", key_turning_points=["转折2"]),
        ]
    )


class TestGenerateOutlineNodeSkip:
    """测试 generate_outline_node 跳过逻辑"""

    def test_skip_when_validated_outline_exists(self, mock_outline_agent, sample_novel_outline):
        """当 validated_outline 已存在时，跳过生成"""
        state = MagicMock()
        state.validated_outline = sample_novel_outline
        state.raw_outline = '{"title": "旧大纲"}'

        result = generate_outline_node(state, mock_outline_agent)

        # 不应调用 agent
        mock_outline_agent.generate_outline.assert_not_called()
        assert result["validated_outline"] == sample_novel_outline
        assert result["outline_validated_error"] is None

    def test_normal_flow_when_no_validated_outline(self, mock_outline_agent):
        """当没有 validated_outline 时，正常生成"""
        state = MagicMock()
        state.validated_outline = None
        state.user_intent = "测试意图"
        state.attempt = 0

        result = generate_outline_node(state, mock_outline_agent)

        # 应该调用 agent
        mock_outline_agent.generate_outline.assert_called_once()


class TestValidateOutlineNodeSkip:
    """测试 validate_outline_node 跳过逻辑"""

    def test_skip_when_validated_outline_exists(self, sample_novel_outline):
        """当 validated_outline 已存在时，跳过验证"""
        state = MagicMock()
        state.validated_outline = sample_novel_outline
        state.outline_validated_error = None
        state.raw_outline = '{"title": "测试"}'

        result = validate_outline_node(state)

        # 不应解析 JSON
        assert result["validated_outline"] == sample_novel_outline
        assert result["outline_validated_error"] is None


class TestGenerateCharactersNodeSkip:
    """测试 generate_characters_node 跳过逻辑"""

    def test_skip_when_validated_characters_exist(self, mock_character_agent):
        """当 validated_characters 已存在时，跳过生成"""
        characters = [
            Character(
                name="角色A",
                background="背景A",
                personality="性格A",
                goals=["目标A"],
                conflicts=["冲突A"],
                arc="成长A"
            )
        ]
        state = MagicMock()
        state.validated_characters = characters

        result = generate_characters_node(state, mock_character_agent)

        # 不应调用 agent
        mock_character_agent.generate_characters.assert_not_called()
        assert result["validated_characters"] == characters
        assert result["characters_validated_error"] is None

    def test_normal_flow_when_no_validated_characters(self, mock_character_agent):
        """当没有 validated_characters 时，正常生成"""
        state = MagicMock()
        state.validated_characters = None
        state.validated_outline = MagicMock()
        state.attempt = 0

        result = generate_characters_node(state, mock_character_agent)

        # 应该调用 agent
        mock_character_agent.generate_characters.assert_called_once()


class TestValidateCharactersNodeSkip:
    """测试 validate_characters_node 跳过逻辑"""

    def test_skip_when_validated_characters_exist(self):
        """当 validated_characters 已存在且无错误时，跳过验证"""
        characters = [
            Character(
                name="角色A",
                background="背景A",
                personality="性格A",
                goals=["目标A"],
                conflicts=["冲突A"],
                arc="成长A"
            )
        ]
        state = MagicMock()
        state.validated_characters = characters
        state.characters_validated_error = None
        state.novel_storage = MagicMock()

        result = validate_characters_node(state)

        assert result["validated_characters"] == characters
        assert result["characters_validated_error"] is None


class TestMasterOutlineNodeSkip:
    """测试分卷模式节点跳过逻辑"""

    def test_skip_generate_master_outline_when_exists(self, mock_outline_agent, sample_novel_outline):
        """当已有分卷大纲时，跳过生成"""
        state = MagicMock()
        state.validated_outline = sample_novel_outline
        state.raw_master_outline = '{"title": "测试"}'
        state.user_intent = "测试"

        result = generate_master_outline_node(state, mock_outline_agent)

        mock_outline_agent.generate_master_outline.assert_not_called()
        assert result["validated_outline"] == sample_novel_outline

    def test_skip_validate_master_outline_when_exists(self, sample_novel_outline):
        """当已有分卷大纲时，跳过验证"""
        state = MagicMock()
        state.validated_outline = sample_novel_outline
        state.outline_validated_error = None
        state.raw_master_outline = '{"title": "测试"}'

        result = validate_master_outline_node(state)

        assert result["validated_outline"] == sample_novel_outline
        assert result["outline_validated_error"] is None


class TestVolumeOutlineNodeSkip:
    """测试分卷章节节点跳过逻辑"""

    def test_skip_generate_volume_when_all_chapters_exist(self, mock_outline_agent):
        """当所有章节都已存在时，跳过分卷章节生成"""
        # 构造一个完整的 outline，所有卷的章节都已生成
        outline = MagicMock()
        outline.chapters = [
            ChapterOutline(title="第一章", summary="", key_events=[], characters_involved=[], setting=""),
            ChapterOutline(title="第二章", summary="", key_events=[], characters_involved=[], setting=""),
        ]
        outline.master_outline = [
            VolumeOutline(title="卷1", chapters_range="1-1", theme="", key_turning_points=[]),
            VolumeOutline(title="卷2", chapters_range="2-2", theme="", key_turning_points=[]),
        ]

        state = MagicMock()
        state.validated_outline = outline

        result = generate_volume_outline_node(state, mock_outline_agent)

        mock_outline_agent.generate_volume_chapters.assert_not_called()
        assert result["raw_volume_chapters"] is None
        assert result["current_volume_index"] == 2  # 总卷数

    def test_skip_validate_volume_when_raw_chapters_none(self):
        """当 raw_volume_chapters 为 None 时，跳过验证"""
        state = MagicMock()
        state.raw_volume_chapters = None

        result = validate_volume_outline_node(state)

        assert result["validated_chapters"] == []
        assert result["outline_validated_error"] is None
