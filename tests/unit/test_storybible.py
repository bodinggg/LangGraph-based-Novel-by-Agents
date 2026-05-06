"""
Unit tests for StoryBible models and storage
Phase 1: StoryBible Core Models
"""
import pytest
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

from src.model import (
    PlotThread,
    CharacterArc,
    CharacterArcStage,
    WorldState,
    StoryBibleEntry,
    StoryBibleContent,
    ConsistencyNote,
    EntityContent
)
from src.storage import NovelStorage


# ============== Fixtures ==============

@pytest.fixture
def temp_storage():
    """Create a temporary storage for testing"""
    temp_dir = tempfile.mkdtemp()
    storage = NovelStorage("测试小说")
    yield storage
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_plot_thread():
    """Sample plot thread for testing"""
    return PlotThread(
        id="plot_1",
        name="主情节线",
        status="active",
        setup_chapter=1,
        key_events=["事件1", "事件2"],
        description="测试情节线"
    )


@pytest.fixture
def sample_character_arc():
    """Sample character arc for testing"""
    stage1 = CharacterArcStage(
        stage_name="迷茫",
        chapter_range="1-5",
        emotional_state="失落",
        key_moment="失去亲人"
    )
    stage2 = CharacterArcStage(
        stage_name="成长",
        chapter_range="6-10",
        emotional_state="坚定",
        key_moment="突破自我"
    )
    return CharacterArc(
        name="主角",
        arc_stages=[stage1, stage2],
        current_stage_index=0,
        emotional_state="失落",
        key_moments=["失去亲人"],
        relationships={"配角1": "师徒", "配角2": "竞争对手"}
    )


@pytest.fixture
def sample_world_state():
    """Sample world state for testing"""
    return WorldState(
        chapter_index=1,
        location="王城",
        time="第一年春天",
        active_factions=["王国", "公会"],
        weather="晴朗",
        mood="紧张",
        description="故事开始于王城"
    )


@pytest.fixture
def sample_story_bible(sample_plot_thread, sample_character_arc, sample_world_state):
    """Sample story bible for testing"""
    return StoryBibleContent(
        novel_title="测试小说",
        plot_threads=[sample_plot_thread],
        character_arcs=[sample_character_arc],
        world_states=[sample_world_state]
    )


# ============== PlotThread Tests ==============

class TestPlotThread:
    """Tests for PlotThread model"""

    def test_create_valid_plot_thread(self, sample_plot_thread):
        """Test creating a valid plot thread"""
        assert sample_plot_thread.id == "plot_1"
        assert sample_plot_thread.name == "主情节线"
        assert sample_plot_thread.status == "active"
        assert sample_plot_thread.setup_chapter == 1
        assert len(sample_plot_thread.key_events) == 2

    def test_plot_thread_is_active(self, sample_plot_thread):
        """Test is_active helper method"""
        assert sample_plot_thread.is_active() is True

    def test_plot_thread_is_resolved_when_status_resolved(self):
        """Test is_resolved when status is resolved"""
        thread = PlotThread(
            id="t1", name="n", status="resolved",
            setup_chapter=1, key_events=[], description=""
        )
        assert thread.is_resolved() is True
        assert thread.is_active() is False

    def test_plot_thread_foreshadowed_status(self):
        """Test foreshadowed status"""
        thread = PlotThread(
            id="t1", name="n", status="foreshadowed",
            setup_chapter=1, key_events=[], description=""
        )
        assert thread.is_active() is False
        assert thread.is_resolved() is False


# ============== CharacterArc Tests ==============

class TestCharacterArc:
    """Tests for CharacterArc model"""

    def test_create_valid_character_arc(self, sample_character_arc):
        """Test creating a valid character arc"""
        assert sample_character_arc.name == "主角"
        assert len(sample_character_arc.arc_stages) == 2
        assert sample_character_arc.current_stage_index == 0

    def test_get_current_stage(self, sample_character_arc):
        """Test get_current_stage helper method"""
        current = sample_character_arc.get_current_stage()
        assert current is not None
        assert current.stage_name == "迷茫"

    def test_advance_stage(self, sample_character_arc):
        """Test advance_stage method"""
        assert sample_character_arc.current_stage_index == 0
        sample_character_arc.advance_stage()
        assert sample_character_arc.current_stage_index == 1

    def test_advance_stage_at_end(self, sample_character_arc):
        """Test advance_stage does nothing at last stage"""
        sample_character_arc.current_stage_index = 1  # last stage
        sample_character_arc.advance_stage()
        assert sample_character_arc.current_stage_index == 1  # unchanged

    def test_get_current_stage_out_of_bounds(self):
        """Test get_current_stage returns None when index out of bounds"""
        arc = CharacterArc(name="test", arc_stages=[], current_stage_index=99)
        assert arc.get_current_stage() is None


# ============== WorldState Tests ==============

class TestWorldState:
    """Tests for WorldState model"""

    def test_create_valid_world_state(self, sample_world_state):
        """Test creating a valid world state"""
        assert sample_world_state.location == "王城"
        assert sample_world_state.time == "第一年春天"
        assert len(sample_world_state.active_factions) == 2
        assert sample_world_state.weather == "晴朗"


# ============== StoryBibleContent Tests ==============

class TestStoryBibleContent:
    """Tests for StoryBibleContent model"""

    def test_create_valid_story_bible(self, sample_story_bible):
        """Test creating a valid story bible"""
        assert sample_story_bible.novel_title == "测试小说"
        assert len(sample_story_bible.plot_threads) == 1
        assert len(sample_story_bible.character_arcs) == 1
        assert len(sample_story_bible.world_states) == 1

    def test_get_active_plot_threads(self, sample_story_bible):
        """Test get_active_plot_threads"""
        active = sample_story_bible.get_active_plot_threads()
        assert len(active) == 1
        assert active[0].status == "active"

    def test_get_unresolved_plot_threads(self):
        """Test get_unresolved_plot_threads for foreshadowed threads"""
        thread = PlotThread(
            id="t1", name="伏笔", status="foreshadowed",
            setup_chapter=1, key_events=[], description=""
        )
        sb = StoryBibleContent(plot_threads=[thread])
        unresolved = sb.get_unresolved_plot_threads()
        assert len(unresolved) == 1
        assert unresolved[0].status == "foreshadowed"

    def test_get_character_arc(self, sample_story_bible):
        """Test get_character_arc"""
        arc = sample_story_bible.get_character_arc("主角")
        assert arc is not None
        assert arc.name == "主角"

    def test_get_character_arc_not_found(self, sample_story_bible):
        """Test get_character_arc returns None when not found"""
        arc = sample_story_bible.get_character_arc("不存在")
        assert arc is None

    def test_get_latest_world_state(self, sample_story_bible):
        """Test get_latest_world_state"""
        latest = sample_story_bible.get_latest_world_state()
        assert latest is not None
        assert latest.location == "王城"

    def test_get_latest_world_state_empty(self):
        """Test get_latest_world_state returns None when empty"""
        sb = StoryBibleContent()
        assert sb.get_latest_world_state() is None

    def test_add_and_resolve_consistency_note(self, sample_story_bible):
        """Test add_consistency_note and resolve_consistency_note"""
        note = ConsistencyNote(
            id="note_1",
            issue_type="warning",
            description="时间线可能有误",
            related_chapters=[3, 5]
        )
        sample_story_bible.add_consistency_note(note)
        assert len(sample_story_bible.consistency_notes) == 1

        sample_story_bible.resolve_consistency_note("note_1")
        assert sample_story_bible.consistency_notes[0].resolved is True


# ============== StoryBible Storage Tests ==============

class TestNovelStorageStoryBible:
    """Tests for NovelStorage StoryBible methods"""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Clean up result directory before each test"""
        import shutil
        result_path = Path("result")
        if result_path.exists():
            for item in result_path.iterdir():
                if item.is_dir() and "_storage" in item.name:
                    shutil.rmtree(item, ignore_errors=True)
        yield

    def test_save_and_load_story_bible(self):
        """Test save_story_bible and load_story_bible"""
        storage = NovelStorage("小说A")
        story_bible = StoryBibleContent(novel_title="小说A")
        storage.save_story_bible(story_bible)

        loaded = storage.load_story_bible()
        assert loaded is not None
        assert loaded.novel_title == "小说A"

    def test_load_story_bible_not_exists(self):
        """Test load_story_bible returns None when file doesn't exist"""
        storage = NovelStorage("小说B")
        loaded = storage.load_story_bible()
        assert loaded is None

    def test_has_story_bible(self):
        """Test has_story_bible"""
        storage = NovelStorage("小说C")
        assert storage.has_story_bible() is False
        story_bible = StoryBibleContent(novel_title="小说C")
        storage.save_story_bible(story_bible)
        assert storage.has_story_bible() is True

    def test_update_plot_thread_new(self):
        """Test update_plot_thread adds new thread"""
        storage = NovelStorage("小说D")
        thread = PlotThread(id="t1", name="情节1", status="active", setup_chapter=1)
        storage.update_plot_thread(thread)

        story_bible = storage.load_story_bible()
        assert len(story_bible.plot_threads) == 1
        assert story_bible.plot_threads[0].id == "t1"

    def test_update_plot_thread_existing(self):
        """Test update_plot_thread updates existing thread"""
        storage = NovelStorage("小说E")
        thread = PlotThread(id="t1", name="情节1", status="active", setup_chapter=1)
        storage.update_plot_thread(thread)

        # Update the same thread
        thread.status = "resolved"
        storage.update_plot_thread(thread)

        story_bible = storage.load_story_bible()
        assert len(story_bible.plot_threads) == 1
        assert story_bible.plot_threads[0].status == "resolved"

    def test_update_character_arc(self):
        """Test update_character_arc"""
        storage = NovelStorage("小说F")
        arc = CharacterArc(name="角色1", emotional_state="开心")
        storage.update_character_arc(arc)

        story_bible = storage.load_story_bible()
        assert len(story_bible.character_arcs) == 1
        assert story_bible.character_arcs[0].name == "角色1"

    def test_append_world_state(self):
        """Test append_world_state"""
        storage = NovelStorage("小说G")
        state = WorldState(chapter_index=1, location="地点A", time="时间A")
        storage.append_world_state(state)

        story_bible = storage.load_story_bible()
        assert len(story_bible.world_states) == 1
        assert story_bible.world_states[0].location == "地点A"

    def test_query_story_bible_all(self):
        """Test query_story_bible returns all entries"""
        storage = NovelStorage("小说H")
        story_bible = StoryBibleContent(novel_title="小说H")
        thread = PlotThread(id="t1", name="情节1", status="active", setup_chapter=1)
        story_bible.plot_threads.append(thread)
        storage.save_story_bible(story_bible)

        result = storage.query_story_bible()
        assert len(result["plot_threads"]) == 1

    def test_query_story_bible_by_type(self):
        """Test query_story_bible filters by entry_type"""
        storage = NovelStorage("小说I")
        story_bible = StoryBibleContent(novel_title="小说I")
        thread = PlotThread(id="t1", name="情节1", status="active", setup_chapter=1)
        story_bible.plot_threads.append(thread)
        storage.save_story_bible(story_bible)

        result = storage.query_story_bible(entry_type="plot_thread")
        assert len(result["plot_threads"]) == 1
        assert len(result["character_arcs"]) == 0

    def test_add_consistency_note(self):
        """Test add_consistency_note"""
        storage = NovelStorage("小说K")
        note = ConsistencyNote(
            id="c1",
            issue_type="contradiction",
            description="测试矛盾"
        )
        storage.add_consistency_note(note)

        story_bible = storage.load_story_bible()
        assert len(story_bible.consistency_notes) == 1
        assert story_bible.consistency_notes[0].description == "测试矛盾"
