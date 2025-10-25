"""
角色档案反馈节点 - 在角色档案生成环节添加人工审查功能
"""
from typing import Dict, Any, Literal
from src.state import NovelState
from src.model import Character
from src.log_config import loggers
import json

logger = loggers['feedback']

class CharacterFeedbackManager:
    """角色档案反馈管理器"""
    
    def __init__(self):
        self.pending_feedback = {}
        self.user_modifications = {}
    
    def request_feedback(self, step: str, content: Any, state: NovelState) -> Dict[str, Any]:
        """请求用户对角色档案的反馈"""
        feedback_id = f"{step}_{state.current_chapter_index if hasattr(state, 'current_chapter_index') else 0}"
        
        self.pending_feedback[feedback_id] = {
            "step": step,
            "content": content,
            "status": "pending",
            "timestamp": None
        }
        
        logger.info(f"请求用户对角色档案的反馈: {step}")
        
        return {
            "feedback_id": feedback_id,
            "step": step,
            "content": content,
            "requires_feedback": True
        }
    
    def submit_feedback(self, feedback_id: str, action: str, modified_content: Any = None) -> Dict[str, Any]:
        """提交用户对角色档案的反馈"""
        if feedback_id not in self.pending_feedback:
            raise ValueError(f"未找到角色档案反馈ID: {feedback_id}")
        
        feedback = self.pending_feedback[feedback_id]
        feedback["status"] = "completed"
        feedback["action"] = action
        
        if modified_content is not None:
            feedback["modified_content"] = modified_content
            self.user_modifications[feedback_id] = modified_content
            content = modified_content
        else:
            content = feedback["content"]
        
        logger.info(f"用户对角色档案的反馈已提交: {action} for {feedback['step']}")
        return {
            "feedback_id": feedback_id,
            "step": feedback['step'],
            "content": content,
            "requires_feedback": True
        }


# 全局角色档案反馈管理器实例
character_feedback_manager = CharacterFeedbackManager()

def character_feedback_node(state: NovelState) -> Dict[str, Any]:
    """角色档案反馈节点 - 等待用户确认或修改角色档案"""
    logger.info("进入角色档案反馈节点")
    
    if not state.validated_characters:
        return {
            "character_feedback_error": "没有可用的角色档案进行反馈",
            "requires_feedback": False
        }
    
    if state.gradio_mode:
        # Gradio模式：直接通过，不需要交互
        return {
            "character_modified": False,
            "character_feedback_action": "success"
        }
    else:
        # 命令行模式：请求用户交互
        step = input(f"您可以查看result/{state.novel_storage.load_outline().title}_storage下的 characters.json文件，如果需要修改可以直接对源文件内容修改！\n请确认角色档案无误，是否需要修改？(y/n)")
        feedback_request = character_feedback_manager.request_feedback(
                step="character_review",
                content=state.validated_characters,
                state=state
            )
        if step.lower() == "y":
            # 请求用户对角色档案的反馈
            input("如果您修改完了，回车继续后续流程")
            # 修改角色档案
            feedback_sumbit = character_feedback_manager.submit_feedback(
                feedback_id=feedback_request["feedback_id"],
                action="continue",
                modified_content=state.validated_characters  # 直接使用当前的角色档案作为修改后的内容
            )
        else:
            # 确认角色档案无误，直接进入下一步，不需要修改
            feedback_sumbit = character_feedback_manager.submit_feedback(
                feedback_id=feedback_request["feedback_id"],
                action="continue"
            )
        return {
            "character_feedback_id": feedback_sumbit["feedback_id"],
            "character_feedback_request": feedback_sumbit,
            "requires_feedback": True,
            "character_feedback_step": feedback_sumbit["step"]
        }

def process_character_feedback_node(state: NovelState) -> Dict[str, Any]:
    """处理角色档案反馈结果"""
    logger.info("处理角色档案反馈结果")
    
    if state.gradio_mode:
        # Gradio模式：直接返回成功
        return {
            "character_modified": False,
            "character_feedback_action": "success"
        }
    
    feedback_id = state.character_feedback_id
    if not feedback_id:
        return {"character_feedback_error": "缺少角色档案反馈ID"}
    
    try:
        feedback = character_feedback_manager.pending_feedback.get(feedback_id)
        if not feedback:
            return {"character_feedback_error": "未找到对应的角色档案反馈"}
        
        action = feedback.get("action", "continue")
        
        if action == "modify" and "modified_content" in feedback:
            # 用户修改了角色档案
            modified_characters = feedback["modified_content"]
            logger.info("用户修改了角色档案，应用修改")
            
            return {
                "validated_characters": modified_characters,
                "character_modified": True,
                "character_feedback_action": "success"
            }
        elif action == "regenerate":
            # 用户要求重新生成
            logger.info("用户要求重新生成角色档案")
            return {
                "validated_characters": None,
                "character_modified": False,
                "character_feedback_action": "retry"
            }
        else:
            # 用户确认继续
            logger.info("用户确认角色档案，继续流程")
            return {
                "character_modified": False,
                "character_feedback_action": "success"
            }
            
    except Exception as e:
        logger.error(f"处理角色档案反馈时出错: {str(e)}")
        return {"character_feedback_error": f"处理角色档案反馈失败: {str(e)}"}

def check_character_feedback_node(state: NovelState) -> Literal["success", "retry", "failure"]:
    """检查角色档案反馈处理结果"""
    if state.gradio_mode:
        return "success"
    
    logger.info(f"检查角色档案反馈处理结果: state.character_feedback_action = {state.character_feedback_action}; state.character_feedback_error = {state.character_feedback_error}")
    if state.character_feedback_error:
        return "failure"

    action = state.character_feedback_action
    
    if action == "retry":
        return "retry"
    elif action == "modify":
        return "success"
    else:
        return "success"
