import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from src.model import NovelOutline, Character, ChapterContent, EntityContent
from src.model import (
    StoryBibleContent, StoryBibleEntry, PlotThread, CharacterArc,
    WorldState, ConsistencyNote
)

logger = logging.getLogger(__name__)


def sanitize_novel_title(novel_title: str) -> str:
    """Sanitize novel title to prevent path traversal attacks.

    Args:
        novel_title: The novel title to sanitize.

    Returns:
        Sanitized title.

    Raises:
        ValueError: If title contains path traversal attempts or invalid characters.
    """
    if not novel_title:
        raise ValueError("Novel title cannot be empty")

    # Strip whitespace
    title = novel_title.strip()

    # Check if empty after stripping
    if not title:
        raise ValueError("Novel title cannot be empty")

    # Check for path traversal attempts
    dangerous_patterns = ["..", "/", "\\", "\0"]
    for pattern in dangerous_patterns:
        if pattern in title:
            raise ValueError(f"Invalid novel title: contains forbidden pattern '{pattern}'")

    # Optionally, limit length to prevent other issues
    if len(title) > 200:
        raise ValueError("Novel title too long (max 200 characters)")

    return title


class NovelStorage:
    def __init__(self, novel_title: str):
        sanitized_title = sanitize_novel_title(novel_title)
        self.base_dir = Path("result").resolve() / f"{sanitized_title}_storage"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.chapter_dir = self.base_dir / "chapters"
        self.chapter_dir_json = self.base_dir / "chapters_json"
        self.chapter_dir_json.mkdir(exist_ok=True)
        self.chapter_dir.mkdir(exist_ok=True)
        self.story_bible_dir = self.base_dir / "story_bible"
        self.story_bible_dir.mkdir(exist_ok=True)
        # 中间结果目录（用于观察修订效果）
        self.chapters_revised_dir = self.base_dir / "chapters_revised"
        self.chapters_revised_dir.mkdir(exist_ok=True)


    # 大纲存储
    def save_outline(self, outline: NovelOutline):
        with open(self.base_dir / "outline.json", "w", encoding="utf-8") as f:
            json.dump(outline.model_dump(), f, ensure_ascii=False, indent=2)

    def load_outline(self) -> Optional[NovelOutline]:
        try:
            with open(self.base_dir / "outline.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            return NovelOutline(**data)
        except FileNotFoundError:
            return None

    # 角色存储
    def save_characters(self, characters: List[Character]):
        with open(self.base_dir / "characters.json", "w", encoding="utf-8") as f:
            json.dump([c.model_dump() for c in characters], f, ensure_ascii=False, indent=2)

    def load_characters(self) -> Optional[List[Character]]:
        try:
            with open(self.base_dir / "characters.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            return [Character(** c) for c in data]
        except FileNotFoundError:
            return None

    # 章节存储
    def save_chapter(self, chapter_index: int, chapter: ChapterContent):
        chapter_path_json = self.chapter_dir_json / f"{chapter_index:03d}.json"
        chapter_path = self.chapter_dir / f"{chapter_index:03d}_{chapter.title.split('.')[-1]}.txt"
        with open(chapter_path, "w", encoding="utf-8") as f:
            f.write(chapter.content)
        with open(chapter_path_json, "w", encoding="utf-8") as f:
            json.dump(chapter.model_dump(), f, ensure_ascii=False, indent=2)

    def save_chapter_revised(self, chapter_index: int, title: str, content: str):
        """保存章节修订版（revision 完成后）

        Args:
            chapter_index: 章节索引
            title: 章节标题
            content: 修订后的内容
        """
        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title)
        chapter_path = self.chapters_revised_dir / f"{chapter_index:03d}_{safe_title}.txt"
        with open(chapter_path, "w", encoding="utf-8") as f:
            f.write(content)

    def load_chapter(self, chapter_index: int) -> Optional[ChapterContent]:
        chapter_path_json = self.chapter_dir_json / f"{chapter_index:03d}.json"
        try:
            with open(chapter_path_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ChapterContent(**data)
        except FileNotFoundError:
            return None

    def load_all_chapters(self) -> List[ChapterContent]:
        chapters = []
        for chapter_path in self.chapter_dir.glob("*.txt"):
            chapter_index = int(chapter_path.stem.split("_")[0])
            chapter_content = self.load_chapter(chapter_index)
            if chapter_content is not None:
                chapters.append(chapter_content)
        return chapters

    # 断点恢复相关方法
    def get_completed_chapter_count(self) -> int:
        """获取已完成的章节数量（用于断点恢复）"""
        chapters = list(self.chapter_dir.glob("*.txt"))
        return len(chapters)

    def get_novel_title(self) -> str:
        """从存储目录名称提取小说标题

        Returns:
            小说标题（不含 _storage 后缀）
        """
        return self.base_dir.name.replace("_storage", "")

    def has_outline(self) -> bool:
        """检查是否存在已保存的大纲"""
        return (self.base_dir / "outline.json").exists()

    def has_characters(self) -> bool:
        """检查是否存在已保存的角色档案"""
        return (self.base_dir / "characters.json").exists()

    def save_outline_metadata(self, current_volume_index: int, validated_chapters_count: int = 0):
        """保存大纲元数据（用于断点恢复）

        Args:
            current_volume_index: 当前已完成的卷索引
            validated_chapters_count: 已验证的章节数量
        """
        meta = {
            "current_volume_index": current_volume_index,
            "validated_chapters_count": validated_chapters_count,
        }
        with open(self.base_dir / "outline_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def load_outline_metadata(self) -> dict:
        """加载大纲元数据

        Returns:
            包含 current_volume_index 和 validated_chapters_count 的字典
        """
        try:
            with open(self.base_dir / "outline_meta.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"current_volume_index": 0, "validated_chapters_count": 0}

    def get_storage_info(self) -> dict:
        """获取存储目录信息（用于断点恢复列表）

        Returns:
            包含小说标题、章节数、是否存在大纲和角色等信息
        """
        return {
            "title": self.get_novel_title(),
            "chapter_count": self.get_completed_chapter_count(),
            "has_outline": self.has_outline(),
            "has_characters": self.has_characters(),
        }

    # ============== StoryBible Methods ==============

    def save_story_bible(self, story_bible: StoryBibleContent):
        """保存StoryBible到storage

        Args:
            story_bible: StoryBibleContent对象
        """
        story_bible.last_updated = datetime.now()
        with open(self.story_bible_dir / "story_bible.json", "w", encoding="utf-8") as f:
            json.dump(story_bible.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

    def load_story_bible(self) -> Optional[StoryBibleContent]:
        """加载StoryBible

        Returns:
            StoryBibleContent对象，如果不存在则返回None
        """
        try:
            with open(self.story_bible_dir / "story_bible.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            return StoryBibleContent(**data)
        except FileNotFoundError:
            return None

    def has_story_bible(self) -> bool:
        """检查是否存在StoryBible"""
        return (self.story_bible_dir / "story_bible.json").exists()

    def append_story_bible_entry(self, entry: StoryBibleEntry):
        """动态追加StoryBible条目

        Args:
            entry: StoryBibleEntry对象
        """
        story_bible = self.load_story_bible()
        if story_bible is None:
            # 创建新的StoryBible
            story_bible = StoryBibleContent(novel_title=self.get_novel_title())

        # 根据类型追加到对应列表
        entry.updated_at = datetime.now()

        if entry.entry_type == "plot_thread":
            story_bible.plot_threads.append(entry.data)
        elif entry.entry_type == "character_arc":
            # 检查是否已存在该角色，存在则更新
            existing = story_bible.get_character_arc(entry.data.name)
            if existing:
                # 更新现有角色弧线
                idx = story_bible.character_arcs.index(existing)
                story_bible.character_arcs[idx] = entry.data
            else:
                story_bible.character_arcs.append(entry.data)
        elif entry.entry_type == "world_state":
            story_bible.world_states.append(entry.data)
        elif entry.entry_type == "entity":
            story_bible.entities.append(entry.data)

        self.save_story_bible(story_bible)

    def update_plot_thread(self, thread: PlotThread):
        """更新情节线

        Args:
            thread: PlotThread对象
        """
        story_bible = self.load_story_bible()
        if story_bible is None:
            story_bible = StoryBibleContent(novel_title=self.get_novel_title())

        # 检查是否已存在
        existing = None
        for t in story_bible.plot_threads:
            if t.id == thread.id:
                existing = t
                break

        if existing:
            # 更新现有
            idx = story_bible.plot_threads.index(existing)
            story_bible.plot_threads[idx] = thread
        else:
            # 添加新的
            story_bible.plot_threads.append(thread)

        self.save_story_bible(story_bible)

    def update_character_arc(self, arc: CharacterArc):
        """更新角色弧线

        Args:
            arc: CharacterArc对象
        """
        story_bible = self.load_story_bible()
        if story_bible is None:
            story_bible = StoryBibleContent(novel_title=self.get_novel_title())

        existing = story_bible.get_character_arc(arc.name)
        if existing:
            idx = story_bible.character_arcs.index(existing)
            story_bible.character_arcs[idx] = arc
        else:
            story_bible.character_arcs.append(arc)

        self.save_story_bible(story_bible)

    def append_world_state(self, state: WorldState):
        """追加世界状态

        Args:
            state: WorldState对象
        """
        story_bible = self.load_story_bible()
        if story_bible is None:
            story_bible = StoryBibleContent(novel_title=self.get_novel_title())

        story_bible.world_states.append(state)
        self.save_story_bible(story_bible)

    def query_story_bible(
        self,
        entry_type: Optional[str] = None,
        chapter_range: Optional[Tuple[int, int]] = None
    ) -> Dict[str, List]:
        """查询指定范围/类型的条目

        Args:
            entry_type: 条目类型 ("entity" | "plot_thread" | "character_arc" | "world_state")
            chapter_range: 章节范围 (start, end)

        Returns:
            包含查询结果的字典
        """
        story_bible = self.load_story_bible()
        if story_bible is None:
            return {
                "entities": [],
                "plot_threads": [],
                "character_arcs": [],
                "world_states": []
            }

        result = {
            "entities": [],
            "plot_threads": [],
            "character_arcs": [],
            "world_states": []
        }

        if entry_type is None or entry_type == "entity":
            result["entities"] = story_bible.entities

        if entry_type is None or entry_type == "plot_thread":
            result["plot_threads"] = story_bible.plot_threads

        if entry_type is None or entry_type == "character_arc":
            result["character_arcs"] = story_bible.character_arcs

        if entry_type is None or entry_type == "world_state":
            result["world_states"] = story_bible.world_states

        return result

    def add_consistency_note(self, note: ConsistencyNote):
        """添加一致性备注

        Args:
            note: ConsistencyNote对象
        """
        story_bible = self.load_story_bible()
        if story_bible is None:
            story_bible = StoryBibleContent(novel_title=self.get_novel_title())

        story_bible.consistency_notes.append(note)
        self.save_story_bible(story_bible)
