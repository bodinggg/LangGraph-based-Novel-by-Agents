"""
Tests for src/agent.py - TDD RED phase
"""
import pytest
from unittest.mock import MagicMock, patch
from src.agent import (
    OutlineGeneratorAgent,
    CharacterAgent,
    WriterAgent,
    ReflectAgent,
    EntityAgent
)
from src.state import NovelState
from src.model import NovelOutline, ChapterOutline, Character, ChapterContent, VolumeOutline
from src.config_loader import BaseConfig
from src.storage import NovelStorage


@pytest.fixture
def mock_model_manager():
    """Mock model manager that returns predictable responses"""
    mock = MagicMock()
    mock.generate.return_value = '{"result": "test output"}'
    return mock


@pytest.fixture
def base_config():
    """Base configuration for agents"""
    return BaseConfig(
        max_new_tokens=3000,
        temperature=0.7,
        top_p=0.9,
        min_chapters=10,
        volume=1,
        master_outline=True
    )


@pytest.fixture
def novel_storage():
    """Create a mock NovelStorage"""
    storage = MagicMock(spec=NovelStorage)
    storage.load_outline.return_value = NovelOutline(
        title="测试小说",
        genre="玄幻",
        theme="测试主题",
        setting="测试世界观",
        plot_summary="测试情节概要",
        master_outline=[
            VolumeOutline(
                title="第一卷",
                chapters_range="1-10",
                theme="起始",
                key_turning_points=["转折点1"]
            )
        ],
        chapters=[
            ChapterOutline(
                title="第一章 测试章节",
                summary="这是测试章节的摘要",
                key_events=["事件1", "事件2"],
                characters_involved=["角色A", "角色B"],
                setting="测试场景"
            )
        ],
        characters=["角色A", "角色B"]
    )
    storage.load_characters.return_value = [
        Character(
            name="角色A",
            background="测试背景",
            personality="开朗",
            goals=["目标1"],
            conflicts=["冲突1"],
            arc="成长弧线"
        )
    ]
    storage.load_chapter.return_value = ChapterContent(
        title="第一章 测试章节",
        content="测试内容"
    )
    return storage


@pytest.fixture
def sample_state(novel_storage):
    """Create a sample NovelState for testing"""
    return NovelState(
        novel_storage=novel_storage,
        user_intent="创作一个玄幻小说",
        min_chapters=10,
        attempt=0,
        max_attempts=10
    )


class TestOutlineGeneratorAgent:
    """Test OutlineGeneratorAgent"""

    def test_init(self, mock_model_manager, base_config):
        """Test agent initialization"""
        agent = OutlineGeneratorAgent(mock_model_manager, base_config)
        assert agent.model_manager is mock_model_manager
        assert agent.config is base_config

    def test_generate_outline_returns_string(self, mock_model_manager, base_config, sample_state):
        """Test generate_outline returns a string (raw LLM response)"""
        agent = OutlineGeneratorAgent(mock_model_manager, base_config)
        mock_model_manager.generate.return_value = '{"title": "测试大纲"}'

        result = agent.generate_outline(sample_state)

        assert isinstance(result, str)
        assert mock_model_manager.generate.called

    def test_generate_outline_accepts_novel_state(self, mock_model_manager, base_config, sample_state):
        """Test generate_outline accepts NovelState parameter"""
        agent = OutlineGeneratorAgent(mock_model_manager, base_config)
        mock_model_manager.generate.return_value = '{"title": "测试大纲"}'

        # Should accept NovelState without raising
        result = agent.generate_outline(sample_state)
        assert result is not None

    def test_generate_master_outline_returns_string(self, mock_model_manager, base_config):
        """Test generate_master_outline returns a string"""
        agent = OutlineGeneratorAgent(mock_model_manager, base_config)
        mock_model_manager.generate.return_value = '{"title": "测试总纲", "chapters": []}'

        result = agent.generate_master_outline("创作一个玄幻小说")

        assert isinstance(result, str)

    def test_generate_volume_chapters_returns_string(self, mock_model_manager, base_config, sample_state):
        """Test generate_volume_chapters returns a string"""
        agent = OutlineGeneratorAgent(mock_model_manager, base_config)
        mock_model_manager.generate.return_value = '{"chapters": []}'

        # Need to set validated_outline for this to work
        sample_state.validated_outline = sample_state.novel_storage.load_outline()

        result = agent.generate_volume_chapters(sample_state, 0)

        assert isinstance(result, str)


class TestCharacterAgent:
    """Test CharacterAgent"""

    def test_init(self, mock_model_manager, base_config):
        """Test agent initialization"""
        agent = CharacterAgent(mock_model_manager, base_config)
        assert agent.model_manager is mock_model_manager
        assert agent.config is base_config

    def test_generate_characters_returns_string(self, mock_model_manager, base_config, sample_state):
        """Test generate_characters returns a string (raw LLM response)"""
        agent = CharacterAgent(mock_model_manager, base_config)
        mock_model_manager.generate.return_value = '[{"name": "角色A", "background": "背景"}]'

        result = agent.generate_characters(sample_state)

        assert isinstance(result, str)
        assert mock_model_manager.generate.called

    def test_generate_characters_accepts_novel_state(self, mock_model_manager, base_config, sample_state):
        """Test generate_characters accepts NovelState parameter"""
        agent = CharacterAgent(mock_model_manager, base_config)
        mock_model_manager.generate.return_value = '[{"name": "角色A"}]'

        # Should accept NovelState without raising
        result = agent.generate_characters(sample_state)
        assert result is not None


class TestWriterAgent:
    """Test WriterAgent"""

    def test_init(self, mock_model_manager, base_config):
        """Test agent initialization"""
        agent = WriterAgent(mock_model_manager, base_config)
        assert agent.model_manager is mock_model_manager
        assert agent.config is base_config
        # Should initialize feedback processor
        assert hasattr(agent, 'feedback_processor')
        assert hasattr(agent, 'content_referencer')

    def test_write_chapter_returns_string(self, mock_model_manager, base_config, sample_state):
        """Test write_chapter returns a string (raw LLM response)"""
        agent = WriterAgent(mock_model_manager, base_config)
        mock_model_manager.generate.return_value = '{"title": "第一章", "content": "测试内容"}'

        # Set required state for writing
        sample_state.current_chapter_index = 0
        sample_state.validated_chapter_draft = None
        sample_state.validated_evaluation = None

        result = agent.write_chapter(sample_state)

        assert isinstance(result, str)
        assert mock_model_manager.generate.called

    def test_write_chapter_accepts_novel_state(self, mock_model_manager, base_config, sample_state):
        """Test write_chapter accepts NovelState parameter"""
        agent = WriterAgent(mock_model_manager, base_config)
        mock_model_manager.generate.return_value = '{"title": "第一章", "content": "测试内容"}'

        sample_state.current_chapter_index = 0
        sample_state.validated_chapter_draft = None
        sample_state.validated_evaluation = None

        # Should accept NovelState without raising
        result = agent.write_chapter(sample_state)
        assert result is not None


class TestReflectAgent:
    """Test ReflectAgent"""

    def test_init(self, mock_model_manager, base_config):
        """Test agent initialization"""
        agent = ReflectAgent(mock_model_manager, base_config)
        assert agent.model_manager is mock_model_manager
        assert agent.config is base_config
        assert hasattr(agent, 'system_prompt')
        assert hasattr(agent, 'evaluation_reporter')

    def test_evaluate_chapter_returns_string(self, mock_model_manager, base_config, sample_state):
        """Test evaluate_chapter returns a string (raw LLM response)"""
        agent = ReflectAgent(mock_model_manager, base_config)
        mock_model_manager.generate.return_value = '{"score": 7, "passes": true}'

        # Set required state for evaluation
        sample_state.current_chapter_index = 0
        sample_state.validated_chapter_draft = ChapterContent(
            title="第一章 测试章节",
            content="测试章节内容"
        )

        result = agent.evaluate_chapter(sample_state)

        assert isinstance(result, str)
        assert mock_model_manager.generate.called

    def test_evaluate_chapter_accepts_novel_state(self, mock_model_manager, base_config, sample_state):
        """Test evaluate_chapter accepts NovelState parameter"""
        agent = ReflectAgent(mock_model_manager, base_config)
        mock_model_manager.generate.return_value = '{"score": 7, "passes": true}'

        sample_state.current_chapter_index = 0
        sample_state.validated_chapter_draft = ChapterContent(
            title="第一章 测试章节",
            content="测试章节内容"
        )

        # Should accept NovelState without raising
        result = agent.evaluate_chapter(sample_state)
        assert result is not None


class TestEntityAgent:
    """Test EntityAgent"""

    def test_init(self, mock_model_manager, base_config):
        """Test agent initialization"""
        agent = EntityAgent(mock_model_manager, base_config)
        assert agent.model_manager is mock_model_manager
        assert agent.config is base_config
        assert hasattr(agent, 'system_prompt')

    def test_generate_entities_returns_string(self, mock_model_manager, base_config, sample_state):
        """Test generate_entities returns a string (raw LLM response)"""
        agent = EntityAgent(mock_model_manager, base_config)
        mock_model_manager.generate.return_value = '{"characters": {}, "organizations": {}}'

        # Set required state for entity generation
        sample_state.current_chapter_index = 0
        sample_state.validated_chapter_draft = ChapterContent(
            title="第一章 测试章节",
            content="测试章节内容"
        )

        result = agent.generate_entities(sample_state)

        assert isinstance(result, str)
        assert mock_model_manager.generate.called

    def test_generate_entities_accepts_novel_state(self, mock_model_manager, base_config, sample_state):
        """Test generate_entities accepts NovelState parameter"""
        agent = EntityAgent(mock_model_manager, base_config)
        mock_model_manager.generate.return_value = '{"characters": {}}'

        sample_state.current_chapter_index = 0
        sample_state.validated_chapter_draft = ChapterContent(
            title="第一章 测试章节",
            content="测试章节内容"
        )

        # Should accept NovelState without raising
        result = agent.generate_entities(sample_state)
        assert result is not None
