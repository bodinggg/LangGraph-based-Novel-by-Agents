
from pydantic import BaseModel
from typing import List, Optional

# 定义角色数据模型，继承BaseModel实现数据验证功能
class Character(BaseModel):
    name: str               # 角色的姓名
    background: str         # 角色的背景故事（如出身、经历等）
    personality: str        # 角色的性格特点（如外向、谨慎等）
    goals: List[str]        # 角色的目标列表（如追求正义、寻找真相等）
    conflicts: List[str]    # 角色面临的冲突列表（如内心矛盾、外部对抗等）
    arc: str                # 角色的成长弧线（故事中角色的变化与发展轨迹）

# 定义章节大纲数据模型，用于结构化章节的核心要素
class ChapterOutline(BaseModel):
    title: str              # 章节的标题
    summary: str            # 章节的内容摘要
    key_events: List[str]   # 章节中的关键事件列表
    characters_involved: List[str]  # 章节中涉及的角色名称列表
    setting: str            # 章节发生的场景设定（如地点、时间等）

# 卷册数据模型
class VolumeOutline(BaseModel):
    title: str                      # 卷册标题
    chapters_range: str             # 章节范围（如"1-30"）
    theme: str                      # 卷册主题
    key_turning_points: List[str]   # 卷内关键转折点

# 定义小说大纲数据模型，用于整体规划小说的核心要素
class NovelOutline(BaseModel):
    title: str              # 小说的标题
    genre: str              # 小说的类型（如科幻、悬疑、爱情等）
    theme: str              # 小说的核心主题（如人性、自由、成长等）
    setting: str            # 小说的整体场景设定（如时代背景、世界架构等）
    plot_summary: str       # 小说的情节概要
    master_outline: List[VolumeOutline]  # 总纲（卷册划分）
    chapters: List[Optional[ChapterOutline]]  # 小说包含的所有章节大纲列表
    characters: List[str]  # 小说中所有角色的名称列表


    


# 定义章节内容数据模型，用于结构化章节的具体内容
class ChapterContent(BaseModel):
    title: str              # 章节的标题
    content: str            # 章节的具体文本内容
    notes: str = ""  # 可选的章节注释，用于记录写作思路或后续修改建议（默认值为空字符串）

# 新增：章节质量评估模型，用于量化和描述章节内容的质量
class QualityEvaluation(BaseModel):
    score: int  # 章节质量评分（范围1-10分）
    feedback: str           # 针对章节质量的具体反馈意见
    passes: bool  # 章节质量是否达标（True为达标，False为不达标）
    length_check: bool  # 章节长度是否符合要求（True为符合，False为不符合）
    
