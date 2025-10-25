from datetime import datetime
from typing import List
import gradio as gr

from src.workflow import create_workflow
from src.model import NovelOutline, Character
from src.config_loader import ModelConfig, BaseConfig
from src.log_config import loggers
# 初始化日志记录器
logger = loggers['gradio']

import os
from dotenv import load_dotenv
load_dotenv(override=True)
api_key = os.getenv("API_KEY")
base_url = os.getenv("BASE_URL")


class NovelGeneratorUI:
    """小说自动生成系统的Gradio界面控制器"""
    
    def __init__(self):
        """初始化UI控制器的状态变量"""
        self.workflow = None  # 后端工作流实例
        self.current_state = None  # 当前生成状态
        self.processing = False  # 生成过程状态标记
        self.all_chapters = []  # 存储所有章节内容 
        self.validated_outline = None  # 已验证的小说大纲
        self.validated_characters = None  # 已验证的角色列表
        self.final_result = None  # 最终生成结果
        # 从环境变量加载默认API配置
        self.default_api_key = api_key
        self.default_base_url = base_url 
        self.last_chapter_index = -1  # 上一次选择的章节索引
        # 交互式工作流控制变量
        self.workflow_iterator = None  # 工作流迭代器
        self.step_approved = None  # 步骤批准状态标志

    def __update_status(self, message):
        """更新状态信息并记录日志"""
        logger.info(message)
        return message

    def _format_outline(self, outline: NovelOutline, master_outline=True):
        """将小说大纲对象格式化为Markdown字符串"""
        if not outline:
            return "尚未生成大纲"
        if master_outline:
            outline_str = f"## 📚 小说总纲（卷册划分）\n"
            for i, vol in enumerate(outline.master_outline, 1):
                outline_str += f"**卷{i}《{vol.title}》**（第{vol.chapters_range}章）\n"
                outline_str += f"  主题: {vol.theme}\n"
                outline_str += f"  关键转折: {', '.join(vol.key_turning_points[:2])}...\n\n"
        else:
            outline_str = ""
        outline_str += f"## 📖 小说大纲\n"
        outline_str += f"**标题**: {outline.title}\n\n"
        outline_str += f"**类型**: {outline.genre}\n\n"
        outline_str += f"**主题**: {outline.theme}\n\n"
        outline_str += f"**背景**: {outline.setting}\n\n"
        outline_str += f"**情节概要**: {outline.plot_summary}\n\n"
        outline_str += f"**主要角色**: {', '.join(outline.characters)}\n\n"
        outline_str += "### 📑 章节列表:\n"
        
        for i, chapter in enumerate(outline.chapters, 1):
            outline_str += f"**第{i}章**: {chapter.title.split('.')[-1]}\n\n"
            outline_str += f"  摘要: {chapter.summary}\n\n"
            outline_str += f"  关键事件: {', '.join(chapter.key_events)}\n\n"
            outline_str += f"  涉及角色: {', '.join(chapter.characters_involved)}\n\n"
            
        return outline_str

    def _format_characters(self, characters: List[Character]):
        """将角色列表格式化为Markdown字符串"""
        if not characters:
            return "尚未生成角色档案"
        
        chars_str = "## 👥 角色档案\n"
        for i, char in enumerate(characters, 1):
            chars_str += f"### {char.name}\n"
            chars_str += f"**背景**: {char.background}\n\n"
            chars_str += f"**性格**: {char.personality}\n\n"
            chars_str += f"**目标**: {', '.join(char.goals)}\n\n"
            chars_str += f"**冲突**: {', '.join(char.conflicts)}\n\n"
            chars_str += f"**成长弧线**: {char.arc}\n\n"
            chars_str += "---\n\n"
            
        return chars_str

    def _format_chapter(self, chapter, index):
        """将章节内容格式化为Markdown字符串"""
        if not chapter:
            return "尚未生成章节内容"
        
        return f"## 📄 第{index+1}章：{chapter.title}\n\n{chapter.content}"

    def _format_evaluation(self, evaluation):
        """将评估结果格式化为Markdown字符串"""
        if not evaluation:
            return "尚未生成评估内容"
        
        score_color = "green" if evaluation.score >= 7 else "orange" if evaluation.score >= 4 else "red"
        length_check = "✅ 达标" if evaluation.length_check else "❌ 不达标"
        
        eval_str = "## 📊 章节质量评估\n"
        eval_str += f"**评分**: <span style='color:{score_color}; font-size:1.2em'>{evaluation.score}/10</span>\n\n"
        eval_str += f"**长度检查**: {length_check}\n\n"
        eval_str += f"**通过状态**: {'✅ 已通过' if evaluation.passes else '❌ 未通过'}\n\n"
        eval_str += "### 反馈建议\n"
        eval_str += evaluation.overall_feedback
        
        
        return eval_str

    def _update_chapter_selection(self, chapters):
        """更新章节选择下拉框的选项"""
        if not chapters:
            return gr.Dropdown(choices=[], interactive=False)
        
        choices = [f"第{i+1}章：{chapters[i].title}" for i in range(len(chapters))]
        return gr.Dropdown(choices=choices, value=choices[-1] if choices else None, interactive=True)

    def _show_selected_chapter(self, selection):
        """显示选中的章节内容"""
        if not selection or not self.all_chapters:
            return "请先生成章节内容"
        
        index = int(selection.split("第")[1].split("章")[0]) - 1
        if 0 <= index < len(self.all_chapters):
            return self._format_chapter(self.all_chapters[index], index)
        return "章节内容不存在"

    def _toggle_model_settings(self, model_type):
        """根据模型类型切换显示对应的设置项"""
        if model_type == "api":
            return (
                gr.update(visible=True),  # api设置面板
                gr.update(visible=False)  # 本地模型设置面板
            )
        else:
            return (
                gr.update(visible=False),  # api设置面板
                gr.update(visible=True)   # 本地模型设置面板
            )
        
    def _save_outline(self, edited_outline_text, status_box):
        """保存编辑后的小说大纲到storage目录"""
        if not self.validated_outline:
            error_msg = "❌ 保存失败：请先生成小说大纲"
            return error_msg, self.__update_status(error_msg), gr.update()
        
        try:
            # 使用NovelStorage保存大纲
            from src.storage import NovelStorage
            
            # 如果用户编辑了大纲文本，需要解析并更新
            if edited_outline_text and edited_outline_text.strip():
                updated_outline = self._parse_edited_outline(edited_outline_text)
                if updated_outline:
                    self.validated_outline = updated_outline
            
            # 创建存储实例（使用更新后的标题）
            storage = NovelStorage(self.validated_outline.title)
            
            # 保存大纲到storage目录
            storage.save_outline(self.validated_outline)
            
            # 格式化更新后的大纲用于前端显示
            updated_outline_display = self._format_outline(self.validated_outline, master_outline=True)
            
            success_msg = f"✅ 大纲保存成功！保存路径：{storage.base_dir / 'outline.json'}"
            logger.info(success_msg)
            return success_msg, self.__update_status(success_msg), updated_outline_display
            
        except Exception as e:
            error_msg = f"❌ 保存大纲失败：{str(e)}"
            logger.error(error_msg)
            return error_msg, self.__update_status(error_msg), gr.update()

    def _approve_current_step(self):
        """批准当前步骤，继续执行工作流"""
        if not hasattr(self, 'workflow_iterator') or self.workflow_iterator is None:
            return "❌ 没有正在执行的工作流", gr.update(visible=False), gr.update(visible=False)
        
        try:
            # 设置批准标志
            self.step_approved = True
            return "✅ 已批准当前步骤，继续执行...", gr.update(visible=False), gr.update(visible=False)
        except Exception as e:
            error_msg = f"❌ 批准步骤失败：{str(e)}"
            logger.error(error_msg)
            return error_msg, gr.update(visible=False), gr.update(visible=False)

    def _reject_current_step(self):
        """拒绝当前步骤，停止工作流"""
        if not hasattr(self, 'workflow_iterator') or self.workflow_iterator is None:
            return "❌ 没有正在执行的工作流", gr.update(visible=False), gr.update(visible=False)
        
        try:
            # 设置拒绝标志
            self.step_approved = False
            self.processing = False
            self.workflow_iterator = None
            return "❌ 已拒绝当前步骤，工作流已停止", gr.update(visible=False), gr.update(visible=False)
        except Exception as e:
            error_msg = f"❌ 拒绝步骤失败：{str(e)}"
            logger.error(error_msg)
            return error_msg, gr.update(visible=False), gr.update(visible=False)

    def _parse_edited_outline(self, edited_text):
        """解析用户编辑的大纲文本，转换为NovelOutline对象"""
        try:
            # 创建一个新的大纲对象，基于原始大纲
            updated_outline = self.validated_outline.model_copy()
            
            lines = edited_text.strip().split('\n')
            current_chapter = None
            chapter_index = -1
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 解析基本信息
                if line.startswith('标题:'):
                    updated_outline.title = line.split(':', 1)[1].strip()
                elif line.startswith('类型:'):
                    updated_outline.genre = line.split(':', 1)[1].strip()
                elif line.startswith('主题:'):
                    updated_outline.theme = line.split(':', 1)[1].strip()
                elif line.startswith('背景:'):
                    updated_outline.setting = line.split(':', 1)[1].strip()
                elif line.startswith('情节概要:'):
                    updated_outline.plot_summary = line.split(':', 1)[1].strip()
                elif line.startswith('主要角色:'):
                    characters_str = line.split(':', 1)[1].strip()
                    updated_outline.characters = [c.strip() for c in characters_str.split(',') if c.strip()]
                
                # 解析章节信息
                elif line.startswith('第') and '章:' in line:
                    # 保存上一章节
                    if current_chapter and chapter_index >= 0:
                        if chapter_index < len(updated_outline.chapters):
                            updated_outline.chapters[chapter_index] = current_chapter
                    
                    # 开始新章节
                    chapter_title = line.split(':', 1)[1].strip()
                    chapter_index += 1
                    
                    # 获取原始章节作为模板，或创建新章节
                    if chapter_index < len(updated_outline.chapters) and updated_outline.chapters[chapter_index]:
                        current_chapter = updated_outline.chapters[chapter_index].model_copy()
                        current_chapter.title = chapter_title
                    else:
                        # 创建新章节（使用默认值）
                        from src.model import ChapterOutline
                        current_chapter = ChapterOutline(
                            title=chapter_title,
                            summary="",
                            key_events=[],
                            characters_involved=[],
                            setting=""
                        )
                
                elif current_chapter:
                    # 解析章节详细信息
                    if line.startswith('摘要:'):
                        current_chapter.summary = line.split(':', 1)[1].strip()
                    elif line.startswith('关键事件:'):
                        events_str = line.split(':', 1)[1].strip()
                        current_chapter.key_events = [e.strip() for e in events_str.split(',') if e.strip()]
                    elif line.startswith('涉及角色:'):
                        chars_str = line.split(':', 1)[1].strip()
                        current_chapter.characters_involved = [c.strip() for c in chars_str.split(',') if c.strip()]
                    elif line.startswith('场景:'):
                        current_chapter.setting = line.split(':', 1)[1].strip()
            
            # 保存最后一个章节
            if current_chapter and chapter_index >= 0:
                if chapter_index < len(updated_outline.chapters):
                    updated_outline.chapters[chapter_index] = current_chapter
                else:
                    updated_outline.chapters.append(current_chapter)
            
            return updated_outline
            
        except Exception as e:
            logger.error(f"解析编辑大纲失败: {e}")
            # 如果解析失败，返回原始大纲
            return self.validated_outline

    def _toggle_outline_edit(self):
        """切换大纲编辑模式"""
        if not self.validated_outline:
            return (
                gr.update(visible=False),  # outline_edit_box
                gr.update(visible=True),   # edit_outline_btn
                gr.update(visible=False),  # save_outline_btn
                gr.update(visible=False),  # cancel_edit_btn
                "❌ 请先生成大纲"
            )
        
        # 将当前大纲转换为可编辑的文本格式
        outline_text = self._outline_to_editable_text(self.validated_outline)
        
        return (
            gr.update(visible=True, value=outline_text),  # outline_edit_box
            gr.update(visible=False),  # edit_outline_btn
            gr.update(visible=True),   # save_outline_btn
            gr.update(visible=True),   # cancel_edit_btn
            "📝 进入编辑模式，可以修改大纲内容"
        )

    def _cancel_outline_edit(self):
        """取消大纲编辑"""
        return (
            gr.update(visible=False, value=""),  # outline_edit_box
            gr.update(visible=True),   # edit_outline_btn
            gr.update(visible=False),  # save_outline_btn
            gr.update(visible=False),  # cancel_edit_btn
            "❌ 已取消编辑"
        )

    def _outline_to_editable_text(self, outline: NovelOutline):
        """将NovelOutline对象转换为可编辑的文本格式"""
        text = f"标题: {outline.title}\n"
        text += f"类型: {outline.genre}\n"
        text += f"主题: {outline.theme}\n"
        text += f"背景: {outline.setting}\n"
        text += f"情节概要: {outline.plot_summary}\n"
        text += f"主要角色: {', '.join(outline.characters)}\n\n"
        
        text += "章节列表:\n"
        for i, chapter in enumerate(outline.chapters, 1):
            if chapter:  # 检查章节是否存在
                text += f"第{i}章: {chapter.title}\n"
                text += f"  摘要: {chapter.summary}\n"
                text += f"  关键事件: {', '.join(chapter.key_events)}\n"
                text += f"  涉及角色: {', '.join(chapter.characters_involved)}\n"
                text += f"  场景: {chapter.setting}\n\n"
        
        return text

    def _characters_to_editable_text(self, characters: List[Character]):
        """将角色列表转换为可编辑的文本格式"""
        if not characters:
            return ""
        
        text = ""
        for i, char in enumerate(characters, 1):
            text += f"角色{i}: {char.name}\n"
            text += f"  背景: {char.background}\n"
            text += f"  性格: {char.personality}\n"
            text += f"  目标: {', '.join(char.goals)}\n"
            text += f"  冲突: {', '.join(char.conflicts)}\n"
            text += f"  成长弧线: {char.arc}\n\n"
        
        return text

    def _toggle_characters_edit(self):
        """切换角色编辑模式"""
        if not self.validated_characters:
            return (
                gr.update(visible=False),  # characters_edit_box
                gr.update(visible=True),   # edit_characters_btn
                gr.update(visible=False),  # save_characters_btn
                gr.update(visible=False),  # cancel_characters_edit_btn
                "❌ 请先生成角色档案"
            )
        
        # 将当前角色档案转换为可编辑的文本格式
        characters_text = self._characters_to_editable_text(self.validated_characters)
        
        return (
            gr.update(visible=True, value=characters_text),  # characters_edit_box
            gr.update(visible=False),  # edit_characters_btn
            gr.update(visible=True),   # save_characters_btn
            gr.update(visible=True),   # cancel_characters_edit_btn
            "📝 进入编辑模式，可以修改角色档案"
        )

    def _cancel_characters_edit(self):
        """取消角色编辑"""
        return (
            gr.update(visible=False, value=""),  # characters_edit_box
            gr.update(visible=True),   # edit_characters_btn
            gr.update(visible=False),  # save_characters_btn
            gr.update(visible=False),  # cancel_characters_edit_btn
            "❌ 已取消编辑"
        )

    def _save_characters(self, edited_characters_text, status_box):
        """保存编辑后的角色档案到storage目录"""
        if not self.validated_characters:
            error_msg = "❌ 保存失败：请先生成角色档案"
            return error_msg, self.__update_status(error_msg), gr.update()
        
        try:
            # 使用NovelStorage保存角色档案
            from src.storage import NovelStorage
            
            # 如果用户编辑了角色文本，需要解析并更新
            if edited_characters_text and edited_characters_text.strip():
                updated_characters = self._parse_edited_characters(edited_characters_text)
                if updated_characters:
                    self.validated_characters = updated_characters
            
            # 创建存储实例（使用当前大纲的标题）
            if self.validated_outline:
                storage = NovelStorage(self.validated_outline.title)
            else:
                # 如果没有大纲，使用默认标题
                storage = NovelStorage("untitled_novel")
            
            # 保存角色档案到storage目录
            storage.save_characters(self.validated_characters)
            
            # 格式化更新后的角色档案用于前端显示
            updated_characters_display = self._format_characters(self.validated_characters)
            
            success_msg = f"✅ 角色档案保存成功！保存路径：{storage.base_dir / 'characters.json'}"
            logger.info(success_msg)
            return success_msg, self.__update_status(success_msg), updated_characters_display
            
        except Exception as e:
            error_msg = f"❌ 保存角色档案失败：{str(e)}"
            logger.error(error_msg)
            return error_msg, self.__update_status(error_msg), gr.update()

    def _parse_edited_characters(self, edited_text):
        """解析用户编辑的角色文本，转换为Character对象列表"""
        try:
            # 创建一个新的角色列表，基于原始角色
            updated_characters = []
            
            lines = edited_text.strip().split('\n')
            current_character = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 解析角色信息
                if line.startswith('角色') and ':' in line:
                    # 保存上一角色
                    if current_character:
                        updated_characters.append(current_character)
                    
                    # 开始新角色
                    character_name = line.split(':', 1)[1].strip()
                    
                    # 查找原始角色作为模板，或创建新角色
                    original_char = None
                    for char in self.validated_characters:
                        if char.name == character_name:
                            original_char = char
                            break
                    
                    if original_char:
                        current_character = original_char.model_copy()
                    else:
                        # 创建新角色（使用默认值）
                        from src.model import Character
                        current_character = Character(
                            name=character_name,
                            background="",
                            personality="",
                            goals=[],
                            conflicts=[],
                            arc=""
                        )
                
                elif current_character:
                    # 解析角色详细信息
                    if line.startswith('背景:'):
                        current_character.background = line.split(':', 1)[1].strip()
                    elif line.startswith('性格:'):
                        current_character.personality = line.split(':', 1)[1].strip()
                    elif line.startswith('目标:'):
                        goals_str = line.split(':', 1)[1].strip()
                        current_character.goals = [g.strip() for g in goals_str.split(',') if g.strip()]
                    elif line.startswith('冲突:'):
                        conflicts_str = line.split(':', 1)[1].strip()
                        current_character.conflicts = [c.strip() for c in conflicts_str.split(',') if c.strip()]
                    elif line.startswith('成长弧线:'):
                        current_character.arc = line.split(':', 1)[1].strip()
            
            # 保存最后一个角色
            if current_character:
                updated_characters.append(current_character)
            
            return updated_characters
            
        except Exception as e:
            logger.error(f"解析编辑角色档案失败: {e}")
            # 如果解析失败，返回原始角色档案
            return self.validated_characters

    def _toggle_chapter_edit(self, chapter_selector_value):
        """切换章节编辑模式"""
        if not self.all_chapters or not chapter_selector_value:
            return (
                gr.update(visible=False),  # chapter_edit_box
                gr.update(visible=True),   # edit_chapter_btn
                gr.update(visible=False),  # save_chapter_btn
                gr.update(visible=False),  # cancel_chapter_edit_btn
                "❌ 请先生成章节内容并选择章节"
            )
        
        # 获取当前选中的章节
        selection = chapter_selector_value
        index = int(selection.split("第")[1].split("章")[0]) - 1
        if 0 <= index < len(self.all_chapters):
            current_chapter = self.all_chapters[index]
            # 将当前章节转换为可编辑的文本格式
            chapter_text = self._chapter_to_editable_text(current_chapter, index)
            
            return (
                gr.update(visible=True, value=chapter_text),  # chapter_edit_box
                gr.update(visible=False),  # edit_chapter_btn
                gr.update(visible=True),   # save_chapter_btn
                gr.update(visible=True),   # cancel_chapter_edit_btn
                f"📝 进入编辑模式，可以修改第{index+1}章内容"
            )
        else:
            return (
                gr.update(visible=False),  # chapter_edit_box
                gr.update(visible=True),   # edit_chapter_btn
                gr.update(visible=False),  # save_chapter_btn
                gr.update(visible=False),  # cancel_chapter_edit_btn
                "❌ 章节不存在"
            )

    def _cancel_chapter_edit(self):
        """取消章节编辑"""
        return (
            gr.update(visible=False, value=""),  # chapter_edit_box
            gr.update(visible=True),   # edit_chapter_btn
            gr.update(visible=False),  # save_chapter_btn
            gr.update(visible=False),  # cancel_chapter_edit_btn
            "❌ 已取消编辑"
        )

    def _chapter_to_editable_text(self, chapter, index):
        """将章节对象转换为可编辑的文本格式"""
        text = f"第{index+1}章: {chapter.title}\n\n"
        text += f"内容:\n{chapter.content}"
        return text

    def _save_chapter(self, edited_chapter_text, status_box, chapter_selector_value):
        """保存编辑后的章节内容到storage目录"""
        if not self.all_chapters or not chapter_selector_value:
            error_msg = "❌ 保存失败：请先生成章节内容并选择章节"
            return error_msg, self.__update_status(error_msg), gr.update()
        
        try:
            # 获取当前选中的章节
            selection = chapter_selector_value
            index = int(selection.split("第")[1].split("章")[0]) - 1
            if index < 0 or index >= len(self.all_chapters):
                error_msg = "❌ 保存失败：章节不存在"
                return error_msg, self.__update_status(error_msg), gr.update()
            
            # 使用NovelStorage保存章节内容
            from src.storage import NovelStorage
            
            # 如果用户编辑了章节文本，需要解析并更新
            if edited_chapter_text and edited_chapter_text.strip():
                updated_chapter = self._parse_edited_chapter(edited_chapter_text, index)
                if updated_chapter:
                    self.all_chapters[index] = updated_chapter
            
            # 创建存储实例（使用当前大纲的标题）
            if self.validated_outline:
                storage = NovelStorage(self.validated_outline.title)
            else:
                # 如果没有大纲，使用默认标题
                storage = NovelStorage("untitled_novel")
            
            # 保存章节内容到storage目录
            storage.save_chapter(self.all_chapters)
            
            # 格式化更新后的章节内容用于前端显示
            updated_chapter_display = self._format_chapter(self.all_chapters[index], index)
            
            success_msg = f"✅ 章节内容保存成功！保存路径：{storage.base_dir / 'chapters.json'}"
            logger.info(success_msg)
            return success_msg, self.__update_status(success_msg), updated_chapter_display
            
        except Exception as e:
            error_msg = f"❌ 保存章节内容失败：{str(e)}"
            logger.error(error_msg)
            return error_msg, self.__update_status(error_msg), gr.update()

    def _parse_edited_chapter(self, edited_text, index):
        """解析用户编辑的章节文本，转换为Chapter对象"""
        try:
            # 创建一个新的章节对象，基于原始章节
            original_chapter = self.all_chapters[index]
            updated_chapter = original_chapter.model_copy()
            
            lines = edited_text.strip().split('\n')
            in_content_section = False
            content_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 解析章节标题
                if line.startswith('第') and '章:' in line:
                    chapter_title = line.split(':', 1)[1].strip()
                    updated_chapter.title = chapter_title
                
                # 解析内容部分
                elif line == '内容:':
                    in_content_section = True
                    continue
                elif in_content_section:
                    content_lines.append(line)
            
            # 合并内容行
            if content_lines:
                updated_chapter.content = '\n'.join(content_lines)
            
            return updated_chapter
            
        except Exception as e:
            logger.error(f"解析编辑章节内容失败: {e}")
            # 如果解析失败，返回原始章节
            return self.all_chapters[index]
    
    def _generate_novel_interactive(self, user_intent, model_type, api_key, base_url, model_name, model_path, min_chapters, volume, master_outline,
                      status_box, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, approve_btn, reject_btn):
        """交互式生成小说的主流程（分步执行，需要用户批准）"""
        if self.processing:
            return status_box, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, gr.update(visible=False), gr.update(visible=False)
        
        self.processing = True
        self.all_chapters = []
        self.validated_outline = None
        self.validated_characters = None
        self.final_result = None
        self.step_approved = None
        self.workflow_iterator = None
        
        # 关键步骤列表，需要用户批准，逻辑同 _feedback_node
        critical_steps = ["character_feedback", "outline_feedback", "chapter_feedback"]
        try:
            status = self.__update_status("🔄 初始化工作流...")
            yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, gr.update(visible=False), gr.update(visible=False)
            
            # 根据模型类型创建配置
            if model_type == "api":
                if not api_key:
                    raise ValueError("API密钥不能为空，请输入有效的API_KEY")
                if not model_name:
                    raise ValueError("请输入模型名称")
                
                model_config = ModelConfig(
                    model_type="api",
                    api_key=api_key,
                    api_url=base_url,
                    model_name=model_name
                )
                status = self.__update_status(f"✅ 已配置API模型: {model_name}")
            else:
                if not model_path:
                    raise ValueError("本地模型路径不能为空，请输入有效的模型路径")
                
                model_config = ModelConfig(
                    model_type="local",
                    model_path=model_path
                )
                status = self.__update_status(f"✅ 已加载本地模型: {os.path.basename(model_path)}")
            
            yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, gr.update(visible=False), gr.update(visible=False)
            
            agent_config = BaseConfig(min_chapters=min_chapters, volume=volume, master_outline=master_outline)
            
            self.workflow = create_workflow(model_config, agent_config)
            status = self.__update_status("✅ 工作流初始化完成，开始交互式生成...")
            yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, gr.update(visible=False), gr.update(visible=False)
            
            # 创建工作流迭代器
            self.workflow_iterator = self.workflow.stream(
                {"user_intent": user_intent, "gradio_mode": True},  # 设置为True以启用交互模式
                {"recursion_limit": 1000000}
            )
            
            final_state = None
            for step in self.workflow_iterator:
                for node, state_dict in step.items():
                    self.current_state = state_dict
                    final_state = state_dict
                    status = self.__update_status(f"🔍 执行节点: {node}")

                    # 更新界面显示
                    if state_dict.get('validated_outline'):
                        self.validated_outline = state_dict['validated_outline']
                        outline_box = self._format_outline(self.validated_outline, master_outline)
                    
                    if state_dict.get('validated_characters'):
                        self.validated_characters = state_dict['validated_characters']
                        characters_box = self._format_characters(self.validated_characters)
                    
                    if state_dict.get('validated_chapter_draft'):
                        current_index = state_dict.get('current_chapter_index', 0)
                        chapter_box = self._format_chapter(
                            state_dict['validated_chapter_draft'], 
                            current_index
                        )
                        if self.last_chapter_index == current_index:
                            self.all_chapters[-1] = state_dict['validated_chapter_draft']
                        elif len(self.all_chapters) <= current_index:
                            self.all_chapters.append(state_dict['validated_chapter_draft'])
                            chapter_selector = self._update_chapter_selection(self.all_chapters)
                        self.last_chapter_index = current_index
                        
                    if state_dict.get('validated_evaluation'):
                        evaluation_box = self._format_evaluation(state_dict['validated_evaluation'])
                    
                    # 检查是否是关键步骤，需要用户批准
                    if node in critical_steps:
                        status = self.__update_status(f"⏸️ 等待用户批准步骤: {node}")
                        yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, gr.update(visible=True), gr.update(visible=True)
                        
                        # 等待用户批准
                        self.step_approved = None
                        while self.step_approved is None and self.processing:
                            import time
                            time.sleep(0.1)  # 短暂等待
                            yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, gr.update(visible=True), gr.update(visible=True)
                        
                        # 检查用户决定
                        if not self.step_approved:
                            status = self.__update_status("❌ 用户拒绝了当前步骤，工作流已停止")
                            yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, gr.update(visible=False), gr.update(visible=False)
                            return
                        
                        status = self.__update_status(f"✅ 用户批准了步骤: {node}，继续执行...")
                        outline_box = self._format_outline(self.validated_outline, master_outline)
                        yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, gr.update(visible=False), gr.update(visible=False)
                    else:
                        yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, gr.update(visible=False), gr.update(visible=False)
            
            self.final_result = final_state.get('result', '') if final_state else ''
            if self.final_result == "生成失败":
                error_msg = final_state.get('final_error', '未知错误') if final_state else '未知错误'
                status = self.__update_status(f"❌ 小说生成失败：{error_msg}")
                yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, gr.update(visible=False), gr.update(visible=False)
            else:
                status = self.__update_status("🎉 小说生成完成！可以点击保存按钮保存内容")
                yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, gr.update(visible=False), gr.update(visible=False)
                
        except Exception as e:
            error_msg = f"❌ 小说生成失败：{str(e)}"
            logger.error(error_msg)
            yield error_msg, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, gr.update(visible=False), gr.update(visible=False)
        finally:
            self.processing = False
            self.workflow_iterator = None

    def _generate_novel(self, user_intent, model_type, api_key, base_url, model_name, model_path, min_chapters, volume, master_outline,
                      status_box, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector):
        """生成小说的主流程（生成器函数）- 保持原有的自动执行模式"""
        if self.processing:
            return status_box, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector
        
        self.processing = True
        self.all_chapters = []
        self.validated_outline = None
        self.validated_characters = None
        self.final_result = None
        
        try:
            status = self.__update_status("🔄 初始化工作流...")
            yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector
            
            # 根据模型类型创建配置
            if model_type == "api":
                if not api_key:
                    raise ValueError("API密钥不能为空，请输入有效的API_KEY")
                if not model_name:
                    raise ValueError("请输入模型名称")
                
                model_config = ModelConfig(
                    model_type="api",
                    api_key=api_key,
                    api_url=base_url,
                    model_name=model_name
                )
                status = self.__update_status(f"✅ 已配置API模型: {model_name}")
            else:
                if not model_path:
                    raise ValueError("本地模型路径不能为空，请输入有效的模型路径")
                
                model_config = ModelConfig(
                    model_type="local",
                    model_path=model_path
                )
                status = self.__update_status(f"✅ 已加载本地模型: {os.path.basename(model_path)}")
            
            yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector
            
            agent_config = BaseConfig(min_chapters=min_chapters, volume=volume, master_outline=master_outline)
            
            self.workflow = create_workflow(model_config, agent_config)
            status = self.__update_status("✅ 工作流初始化完成，开始生成小说...")
            yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector
            
            final_state = None
            for step in self.workflow.stream(
                {"user_intent": user_intent, "gradio_mode":True},
                {"recursion_limit": 1000000}
            ):
                for node, state_dict in step.items():
                    self.current_state = state_dict
                    final_state = state_dict
                    status = self.__update_status(f"🔍 执行节点: {node}")

                    if state_dict.get('validated_outline'):
                        self.validated_outline = state_dict['validated_outline']
                        outline_box = self._format_outline(self.validated_outline, master_outline)
                    
                    if state_dict.get('validated_characters'):
                        self.validated_characters = state_dict['validated_characters']
                        characters_box = self._format_characters(self.validated_characters)
                    
                    if state_dict.get('validated_chapter_draft'):
                        current_index = state_dict.get('current_chapter_index', 0)
                        chapter_box = self._format_chapter(
                            state_dict['validated_chapter_draft'], 
                            current_index
                        )
                        if self.last_chapter_index == current_index:
                            self.all_chapters[-1] = state_dict['validated_chapter_draft']
                        
                        elif len(self.all_chapters) <= current_index:
                            self.all_chapters.append(state_dict['validated_chapter_draft'])
                            chapter_selector = self._update_chapter_selection(self.all_chapters)
                        self.last_chapter_index = current_index
                    if state_dict.get('validated_evaluation'):
                        evaluation_box = self._format_evaluation(state_dict['validated_evaluation'])
                    
                    yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector
            
            self.final_result = final_state.get('result', '') if final_state else ''
            if self.final_result == "生成失败":
                error_msg = final_state.get('final_error', '未知错误') if final_state else '未知错误'
                status = self.__update_status(f"❌ 小说生成失败：{error_msg}")
                yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector
            else:
                status = self.__update_status("🎉 小说生成完成！可以点击保存按钮保存内容")
                yield status, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector
                
        except Exception as e:
            error_msg = f"❌ 小说生成失败：{str(e)}"
            logger.error(error_msg)
            yield error_msg, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector
        finally:
            self.processing = False

    def _save_novel(self, save_path, status_box):
        """保存生成的小说内容到本地文件"""
        if self.final_result == "生成失败":
            error_msg = "❌ 保存失败：小说生成过程已失败，无法保存内容"
            return error_msg, self.__update_status(error_msg)
        
        if not self.validated_outline or not self.validated_characters or not self.all_chapters:
            return "❌ 保存失败：请先完成小说生成（至少需要大纲、角色和章节内容）", status_box
        
        try:
            if not save_path:
                title = self.validated_outline.title.replace(' ', '_').replace('/', '_')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_dir = "result"
                os.makedirs(default_dir, exist_ok=True)
                save_path = os.path.join(default_dir, f"{title}_{timestamp}.txt")
            
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write("=" * 50 + "\n")
                f.write("【小说大纲】\n")
                f.write("=" * 50 + "\n")
                f.write(f"标题: {self.validated_outline.title}\n")
                f.write(f"类型: {self.validated_outline.genre}\n")
                f.write(f"主题: {self.validated_outline.theme}\n")
                f.write(f"背景: {self.validated_outline.setting}\n\n")
                f.write("情节概要:\n")
                f.write(f"{self.validated_outline.plot_summary}\n\n")
                
                f.write("\n" + "=" * 50 + "\n")
                f.write("【角色档案】\n")
                f.write("=" * 50 + "\n")
                for char in self.validated_characters:
                    f.write(f"角色名称: {char.name}\n")
                    f.write(f"背景: {char.background}\n")
                    f.write(f"性格: {char.personality}\n")
                    f.write(f"目标: {', '.join(char.goals)}\n")
                    f.write(f"冲突: {', '.join(char.conflicts)}\n")
                    f.write(f"成长弧线: {char.arc}\n\n")
                
                f.write("\n" + "=" * 50 + "\n")
                f.write("【章节内容】\n")
                f.write("=" * 50 + "\n")
                for i, chapter in enumerate(self.all_chapters, 1):
                    f.write(f"第{i}章: {chapter.title}\n")
                    f.write("-" * 40 + "\n")
                    f.write(f"{chapter.content}\n\n")
            
            success_msg = f"✅ 保存成功！文件路径：{save_path}"
            logger.info(success_msg)
            return success_msg, self.__update_status(success_msg)
            
        except Exception as e:
            error_msg = f"❌ 保存失败：{str(e)}"
            logger.error(error_msg)
            return error_msg, self.__update_status(error_msg)

    # 按章节保存
    def _save_chapter_novel(self, save_path, status_box):
        """保存生成的小说内容到本地文件"""
        if self.final_result == "生成失败":
            error_msg = "❌ 保存失败：小说生成过程已失败，无法保存内容"
            return error_msg, self.__update_status(error_msg)
        
        if not self.validated_outline or not self.validated_characters or not self.all_chapters:
            return "❌ 保存失败：请先完成小说生成（至少需要大纲、角色和章节内容）", status_box
        
        try:
            if not save_path:
                # 处理标题特殊字符，用于创建目录
                title = self.validated_outline.title.replace(' ', '_').replace('/', '_')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_root = "result"
                # 创建主目录：result/标题_时间戳
                main_dir = os.path.join(default_root, f"{title}_{timestamp}")
                os.makedirs(main_dir, exist_ok=True)
                
                # 主文件路径（保存大纲和角色档案）
                main_file_path = os.path.join(main_dir, "00_main_info.txt")
            else:
                # 如果指定了保存路径，将其视为目录
                main_dir = save_path
                os.makedirs(main_dir, exist_ok=True)
                main_file_path = os.path.join(main_dir, "00_main_info.txt")
            
            with open(main_file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 50 + "\n")
                f.write("【小说大纲】\n")
                f.write("=" * 50 + "\n")
                f.write(f"标题: {self.validated_outline.title}\n")
                f.write(f"类型: {self.validated_outline.genre}\n")
                f.write(f"主题: {self.validated_outline.theme}\n")
                f.write(f"背景: {self.validated_outline.setting}\n\n")
                f.write("情节概要:\n")
                f.write(f"{self.validated_outline.plot_summary}\n\n")
                
                f.write("\n" + "=" * 50 + "\n")
                f.write("【角色档案】\n")
                f.write("=" * 50 + "\n")
                for char in self.validated_characters:
                    f.write(f"角色名称: {char.name}\n")
                    f.write(f"背景: {char.background}\n")
                    f.write(f"性格: {char.personality}\n")
                    f.write(f"目标: {', '.join(char.goals)}\n")
                    f.write(f"冲突: {', '.join(char.conflicts)}\n")
                    f.write(f"成长弧线: {char.arc}\n\n")
            
            # 写入主文件（大纲和角色档案）
            with open(main_file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 50 + "\n")
                f.write("【小说大纲】\n")
                f.write("=" * 50 + "\n")
                f.write(f"标题: {self.validated_outline.title}\n")
                f.write(f"类型: {self.validated_outline.genre}\n")
                f.write(f"主题: {self.validated_outline.theme}\n")
                f.write(f"背景: {self.validated_outline.setting}\n\n")
                f.write("情节概要:\n")
                f.write(f"{self.validated_outline.plot_summary}\n\n")
                
                f.write("\n" + "=" * 50 + "\n")
                f.write("【角色档案】\n")
                f.write("=" * 50 + "\n")
                for char in self.validated_characters:
                    f.write(f"角色名称: {char.name}\n")
                    f.write(f"背景: {char.background}\n")
                    f.write(f"性格: {char.personality}\n")
                    f.write(f"目标: {', '.join(char.goals)}\n")
                    f.write(f"冲突: {', '.join(char.conflicts)}\n")
                    f.write(f"成长弧线: {char.arc}\n\n")

            # 分章保存章节内容
            chapter_paths = []
            for i, chapter in enumerate(self.all_chapters, 1):
                # 处理章节标题特殊字符
                chapter_title = chapter.title.replace(' ', '_').replace('/', '_')
                # 章节文件名格式：01_章节标题.txt、02_章节标题.txt...
                chapter_filename = f"{i:02d}_{chapter_title}.txt"
                chapter_path = os.path.join(main_dir, chapter_filename)
                
                with open(chapter_path, 'w', encoding='utf-8') as f:
                    f.write(f"第{i}章: {chapter.title}\n")
                    f.write("-" * 40 + "\n")
                    f.write(f"{chapter.content}\n")
                
                chapter_paths.append(chapter_path)

            # 构建成功消息
            success_msg = f"✅ 保存成功！\n"
            success_msg += f"主文件（大纲+角色）路径：{main_file_path}\n"
            success_msg += f"共保存 {len(chapter_paths)} 个章节文件到目录：{main_dir}"
            logger.info(success_msg)
            return success_msg, self.__update_status(success_msg)
            
        except Exception as e:
            error_msg = f"❌ 保存失败：{str(e)}"
            logger.error(error_msg)
            return error_msg, self.__update_status(error_msg)
    
        
    def _load_css(self, filename):
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return f.read()
        return ""
    
    def create_interface(self):
        """创建优雅布局的Gradio界面"""
        with gr.Blocks(
            title="小说自动生成系统", 
            theme=gr.themes.Soft(),
            css=self._load_css('web/style.css')  # 应用CSS样式
        ) as demo:
            gr.Markdown("""
            <div style="text-align: center;">
                <h1 style="font-size: 1.1rem; 
                            line-height: 1.6; 
                            max-width: 800px; 
                            margin: 0 auto; 
                            padding: 0 1rem;
                            background-image: linear-gradient(to right, #6699FF, #E6F0FF); 
                            -webkit-background-clip: text; 
                            background-clip: text; 
                            color: transparent;">
                        LangGraph-based-Novel-by-Agent
                    </h1>
                <p class="subtitle-text" style="font-size: 1.1rem; color: #4a5568; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 0 1rem;">
                释放AI的想象力<br>
                让AI带你看看它眼中的小说作品
                </p>
            </div>
            """)
            
            # 分隔线
            gr.HTML("""
            <hr style="height: 3px; border: none; background: linear-gradient(90deg, transparent, #6a11cb, transparent); margin: 1.5rem 0; opacity: 0.7;">
            """)
            

            with gr.Row(elem_classes="main-container"):

                with gr.Column(scale=1):
                    gr.Markdown("## ⚙️ 生成设置", elem_classes="panel-title")
                    user_intent = gr.Textbox(
                            label="小说创作意图", 
                            placeholder="例如：科幻题材，关于人工智能觉醒的故事",
                            lines=3,
                            elem_classes="input-field"
                        )
                    
                    # 模型类型选择
                    model_type = gr.Radio(
                        choices=["api", "local"], 
                        label="模型类型", 
                        value="api",
                        elem_classes="model-type-select"
                    )
                    
                    # API模型设置面板
                    with gr.Accordion("API模型设置", open=True, visible=True, elem_id="api-settings") as api_settings:
                        api_key = gr.Textbox(
                            label="API密钥", 
                            #placeholder="输入你的API密钥",
                            value=self.default_api_key,
                            type="password",
                            lines=1
                        )
                        base_url = gr.Textbox(
                            label="API基础地址", 
                            #placeholder="例如：https://api.openai.com/v1",
                            value=self.default_base_url,
                            lines=1
                        )
                        model_name = gr.Textbox(
                            label="模型名称", 
                            placeholder="服务提供商提供的模型名称",
                            lines=1
                        )
                    
                    # 本地模型设置面板
                    with gr.Accordion("本地模型设置", open=True, visible=False, elem_id="local-settings") as local_settings:
                        model_path = gr.Textbox(
                            label="本地模型路径", 
                            placeholder="输入你的本地模型路径",
                            lines=1
                        )
                    
                    # 绑定模型类型切换事件
                    model_type.change(
                        fn=self._toggle_model_settings,
                        inputs=[model_type],
                        outputs=[api_settings, local_settings]
                    )
                    
                    status_box = gr.Textbox(
                                label="状态信息", 
                                lines=2, 
                                interactive=False,
                                elem_classes="status-container"
                            )
                    
                    # 生成模式选择
                    with gr.Row():
                        generate_btn = gr.Button("🚀 自动创作", elem_classes="generate-btn", scale=1)
                        interactive_btn = gr.Button("🎯 交互式创作", elem_classes="generate-btn", scale=1)
                    
                    # 交互式控制按钮（默认隐藏）
                    with gr.Row(visible=False) as approval_buttons:
                        approve_btn = gr.Button("✅ 批准继续", elem_classes="approve-btn", scale=1)
                        reject_btn = gr.Button("❌ 拒绝停止", elem_classes="reject-btn", scale=1)
                       
                    
                    # 保存设置和状态 - 横向排列（2:1比例）
                    with gr.Row(elem_classes="info-card-container"):
                        with gr.Column(scale=2, elem_classes="save-settings-panel"):
                            gr.Markdown("## 💾 保存设置", elem_classes="panel-title")
                            save_path = gr.Textbox(
                                label="保存路径", 
                                placeholder="不填则使用默认路径和文件名",
                                lines=1,
                                elem_classes="input-field"
                            )
                            save_btn = gr.Button("🗄️ 保存小说", elem_classes="save-btn")
                        with gr.Column(scale=1):
                            gr.Markdown("## 📃 保存状态", elem_classes="panel-title")
                            save_status = gr.Textbox(
                                label="保存信息", 
                                lines=2, 
                                interactive=False,
                                elem_classes="save-status-container"
                            )
                
                with gr.Column(scale=1):
                    min_chapters = gr.Slider(
                        minimum=10,
                        maximum=1000,
                        value = 50,
                        step=1,
                        label="最小章节数"
                    )
                    volume = gr.Slider(
                        minimum=1,
                        maximum=10,
                        value = 2,
                        step=1,
                        label="分卷数量"
                    )
                    master_outline = gr.Checkbox(
                        value=True,
                        label="是否开启分卷解析大纲功能"
                    )
                   
                            
                # 右侧内容展示区（占3份宽度）
                with gr.Column(scale=2):
                    with gr.Tabs(elem_classes="info-card"):
                        with gr.Tab("📋 大纲"):
                            with gr.Row():
                                with gr.Column(scale=3):
                                    outline_box = gr.Markdown("等待生成...")
                                with gr.Column(scale=1):
                                    gr.Markdown("### 🛠️ 大纲操作")
                                    # 大纲编辑区域
                                    outline_edit_box = gr.Textbox(
                                        label="编辑大纲",
                                        placeholder="生成大纲后，可在此编辑修改...",
                                        lines=10,
                                        interactive=True,
                                        visible=False
                                    )
                                    # 操作按钮
                                    edit_outline_btn = gr.Button("✏️ 编辑大纲", size="sm")
                                    save_outline_btn = gr.Button("💾 保存大纲", size="sm", visible=False)
                                    cancel_edit_btn = gr.Button("❌ 取消编辑", size="sm", visible=False)
                                    
                                    # 大纲操作状态
                                    outline_status = gr.Textbox(
                                        label="操作状态",
                                        lines=2,
                                        interactive=False
                                    )
                        with gr.Tab("👥 角色档案"):
                            with gr.Row():
                                with gr.Column(scale=3):
                                    characters_box = gr.Markdown("等待生成...")
                                with gr.Column(scale=1):
                                    gr.Markdown("### 🛠️ 角色操作")
                                    # 角色编辑区域
                                    characters_edit_box = gr.Textbox(
                                        label="编辑角色档案",
                                        placeholder="生成角色档案后，可在此编辑修改...",
                                        lines=10,
                                        interactive=True,
                                        visible=False
                                    )
                                    # 操作按钮
                                    edit_characters_btn = gr.Button("✏️ 编辑角色", size="sm")
                                    save_characters_btn = gr.Button("💾 保存角色", size="sm", visible=False)
                                    cancel_characters_edit_btn = gr.Button("❌ 取消编辑", size="sm", visible=False)
                                    
                                    # 角色操作状态
                                    characters_status = gr.Textbox(
                                        label="操作状态",
                                        lines=2,
                                        interactive=False
                                    )
                        with gr.Tab("📄 章节内容"):
                            with gr.Row():
                                with gr.Column(scale=3):
                                    chapter_selector = gr.Dropdown(
                                        label="选择章节", 
                                        choices=[], 
                                        interactive=False
                                    )
                                    chapter_box = gr.Markdown("等待生成...")
                                    chapter_selector.change(
                                        fn=self._show_selected_chapter,
                                        inputs=[chapter_selector],
                                        outputs=[chapter_box]
                                    )
                                with gr.Column(scale=1):
                                    gr.Markdown("### 🛠️ 章节操作")
                                    # 章节编辑区域
                                    chapter_edit_box = gr.Textbox(
                                        label="编辑章节内容",
                                        placeholder="选择章节后，可在此编辑修改...",
                                        lines=15,
                                        interactive=True,
                                        visible=False
                                    )
                                    # 操作按钮
                                    edit_chapter_btn = gr.Button("✏️ 编辑章节", size="sm")
                                    save_chapter_btn = gr.Button("💾 保存章节", size="sm", visible=False)
                                    cancel_chapter_edit_btn = gr.Button("❌ 取消编辑", size="sm", visible=False)
                                    
                                    # 章节操作状态
                                    chapter_status = gr.Textbox(
                                        label="操作状态",
                                        lines=2,
                                        interactive=False
                                    )
                        with gr.Tab("📊 评估反馈"):
                            evaluation_box = gr.Markdown("等待生成...")
            
            # 绑定生成按钮事件
            generate_btn.click(
                fn=self._generate_novel,
                inputs=[
                    user_intent, model_type, api_key, base_url, model_name, model_path, min_chapters,volume, master_outline,
                    status_box, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector
                ],
                outputs=[status_box, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector]
            )
            
            # 绑定交互式生成按钮事件
            interactive_btn.click(
                fn=self._generate_novel_interactive,
                inputs=[
                    user_intent, model_type, api_key, base_url, model_name, model_path, min_chapters, volume, master_outline,
                    status_box, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, approve_btn, reject_btn
                ],
                outputs=[status_box, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector, approval_buttons, approval_buttons]
            )
            
            # 绑定批准按钮事件
            approve_btn.click(
                fn=self._approve_current_step,
                inputs=[],
                outputs=[status_box, approval_buttons, approval_buttons]
            )
            
            # 绑定拒绝按钮事件
            reject_btn.click(
                fn=self._reject_current_step,
                inputs=[],
                outputs=[status_box, approval_buttons, approval_buttons]
            )
            
            # 绑定保存按钮事件
            save_btn.click(
                fn=self._save_chapter_novel,    # 分章节存储
                inputs=[save_path, status_box],
                outputs=[save_status, status_box]
            )
            
            # 绑定大纲操作事件
            edit_outline_btn.click(
                fn=self._toggle_outline_edit,
                inputs=[],
                outputs=[outline_edit_box, edit_outline_btn, save_outline_btn, cancel_edit_btn, outline_status]
            )
            
            cancel_edit_btn.click(
                fn=self._cancel_outline_edit,
                inputs=[],
                outputs=[outline_edit_box, edit_outline_btn, save_outline_btn, cancel_edit_btn, outline_status]
            )
            
            save_outline_btn.click(
                fn=self._save_outline,
                inputs=[outline_edit_box, status_box],
                outputs=[outline_status, status_box, outline_box]
            )
            
            # 绑定角色操作事件
            edit_characters_btn.click(
                fn=self._toggle_characters_edit,
                inputs=[],
                outputs=[characters_edit_box, edit_characters_btn, save_characters_btn, cancel_characters_edit_btn, characters_status]
            )
            
            cancel_characters_edit_btn.click(
                fn=self._cancel_characters_edit,
                inputs=[],
                outputs=[characters_edit_box, edit_characters_btn, save_characters_btn, cancel_characters_edit_btn, characters_status]
            )
            
            save_characters_btn.click(
                fn=self._save_characters,
                inputs=[characters_edit_box, status_box],
                outputs=[characters_status, status_box, characters_box]
            )
            
            # 绑定章节操作事件
            edit_chapter_btn.click(
                fn=self._toggle_chapter_edit,
                inputs=[chapter_selector],
                outputs=[chapter_edit_box, edit_chapter_btn, save_chapter_btn, cancel_chapter_edit_btn, chapter_status]
            )
            
            cancel_chapter_edit_btn.click(
                fn=self._cancel_chapter_edit,
                inputs=[],
                outputs=[chapter_edit_box, edit_chapter_btn, save_chapter_btn, cancel_chapter_edit_btn, chapter_status]
            )
            
            save_chapter_btn.click(
                fn=self._save_chapter,
                inputs=[chapter_edit_box, status_box, chapter_selector],
                outputs=[chapter_status, status_box, chapter_box]
            )
            
            
            
            with gr.Accordion("使用说明", open=False):
                gr.Markdown("""
                ## 📖 基本使用流程
                1. **配置模型**：选择模型类型（API或本地模型）并填写相应配置
                2. **设置参数**：调整最小章节数、分卷数量等生成参数
                3. **输入创作意图**：描述你想要的小说类型和主题
                4. **开始生成**：点击"🚀 开始创作"按钮启动创作流程
                5. **查看结果**：在各个标签页查看生成过程和结果
                6. **保存作品**：生成完成后，通过"🗄️ 保存小说"按钮保存内容
                
                ## 📋 编辑功能
                - **编辑**：点击"✏️ 编辑··"按钮进入编辑模式，直接编辑当前已生成的内容
                - **修改**：在编辑框中直接修改相关内容
                - **保存修改**：点击"💾 保存··"将编辑后的大纲保存到storage目录
                - **取消编辑**：点击"❌ 取消··"退出编辑模式
                - **注意事项**：编辑功能仅在询问批准时生效，请谨慎操作
                
                ## 📑 各标签页功能
                - **📋 大纲**：查看和编辑小说整体结构、章节规划
                - **👥 角色档案**：查看角色背景、性格和成长弧线
                - **📄 章节内容**：浏览各章节详细内容，可通过下拉框切换
                - **📊 评估反馈**：查看章节质量评分和改进建议
                
                """)
        
        return demo
