"""
用户反馈节点 - 简化版本
在关键环节添加人工审查功能
"""
from typing import Dict, Any, Literal
from src.state import NovelState
from src.model import NovelOutline
from src.log_config import loggers
import json

logger = loggers['feedback']

class FeedbackManager:
    """简化的反馈管理器"""
    
    def __init__(self):
        self.pending_feedback = {}
        self.user_modifications = {}
    
    def request_feedback(self, step: str, content: Any, state: NovelState) -> Dict[str, Any]:
        """请求用户反馈"""
        feedback_id = f"{step}_{state.current_chapter_index if hasattr(state, 'current_chapter_index') else 0}"
        print(f"[test] feedback_id: {feedback_id}")
        
        self.pending_feedback[feedback_id] = {
            "step": step,
            "content": content,
            "status": "pending",
            "timestamp": None
        }
        
        logger.info(f"请求用户反馈: {step}")
        
        
        return {
            "feedback_id": feedback_id,
            "step": step,
            "content": content,
            "requires_feedback": True
        }
    
    def submit_feedback(self, feedback_id: str, action: str, modified_content: Any = None) -> Dict[str, Any]:
        """提交用户反馈"""
        if feedback_id not in self.pending_feedback:
            raise ValueError(f"未找到反馈ID: {feedback_id}")
        
        feedback = self.pending_feedback[feedback_id]
        feedback["status"] = "completed"
        feedback["action"] = action
        
        if modified_content is not None:
            feedback["modified_content"] = modified_content
            self.user_modifications[feedback_id] = modified_content
            content = modified_content
        else:
            content = feedback["content"]
        
        
        logger.info(f"用户反馈已提交: {action} for {feedback['step']}")
        return {
            "feedback_id": feedback_id,
            "step": feedback['step'],
            "content": content,
            "requires_feedback": True
        }


# 全局反馈管理器实例
feedback_manager = FeedbackManager()

def outline_feedback_node(state: NovelState) -> Dict[str, Any]:
    """大纲反馈节点 - 等待用户确认或修改大纲"""
    logger.info("进入大纲反馈节点")
    
    if not state.validated_outline:
        return {
            "feedback_error": "没有可用的大纲进行反馈",
            "requires_feedback": False
        }
    
    if state.gradio_mode:
        # Gradio模式：直接通过，不需要交互
        return {
            "outline_modified": False,
            "feedback_action": "success"
        }
    else:
        # 命令行模式：请求用户交互
        step = input(f"您可以查看result/{state.novel_storage.load_outline().title}_storage下的 outline.json文件，如果需要修改可以直接对源文件内容修改！\n请确认大纲无误，是否需要修改？(y/n)")
        feedback_request = feedback_manager.request_feedback(
                step="outline_review",
                content=state.validated_outline,
                state=state
            )
        if step.lower() == "y":
            # 请求用户对大纲的反馈
            input("如果您修改完了，回车继续后续流程")
            # 修改大纲
            feedback_sumbit = feedback_manager.submit_feedback(
                feedback_id=feedback_request["feedback_id"],
                action="continue",
                modified_content=state.validated_outline        # 直接使用当前的大纲作为修改后的内容
            )
        else:
            # 确认大纲无误，直接进入下一步，不需要修改大纲
            feedback_sumbit = feedback_manager.submit_feedback(
                feedback_id=feedback_request["feedback_id"],
                action="continue"
            )
        return {
            "outline_feedback_id": feedback_sumbit["feedback_id"],
            "outline_feedback_request": feedback_sumbit,
            "requires_feedback": True,
            "feedback_step": feedback_sumbit["step"]
        }

def process_outline_feedback_node(state: NovelState) -> Dict[str, Any]:
    """处理大纲反馈结果"""
    logger.info("处理大纲反馈结果")
    
    if state.gradio_mode:
        # Gradio模式：直接返回成功
        return {
            "outline_modified": False,
            "feedback_action": "success"
        }
    
    feedback_id = state.outline_feedback_id
    if not feedback_id:
        return {"feedback_error": "缺少反馈ID"}
    
    try:
        feedback = feedback_manager.pending_feedback.get(feedback_id)
        if not feedback:
            return {"feedback_error": "未找到对应的反馈"}
        
        action = feedback.get("action", "continue")
        
        if action == "modify" and "modified_content" in feedback:
            # 用户修改了大纲
            modified_outline = feedback["modified_content"]
            logger.info("用户修改了大纲，应用修改")
            
            return {
                "validated_outline": modified_outline,
                "outline_modified": True,
                "feedback_action": "success"
            }
        elif action == "regenerate":
            # 用户要求重新生成
            logger.info("用户要求重新生成大纲")
            return {
                "validated_outline": None,
                "outline_modified": False,
                "feedback_action": "retry"
            }
        else:
            # 用户确认继续
            logger.info("用户确认大纲，继续流程")
            return {
                "outline_modified": False,
                "feedback_action": "success"
            }
            
    except Exception as e:
        logger.error(f"处理大纲反馈时出错: {str(e)}")
        return {"feedback_error": f"处理反馈失败: {str(e)}"}

def check_outline_feedback_node(state: NovelState) -> Literal["success", "retry", "failure"]:
    """检查大纲反馈处理结果"""
    if state.gradio_mode:
        return "success"
    
    logger.info(f"检查大纲反馈处理结果: state.feedback_action = {state.feedback_action}; state.feedback_error = {state.feedback_error}")
    if state.feedback_error:
        return "failure"

    action = state.feedback_action
    
    if action == "retry":
        return "retry"
    elif action == "modify":
        return "success"
    else:
        return "success"
