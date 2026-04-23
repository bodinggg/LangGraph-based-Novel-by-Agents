"""
Tests for app.py resume logic - checkpoint恢复场景
验证断点恢复时 checkpoint 中某些字段为 None/null 的处理
"""
import pytest
from unittest.mock import MagicMock, patch
from src.model import NovelOutline, ChapterOutline, Character, VolumeOutline


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


@pytest.fixture
def sample_characters():
    """示例角色列表"""
    return [
        Character(
            name="角色A",
            background="背景A",
            personality="性格A",
            goals=["目标A"],
            conflicts=["冲突A"],
            arc="成长A"
        ),
        Character(
            name="角色B",
            background="背景B",
            personality="性格B",
            goals=["目标B"],
            conflicts=["冲突B"],
            arc="成长B"
        ),
    ]


class TestAppResumeCheckpointRestore:
    """
    模拟 app.py 从 checkpoint 恢复的场景
    checkpoint 中 validated_outline, raw_master_outline, validated_characters 可能为 None/null
    """

    def test_resume_with_null_validated_characters(self, sample_characters):
        """
        测试：checkpoint 中 validated_characters 为 null
        期望：不会在迭代时崩溃
        实际：checkpoint.get("validated_characters", []) 返回 None（因为键存在但值为 null）
        """
        # 模拟 checkpoint，其中 validated_characters 为 null（JSON null）
        checkpoint = {
            "validated_outline": None,  # null in JSON
            "raw_master_outline": None,  # null in JSON
            "validated_characters": None,  # null in JSON - 这是问题所在！
            "current_chapter_index": 1,
            "novel_title": "测试小说",
        }

        # 模拟 app.py 的恢复逻辑
        # 问题：checkpoint.get("validated_characters", []) 当键存在值为null时，返回None而不是[]
        result = checkpoint.get("validated_characters", [])
        print(f"checkpoint.get('validated_characters', []) = {result}")
        print(f"type = {type(result)}")

        # 这会导致 TypeError: 'NoneType' object is not iterable
        with pytest.raises(TypeError, match="'NoneType' object is not iterable"):
            for c in result:  # 如果 result 是 None，这里会崩溃
                pass

    def test_resume_fix_with_none_check(self, sample_characters):
        """
        修复：在迭代前检查是否为 None
        """
        checkpoint = {
            "validated_characters": None,
        }

        # 正确做法：先检查是否为 None
        validated_characters = checkpoint.get("validated_characters") or []
        assert validated_characters == []

        # 现在可以安全迭代
        result_list = []
        for c in validated_characters:
            result_list.append(c)
        assert result_list == []

    def test_resume_with_proper_restore(self, sample_novel_outline, sample_characters):
        """
        完整的恢复流程：模拟 app.py + storage 恢复
        关键：优先从 storage 读取，storage 没有时才用 checkpoint
        """
        checkpoint = {
            "validated_outline": None,  # null in checkpoint
            "validated_characters": None,  # null in checkpoint
            "current_chapter_index": 1,
            "completed_chapters": [],
            "novel_title": "测试小说",
        }

        # 模拟 storage
        mock_storage = MagicMock()
        mock_storage.load_outline.return_value = sample_novel_outline
        mock_storage.load_characters.return_value = sample_characters  # storage 有数据
        mock_storage.load_outline_metadata.return_value = {"current_volume_index": 0}

        # app.py 的恢复逻辑（修复版）
        initial_state = {
            "user_intent": checkpoint.get("user_intent", ""),
            "min_chapters": checkpoint.get("min_chapters", 10),
            "gradio_mode": checkpoint.get("gradio_mode", False),
        }

        novel_title = checkpoint.get("novel_title", "")
        if novel_title:  # novel_title 是 "测试小说"，truthy
            initial_state["novel_storage"] = mock_storage

            # 恢复已验证的大纲（从 storage 优先）
            validated_outline = mock_storage.load_outline()
            if validated_outline:
                initial_state["validated_outline"] = validated_outline
                initial_state["validated_chapters"] = validated_outline.chapters

            # 恢复已验证的角色（从 storage 优先）
            stored_characters = mock_storage.load_characters()
            if stored_characters:
                initial_state["validated_characters"] = stored_characters
            else:
                # fallback to checkpoint
                validated_characters = []
                raw_chars = checkpoint.get("validated_characters") or []
                for c in raw_chars:
                    try:
                        validated_characters.append(Character(**c))
                    except Exception:
                        pass
                initial_state["validated_characters"] = validated_characters

            # 恢复卷进度
            outline_meta = mock_storage.load_outline_metadata()
            initial_state["current_volume_index"] = outline_meta.get("current_volume_index", 0)

        # 恢复章节索引（checkpoint 中恢复）
        initial_state["current_chapter_index"] = checkpoint.get("current_chapter_index", 0)
        initial_state["completed_chapters"] = checkpoint.get("completed_chapters", [])

        # 验证恢复结果
        assert initial_state["validated_outline"] == sample_novel_outline
        assert initial_state["validated_characters"] == sample_characters  # 从 storage 恢复
        assert initial_state["validated_chapters"] == sample_novel_outline.chapters
        assert initial_state["current_chapter_index"] == 1
        assert initial_state["current_volume_index"] == 0
        assert initial_state["novel_storage"] == mock_storage


class TestMasterOutlineNodeWithNoneRaw:
    """
    测试 validate_master_outline_node 在 raw_master_outline 为 None 时的行为
    """

    def test_validate_master_outline_with_none_raw_and_validated(self, sample_novel_outline):
        """
        当 validated_outline 存在但 raw_master_outline 为 None 时的处理
        """
        from src.node import validate_master_outline_node

        state = MagicMock()
        state.validated_outline = sample_novel_outline  # 有值，不为 None
        state.outline_validated_error = None
        state.raw_master_outline = None  # 但 raw 是 None

        # 情况1：skip 路径应该能正确返回
        # 条件：validated_outline is not None and outline_validated_error is None
        # 结果：True and True = True，应该 skip
        result = validate_master_outline_node(state)
        assert result["validated_outline"] == sample_novel_outline
        assert "novel_storage" in result

    def test_validate_master_outline_with_both_none(self):
        """
        当 validated_outline 和 raw_master_outline 都为 None 时
        期望：返回 outline_validated_error 而不是崩溃
        """
        from src.node import validate_master_outline_node

        state = MagicMock()
        state.validated_outline = None  # None
        state.outline_validated_error = None
        state.raw_master_outline = None  # None

        # 条件：validated_outline is not None ... -> False，不 skip
        # 会尝试 json.loads(None) -> TypeError (被捕获并转为 error dict)
        result = validate_master_outline_node(state)
        assert result["outline_validated_error"] is not None
        assert "NoneType" in result["outline_validated_error"]
