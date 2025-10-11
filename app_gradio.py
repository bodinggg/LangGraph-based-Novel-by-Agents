import gradio as gr
import os
import argparse
from datetime import datetime
from src.workflow import create_workflow
from src.log_config import loggers
from src.model import NovelOutline
from src.config_loader import ModelConfig, BaseConfig

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, help="端口号", default=8000)
    return parser.parse_args()

# 初始化日志记录器
logger = loggers['gradio']

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
        self.default_api_key = os.getenv("API_KEY", "")
        self.default_base_url = os.getenv("BASE_URL", "")

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
            outline_str += f"**第{i}章**: {chapter.title}\n\n"
            outline_str += f"  摘要: {chapter.summary}\n\n"
            outline_str += f"  关键事件: {', '.join(chapter.key_events)}\n\n"
            outline_str += f"  涉及角色: {', '.join(chapter.characters_involved)}\n\n"
            
        return outline_str

    def _format_characters(self, characters):
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
        eval_str += evaluation.feedback
        
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

    def _generate_novel(self, user_intent, model_type, api_key, base_url, model_name, model_path, min_chapters, volume, master_outline,
                      status_box, outline_box, characters_box, chapter_box, evaluation_box, chapter_selector):
        """生成小说的主流程（生成器函数）"""
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
                {"user_intent": user_intent},
                {"recursion_limit": 1000}
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
                    
                    if state_dict.get('chapters_content'):
                        self.all_chapters = state_dict['chapters_content']
                        chapter_selector = self._update_chapter_selection(self.all_chapters)
                        chapter_box = self._format_chapter(
                            self.all_chapters[-1], 
                            len(self.all_chapters)-1
                        )
                    elif state_dict.get('validated_chapter_draft'):
                        current_index = state_dict.get('current_chapter_index', 0)
                        chapter_box = self._format_chapter(
                            state_dict['validated_chapter_draft'], 
                            current_index
                        )
                        if len(self.all_chapters) <= current_index:
                            self.all_chapters.insert(current_index, state_dict['validated_chapter_draft'])
                            chapter_selector = self._update_chapter_selection(self.all_chapters)
                    
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
                            placeholder="输入你的API密钥",
                            value=self.default_api_key,
                            type="password",
                            lines=1
                        )
                        base_url = gr.Textbox(
                            label="API基础地址", 
                            placeholder="例如：https://api.openai.com/v1",
                            value=self.default_base_url,
                            lines=1
                        )
                        model_name = gr.Textbox(
                            label="模型名称", 
                            placeholder="例如：gpt-4o",
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
                    generate_btn = gr.Button("🚀 开始创作", elem_classes="generate-btn")
                       
                    
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
                            outline_box = gr.Markdown("等待生成...")
                        with gr.Tab("👥 角色档案"):
                            characters_box = gr.Markdown("等待生成...")
                        with gr.Tab("📄 章节内容"):
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
            
            # 绑定保存按钮事件
            save_btn.click(
                fn=self._save_chapter_novel,    # 分章节存储
                inputs=[save_path, status_box],
                outputs=[save_status, status_box]
            )
            
            with gr.Accordion("使用说明", open=False):
                gr.Markdown("""
                1. 选择模型类型（API或本地模型）并填写相应配置
                2. 输入小说创作意图
                3. 点击"开始生成"按钮启动创作流程
                4. 在各个标签页查看生成过程和结果：
                   - 📋 大纲：查看小说整体结构和章节规划
                   - 👥 角色档案：查看角色背景、性格和成长弧线
                   - 📄 章节内容：浏览各章节详细内容，可通过下拉框切换
                   - 📊 评估反馈：查看章节质量评分和改进建议
                5. 生成完成后，可通过"保存小说"按钮将内容保存到本地文件
                """)
        
        return demo

if __name__ == "__main__":
    args = get_args()
    ui = NovelGeneratorUI()
    demo = ui.create_interface()
    # 自定义端口号
    demo.launch(server_port=args.port)
