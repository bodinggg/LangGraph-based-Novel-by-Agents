"""
统一反馈系统 - 合并 outline_feedback_nodes.py, character_feedback_nodes.py, chapter_feedback_nodes.py
通过泛型设计减少代码重复，提高可维护性
"""
from typing import Dict, Any, Literal, TypeVar, Generic, Optional
from src.state import NovelState
from src.model import NovelOutline, Character, ChapterContent
from src.log_config import loggers
import json

logger = loggers['feedback']

# 定义泛型类型变量
T = TypeVar('T')

class FeedbackManager(Generic[T]):
    """统一反馈管理器 - 支持多种类型的反馈"""
    
    def __init__(self, feedback_type: str):
        self.feedback_type = feedback_type
        self.pending_feedback = {}
        self.user_modifications = {}
    
    def request_feedback(self, step: str, content: T, state: NovelState) -> Dict[str, Any]:
        """请求用户反馈"""
        feedback_id = f"{step}_{state.current_chapter_index if hasattr(state, 'current_chapter_index') else 0}"
        # print("="*100)
        # print(f"请求对用户的反馈")
        # print("-"*100)
        # print(f"feedback_id: {feedback_id}")
        # print(f"step: {step}")
        # print(f"content: {content}")
        # print("="*100)
        self.pending_feedback[feedback_id] = {
            "step": step,
            "content": content,
            "status": "pending",
            "timestamp": None,
            "feedback_type": self.feedback_type
        }
        
        logger.info(f"请求用户对{self.feedback_type}的反馈: {step}")
        
        return {
            "feedback_id": feedback_id,
            "step": step,
            "content": content,
            "feedback_type": self.feedback_type
        }
    
    def submit_feedback(self, feedback_id: str, action: str, modified_content: T = None) -> Dict[str, Any]:
        """提交用户反馈"""
        # print("="*100)
        # print(f"请求对用户的反馈")
        # print("-"*100)
        # print(f"feedback_id: {feedback_id}")
        # print(f"action: {action}")

        # print("="*100)
        if feedback_id not in self.pending_feedback:
            raise ValueError(f"未找到{self.feedback_type}反馈ID: {feedback_id}")
        
        feedback = self.pending_feedback[feedback_id]
        feedback["status"] = "completed"
        feedback["action"] = action
        
        if modified_content is not None:
            feedback["modified_content"] = modified_content
            self.user_modifications[feedback_id] = modified_content
            content = modified_content
        else:
            content = feedback["content"]
        
        logger.info(f"用户对{self.feedback_type}的反馈已提交: {action} for {feedback['step']}")
        return {
            "feedback_id": feedback_id,
            "step": feedback['step'],
            "action": feedback['action'],
            "content": content,
            "feedback_type": self.feedback_type
        }


# 全局反馈管理器实例
outline_feedback_manager = FeedbackManager[NovelOutline]("outline")
character_feedback_manager = FeedbackManager[list[Character]]("character")
chapter_feedback_manager = FeedbackManager[ChapterContent]("chapter")


def create_feedback_node(
    feedback_manager: FeedbackManager,
    feedback_id_attr: str,
    feedback_request_attr: str,
    feedback_action_attr: str,
    feedback_error_attr: str,
    file_path_template: str,
    feedback_type_name: str
):
    """创建-反馈节点"""
    
    def feedback_node(state: NovelState) -> Dict[str, Any]:
        """通用反馈节点 - 等待用户确认或修改内容"""
        logger.info(f"进入{feedback_type_name}反馈节点")
        try:
            if state.gradio_mode:
                # Gradio模式：直接通过，不需要交互
                return {
                    feedback_action_attr: "success"
                }
            else:
                # 命令行模式：请求用户交互
                current_index = getattr(state, 'current_chapter_index', 0)
                file_path = file_path_template.format(
                    title=state.novel_storage.load_outline().title,
                    index=current_index + 1,
                    index_padded=f"{current_index + 1:04d}"
                )
                
                step = input(f"您可以查看{file_path}文件，如果需要修改可以直接对源文件内容修改！\n请确认{feedback_type_name}无误，是否需要修改？\n(y(修改)/r(重新生成/n(不做改变)\n")
                feedback_request = feedback_manager.request_feedback(
                    step=f"{feedback_type_name}_review",
                    content=None,
                    state=state
                )
                
                if step.lower() == "y":
                    # 请求用户反馈
                    input("如果您修改完了，回车继续后续流程")
                    action = "continue"
                elif step.lower() == "r":
                    action = "regenerate"
                else:
                    action = "continue"
                
                # 修改内容
                feedback_submit = feedback_manager.submit_feedback(
                    feedback_id=feedback_request["feedback_id"],
                    action= action,
                    modified_content=None
                )
                
                # print("="*100)
                # print(f"{feedback_type_name}反馈完成")
                # print("-"*100)
                # print(f"feedback_submit: {feedback_submit}")
                # print("="*100)
                return {
                    feedback_id_attr: feedback_submit["feedback_id"],
                    feedback_request_attr: feedback_submit
                }
        except Exception as e:
            logger.error(f"处理{feedback_type_name}反馈时出错: {str(e)}")
            return {feedback_error_attr: f"处理{feedback_type_name}反馈失败: {str(e)}"}
        
    return feedback_node


def create_process_feedback_node(
    feedback_manager: FeedbackManager,
    content_attr: str,
    feedback_id_attr: str,
    feedback_action_attr: str,
    feedback_error_attr: str,
    feedback_type_name: str
):
    """创建-处理反馈结果节点"""
    
    def process_feedback_node(state: NovelState) -> Dict[str, Any]:
        """处理反馈结果"""
        logger.info(f"处理{feedback_type_name}反馈结果")
        
        if state.gradio_mode:
            # Gradio模式：直接返回成功
            return {
                feedback_action_attr: "success"
            }
        
        feedback_id = getattr(state, feedback_id_attr, None)
        if not feedback_id:
            return {feedback_error_attr: f"缺少{feedback_type_name}反馈ID"}
        
        try:
            feedback = feedback_manager.pending_feedback.get(feedback_id)
            if not feedback:
                return {feedback_error_attr: f"未找到对应的{feedback_type_name}反馈"}
            
            action = feedback.get("action", "continue")
            
            # 暂未启用
            if action == "modify" and "modified_content" in feedback:
                # 用户修改了内容
                modified_content = feedback["modified_content"]
                logger.info(f"用户修改了{feedback_type_name}，应用修改")
                
                return {
                    content_attr: modified_content,
                    feedback_action_attr: "success"
                }
            elif action == "regenerate":
                # 用户要求重新生成
                logger.info(f"用户要求重新生成{feedback_type_name}")
                return {
                    content_attr: None,
                    feedback_action_attr: "retry"
                }
            else:
                # 用户确认继续
                logger.info(f"用户确认{feedback_type_name}，继续流程")
                return {
                    feedback_action_attr: "success"
                }
                
        except Exception as e:
            logger.error(f"处理{feedback_type_name}反馈时出错: {str(e)}")
            return {feedback_error_attr: f"处理{feedback_type_name}反馈失败: {str(e)}"}
    
    return process_feedback_node


def create_check_feedback_node(
    feedback_action_attr: str,
    feedback_error_attr: str
):
    """创建-检查反馈处理结果节点"""
    
    def check_feedback_node(state: NovelState) -> Literal["success", "retry", "failure"]:
        """检查反馈处理结果"""
        if state.gradio_mode:
            return "success"
        
        logger.info(f"检查反馈处理结果: {feedback_action_attr} = {getattr(state, feedback_action_attr, None)}; {feedback_error_attr} = {getattr(state, feedback_error_attr, None)}")
        
        if getattr(state, feedback_error_attr, None):
            return "failure"

        action = getattr(state, feedback_action_attr, "success")
        
        if action == "retry":
            return "retry"
        elif action == "modify":
            return "success"
        else:
            return "success"
    
    return check_feedback_node


# 使用工厂函数创建具体的反馈节点
outline_feedback_node = create_feedback_node(
    feedback_manager=outline_feedback_manager,
    feedback_id_attr="outline_feedback_id",
    feedback_request_attr="outline_feedback_request",
    feedback_action_attr="outline_feedback_action",
    feedback_error_attr="outline_feedback_error",
    file_path_template="result/{title}_storage/outline.json",
    feedback_type_name="大纲"
)

process_outline_feedback_node = create_process_feedback_node(
    feedback_manager=outline_feedback_manager,
    content_attr="validated_outline",
    feedback_id_attr="outline_feedback_id",
    feedback_action_attr="outline_feedback_action",
    feedback_error_attr="outline_feedback_error",
    feedback_type_name="大纲"
)

check_outline_feedback_node = create_check_feedback_node(
    feedback_action_attr="outline_feedback_action",
    feedback_error_attr="outline_feedback_error"
)

character_feedback_node = create_feedback_node(
    feedback_manager=character_feedback_manager,
    feedback_id_attr="character_feedback_id",
    feedback_request_attr="character_feedback_request",
    feedback_action_attr="character_feedback_action",
    feedback_error_attr="character_feedback_error",
    file_path_template="result/{title}_storage/characters.json",
    feedback_type_name="角色档案"
)

process_character_feedback_node = create_process_feedback_node(
    feedback_manager=character_feedback_manager,
    content_attr="validated_characters",
    feedback_id_attr="character_feedback_id",
    feedback_action_attr="character_feedback_action",
    feedback_error_attr="character_feedback_error",
    feedback_type_name="角色档案"
)

check_character_feedback_node = create_check_feedback_node(
    feedback_action_attr="character_feedback_action",
    feedback_error_attr="character_feedback_error"
)

chapter_feedback_node = create_feedback_node(
    feedback_manager=chapter_feedback_manager,
    feedback_id_attr="chapter_feedback_id",
    feedback_request_attr="chapter_feedback_request",
    feedback_action_attr="chapter_feedback_action",
    feedback_error_attr="chapter_feedback_error",
    file_path_template="result/{title}_storage/chapters_json/{index_padded}.json",
    feedback_type_name="章节内容"
)

process_chapter_feedback_node = create_process_feedback_node(
    feedback_manager=chapter_feedback_manager,
    content_attr="validated_chapter_draft",
    feedback_id_attr="chapter_feedback_id",
    feedback_action_attr="chapter_feedback_action",
    feedback_error_attr="chapter_feedback_error",
    feedback_type_name="章节内容"
)

check_chapter_feedback_node = create_check_feedback_node(
    feedback_action_attr="chapter_feedback_action",
    feedback_error_attr="chapter_feedback_error"
)
