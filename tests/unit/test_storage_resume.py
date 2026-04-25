"""
Unit tests for src/storage.py resume functionality
"""
import pytest
import shutil
from pathlib import Path
from src.storage import NovelStorage, sanitize_novel_title
from src.model import NovelOutline, Character, ChapterContent


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory for testing"""
    storage = NovelStorage("测试恢复小说")
    yield storage
    # Cleanup
    result_dir = Path("result/测试恢复小说_storage")
    if result_dir.exists():
        shutil.rmtree(result_dir, ignore_errors=True)


class TestStorageResumeMethods:
    """Tests for NovelStorage resume-related methods"""

    def test_get_completed_chapter_count_empty(self, temp_storage):
        """Test getting chapter count when no chapters exist"""
        count = temp_storage.get_completed_chapter_count()
        assert count == 0

    def test_get_completed_chapter_count_with_chapters(self, temp_storage):
        """Test getting chapter count after saving chapters"""
        # Save 3 chapters
        for i in range(3):
            chapter = ChapterContent(
                title=f"第{i+1}章",
                content=f"内容{i}"
            )
            temp_storage.save_chapter(i, chapter)

        count = temp_storage.get_completed_chapter_count()
        assert count == 3

    def test_get_novel_title(self, temp_storage):
        """Test extracting novel title from storage path"""
        title = temp_storage.get_novel_title()
        assert title == "测试恢复小说"

    def test_has_outline_false_when_not_exists(self, temp_storage):
        """Test has_outline returns False when outline doesn't exist"""
        assert temp_storage.has_outline() is False

    def test_has_outline_true_after_save(self, temp_storage, sample_novel_outline):
        """Test has_outline returns True after saving outline"""
        temp_storage.save_outline(sample_novel_outline)
        assert temp_storage.has_outline() is True

    def test_has_characters_false_when_not_exists(self, temp_storage):
        """Test has_characters returns False when characters file doesn't exist"""
        assert temp_storage.has_characters() is False

    def test_has_characters_true_after_save(self, temp_storage, sample_character):
        """Test has_characters returns True after saving characters"""
        temp_storage.save_characters([sample_character])
        assert temp_storage.has_characters() is True

    def test_get_storage_info_empty(self, temp_storage):
        """Test get_storage_info when nothing is saved"""
        info = temp_storage.get_storage_info()
        assert info["title"] == "测试恢复小说"
        assert info["chapter_count"] == 0
        assert info["has_outline"] is False
        assert info["has_characters"] is False

    def test_get_storage_info_partial(self, temp_storage, sample_novel_outline):
        """Test get_storage_info with some data saved"""
        temp_storage.save_outline(sample_novel_outline)
        # Save one chapter
        chapter = ChapterContent(title="第1章", content="内容")
        temp_storage.save_chapter(1, chapter)

        info = temp_storage.get_storage_info()
        assert info["title"] == "测试恢复小说"
        assert info["chapter_count"] == 1
        assert info["has_outline"] is True
        assert info["has_characters"] is False

    def test_get_storage_info_complete(self, temp_storage, sample_novel_outline, sample_character):
        """Test get_storage_info with all data saved"""
        temp_storage.save_outline(sample_novel_outline)
        temp_storage.save_characters([sample_character])
        chapter = ChapterContent(title="第1章", content="内容")
        temp_storage.save_chapter(1, chapter)

        info = temp_storage.get_storage_info()
        assert info["title"] == "测试恢复小说"
        assert info["chapter_count"] == 1
        assert info["has_outline"] is True
        assert info["has_characters"] is True


class TestStateManagerListNovels:
    """Tests for StateManager.list_existing_novels"""

    def test_list_existing_novels_empty(self, temp_state_manager):
        """Test listing novels when none exist"""
        novels = temp_state_manager.list_existing_novels()
        assert isinstance(novels, list)

    def test_list_existing_novels_with_storage(self, temp_state_manager, temp_storage, sample_novel_outline):
        """Test listing novels after creating storage"""
        # Save some data
        temp_storage.save_outline(sample_novel_outline)
        chapter = ChapterContent(title="第1章", content="内容")
        temp_storage.save_chapter(1, chapter)

        novels = temp_state_manager.list_existing_novels()
        assert len(novels) >= 1
        # Find our test novel
        test_novel = next((n for n in novels if n["title"] == "测试恢复小说"), None)
        assert test_novel is not None
        assert test_novel["chapter_count"] == 1
        assert test_novel["has_outline"] is True


class TestSanitizeNovelTitle:
    """Tests for sanitize_novel_title path traversal prevention"""

    def test_rejects_path_traversal_with_dots(self):
        """Verify path traversal with '..' is rejected"""
        with pytest.raises(ValueError, match="Invalid novel title"):
            sanitize_novel_title("../../../etc")

        with pytest.raises(ValueError, match="Invalid novel title"):
            sanitize_novel_title("novel/../../etc")

        with pytest.raises(ValueError, match="Invalid novel title"):
            sanitize_novel_title("..")

    def test_rejects_forward_slash(self):
        """Verify forward slash is rejected"""
        with pytest.raises(ValueError, match="Invalid novel title"):
            sanitize_novel_title("novel/secret")

        with pytest.raises(ValueError, match="Invalid novel title"):
            sanitize_novel_title("/etc/passwd")

    def test_rejects_backslash(self):
        """Verify backslash is rejected (Windows path traversal)"""
        with pytest.raises(ValueError, match="Invalid novel title"):
            sanitize_novel_title("novel\\..\\..\\etc")

        with pytest.raises(ValueError, match="Invalid novel title"):
            sanitize_novel_title("C:\\Windows\\System32")

    def test_rejects_null_byte(self):
        """Verify null byte is rejected"""
        with pytest.raises(ValueError, match="Invalid novel title"):
            sanitize_novel_title("novel\0secret")

    def test_rejects_empty_title(self):
        """Verify empty title is rejected"""
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_novel_title("")

        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_novel_title("   ")

    def test_rejects_too_long_title(self):
        """Verify overly long title is rejected"""
        long_title = "a" * 201
        with pytest.raises(ValueError, match="too long"):
            sanitize_novel_title(long_title)

    def test_accepts_valid_title(self):
        """Verify normal titles pass through unchanged"""
        assert sanitize_novel_title("我的小说") == "我的小说"
        assert sanitize_novel_title("Test Novel 123") == "Test Novel 123"
        assert sanitize_novel_title("小说_title-123") == "小说_title-123"

    def test_strips_whitespace(self):
        """Verify whitespace is stripped"""
        assert sanitize_novel_title("  小说名  ") == "小说名"
        assert sanitize_novel_title("\t标题\n") == "标题"
