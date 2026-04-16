"""
Integration tests for src/storage.py
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from src.storage import NovelStorage
from src.model import NovelOutline, Character, ChapterContent, EntityContent


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory for testing"""
    temp_dir = tempfile.mkdtemp()
    # NovelStorage expects relative path "result/{title}_storage"
    # so we need to pass just the title and let it create the path
    storage = NovelStorage("测试小说")
    yield storage
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)
    # Also cleanup the created result directory
    result_dir = Path("result/测试小说_storage")
    if result_dir.exists():
        shutil.rmtree(result_dir, ignore_errors=True)


class TestNovelStorage:
    """Tests for NovelStorage"""

    def test_save_and_load_outline(self, temp_storage, sample_novel_outline):
        """Test saving and loading a novel outline"""
        temp_storage.save_outline(sample_novel_outline)
        loaded = temp_storage.load_outline()
        assert loaded is not None
        assert loaded.title == sample_novel_outline.title
        assert loaded.genre == sample_novel_outline.genre

    def test_load_outline_when_not_exists(self, temp_storage):
        """Test loading outline returns None when file doesn't exist"""
        result = temp_storage.load_outline()
        assert result is None

    def test_save_and_load_characters(self, temp_storage, sample_character):
        """Test saving and loading characters"""
        characters = [sample_character]
        temp_storage.save_characters(characters)
        loaded = temp_storage.load_characters()
        assert loaded is not None
        assert len(loaded) == 1
        assert loaded[0].name == sample_character.name

    def test_load_characters_when_not_exists(self, temp_storage):
        """Test loading characters returns None when file doesn't exist"""
        result = temp_storage.load_characters()
        assert result is None

    def test_save_and_load_chapter(self, temp_storage):
        """Test saving and loading a chapter"""
        chapter = ChapterContent(
            title="第一章 测试",
            content="这是测试内容"
        )
        temp_storage.save_chapter(0, chapter)
        loaded = temp_storage.load_chapter(0)
        assert loaded is not None
        assert loaded.title == chapter.title
        assert loaded.content == chapter.content

    def test_load_chapter_when_not_exists(self, temp_storage):
        """Test loading chapter returns None when file doesn't exist"""
        result = temp_storage.load_chapter(999)
        assert result is None

    def test_load_all_chapters(self, temp_storage):
        """Test loading all chapters"""
        # Save multiple chapters
        for i in range(3):
            chapter = ChapterContent(
                title=f"第{i+1}章",
                content=f"内容{i}"
            )
            temp_storage.save_chapter(i, chapter)

        chapters = temp_storage.load_all_chapters()
        assert len(chapters) == 3

    def test_save_and_load_entity(self, temp_storage):
        """Test saving and loading entity data"""
        entity = EntityContent(
            characters=["角色A"],
            organizations=["组织A"],
            locations=["城市A"],
            events=["事件1"],
            entities=[]
        )
        temp_storage.save_entity(0, entity)
        loaded = temp_storage.load_entity(0)
        assert loaded is not None
        assert len(loaded.locations) == 1
        assert loaded.locations[0] == "城市A"

    def test_load_entity_when_not_exists(self, temp_storage):
        """Test loading entity returns None when file doesn't exists"""
        result = temp_storage.load_entity(999)
        assert result is None

    def test_storage_directory_structure(self, temp_storage):
        """Test that storage creates correct directory structure"""
        assert temp_storage.base_dir.exists()
        assert temp_storage.chapter_dir.exists()
        assert temp_storage.chapter_dir_json.exists()
        assert temp_storage.entity_dir.exists()
