"""
章节内容反馈节点 - 在章节撰写环节添加人工审查功能
"""
from typing import Dict, Any, Literal
from src.state import NovelState
from src.model import ChapterContent
from src.log_config import loggers
import json

logger = loggers['feedback']

class ChapterFeedbackManager:
    """章节内容反馈管理器"""
    
    def __init__(self):
        self.pending_feedback = {}
        self.user_modifications = {}
    
    def request_feedback(self, step: str, content: Any, state: NovelState) -> Dict[str, Any]:
        """请求用户对章节内容的反馈"""
        feedback_id = f"{step}_{state.current_chapter_index}"
        
        self.pending_feedback[feedback_id] = {
            "step": step,
            "content": content,
            "status": "pending",
            "timestamp": None
        }
        
        logger.info(f"请求用户对章节内容的反馈: {step}")
        
        return {
            "feedback_id": feedback_id,
            "step": step,
            "content": content,
            "requires_feedback": True
        }
    
    def submit_feedback(self, feedback_id: str, action: str, modified_content: Any = None) -> Dict[str, Any]:
        """提交用户对章节内容的反馈"""
        if feedback_id not in self.pending_feedback:
            raise ValueError(f"未找到章节内容反馈ID: {feedback_id}")
        
        feedback = self.pending_feedback[feedback_id]
        feedback["status"] = "completed"
        feedback["action"] = action
        
        if modified_content is not None:
            feedback["modified_content"] = modified_content
            self.user_modifications[feedback_id] = modified_content
            content = modified_content
        else:
            content = feedback["content"]
        
        logger.info(f"用户对章节内容的反馈已提交: {action} for {feedback['step']}")
        return {
            "feedback_id": feedback_id,
            "step": feedback['step'],
            "content": content,
            "requires_feedback": True
        }


# 全局章节内容反馈管理器实例
chapter_feedback_manager = ChapterFeedbackManager()

def chapter_feedback_node(state: NovelState) -> Dict[str, Any]:
    """章节内容反馈节点 - 等待用户确认或修改章节内容"""
    logger.info("进入章节内容反馈节点")
    
    if not state.validated_chapter_draft:
        return {
            "chapter_feedback_error": "没有可用的章节内容进行反馈",
            "requires_feedback": False
        }
    
    if state.gradio_mode:
        # Gradio模式：直接通过，不需要交互
        return {
            "chapter_modified": False,
            "chapter_feedback_action": "success"
        }
    else:
        # 命令行模式：请求用户交互
        current_index = state.current_chapter_index
        step = input(f"您可以查看result/{state.novel_storage.load_outline().title}_storage/chapters_json/{state.current_chapter_index+1:04d}.json 文件，如果需要修改可以直接对源文件内容修改！\n请确认第{current_index + 1}章内容无误，是否需要修改？(y/n)")
        feedback_request = chapter_feedback_manager.request_feedback(
                step="chapter_review",
                content=state.validated_chapter_draft,
                state=state
            )
        if step.lower() == "y":
            # 请求用户对章节内容的反馈
            input("如果您修改完了，回车继续后续流程")
            # 修改章节内容
            feedback_sumbit = chapter_feedback_manager.submit_feedback(
                feedback_id=feedback_request["feedback_id"],
                action="continue",
                modified_content=state.validated_chapter_draft  # 直接使用当前的章节内容作为修改后的内容
            )
        else:
            # 确认章节内容无误，直接进入下一步，不需要修改
            feedback_sumbit = chapter_feedback_manager.submit_feedback(
                feedback_id=feedback_request["feedback_id"],
                action="continue"
            )
        return {
            "chapter_feedback_id": feedback_sumbit["feedback_id"],
            "chapter_feedback_request": feedback_sumbit,
            "requires_feedback": True,
            "chapter_feedback_step": feedback_sumbit["step"]
        }

def process_chapter_feedback_node(state: NovelState) -> Dict[str, Any]:
    """处理章节内容反馈结果"""
    logger.info("处理章节内容反馈结果")
    
    if state.gradio_mode:
        # Gradio模式：直接返回成功
        return {
            "chapter_modified": False,
            "chapter_feedback_action": "success"
        }
    
    feedback_id = state.chapter_feedback_id
    if not feedback_id:
        return {"chapter_feedback_error": "缺少章节内容反馈ID"}
    
    try:
        feedback = chapter_feedback_manager.pending_feedback.get(feedback_id)
        if not feedback:
            return {"chapter_feedback_error": "未找到对应的章节内容反馈"}
        
        action = feedback.get("action", "continue")
        
        if action == "modify" and "modified_content" in feedback:
            # 用户修改了章节内容
            modified_chapter = feedback["modified_content"]
            logger.info("用户修改了章节内容，应用修改")
            
            return {
                "validated_chapter_draft": modified_chapter,
                "chapter_modified": True,
                "chapter_feedback_action": "success"
            }
        elif action == "regenerate":
            # 用户要求重新生成
            logger.info("用户要求重新生成章节内容")
            return {
                "validated_chapter_draft": None,
                "chapter_modified": False,
                "chapter_feedback_action": "retry"
            }
        else:
            # 用户确认继续
            logger.info("用户确认章节内容，继续流程")
            return {
                "chapter_modified": False,
                "chapter_feedback_action": "success"
            }
            
    except Exception as e:
        logger.error(f"处理章节内容反馈时出错: {str(e)}")
        return {"chapter_feedback_error": f"处理章节内容反馈失败: {str(e)}"}

def check_chapter_feedback_node(state: NovelState) -> Literal["success", "retry", "failure"]:
    """检查章节内容反馈处理结果"""
    if state.gradio_mode:
        return "success"
    
    logger.info(f"检查章节内容反馈处理结果: state.chapter_feedback_action = {state.chapter_feedback_action}; state.chapter_feedback_error = {state.chapter_feedback_error}")
    if state.chapter_feedback_error:
        return "failure"

    action = state.chapter_feedback_action
    
    if action == "retry":
        return "retry"
    elif action == "modify":
        return "success"
    else:
        return "success"
