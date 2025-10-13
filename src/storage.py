import json
from pathlib import Path
from typing import Optional, List
from src.model import NovelOutline, Character, ChapterContent

class NovelStorage:
    def __init__(self, novel_title: str):
        self.base_dir = Path(f"result/{novel_title}_storage")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.chapter_dir = self.base_dir / "chapters"
        self.chapter_dir_json = self.base_dir / "chapters_json"
        self.chapter_dir_json.mkdir(exist_ok=True)
        self.chapter_dir.mkdir(exist_ok=True)


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

    def load_chapter(self, chapter_index: int) -> Optional[ChapterContent]:
        chapter_path_json = self.chapter_dir_json / f"{chapter_index:03d}.json"
        try:
            with open(chapter_path_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ChapterContent(**data)

        
        except FileNotFoundError:
            return None

