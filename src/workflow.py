"""
定义工作状态, 核心部分
"""
from langgraph.graph import StateGraph, END
from src.agent import OutlineGeneratorAgent, CharacterAgent, WriterAgent, ReflectAgent 
from src.node import *
from src.client import SharedModelManager
from src.state import NovelState
from src.log_config import loggers

logger = loggers['workflow']

# 构建工作流
def create_workflow(model_path: str) -> StateGraph:
    """创建包含章节写作和质量评审的完整工作流"""
    # 获取共享模型实例和分词器
    shared_pipeline, shared_tokenizer = SharedModelManager.get_instance(model_path)
    logger.info("成功加载共享模型实例和分词器")
    # 初始化使用共享模型的代理
    outline_agent = OutlineGeneratorAgent(shared_pipeline, shared_tokenizer)    # 大纲
    character_agent = CharacterAgent(shared_pipeline, shared_tokenizer)         # 角色
    writer_agent = WriterAgent(shared_pipeline, shared_tokenizer)               # 写作
    reflect_agent = ReflectAgent(shared_pipeline, shared_tokenizer)             # 反思
    
    logger.info("代理初始化完成, 开始构建工作流图...")
    
    # 创建图
    workflow = StateGraph(NovelState)
    # -------------------- 创建节点 --------------------
    # 大纲
    workflow.add_node("generate_outline", 
                     lambda state: generate_outline_node(state, outline_agent))
    workflow.add_node("validate_outline", validate_outline_node)
    
    # 角色
    workflow.add_node("generate_characters", 
                     lambda state: generate_characters_node(state, character_agent))
    workflow.add_node("validate_characters",validate_characters_node)
    
    # 写作
    workflow.add_node("write_chapter",
                      lambda state: write_chapter_node(state, writer_agent))
    workflow.add_node("validate_chapter", validate_chapter_node)
    
    # 评估
    workflow.add_node("evaluate_chapter",
                      lambda state: evaluate_chapter_node(state, reflect_agent))
    workflow.add_node("validate_evaluate", validate_evaluate_node)
    
    workflow.add_node("evaluate2wirte", evaluation_to_chapter_node)
    
    # 接受本章
    workflow.add_node("accpet_chapter", accept_chapter_node)
    
    workflow.add_node("success", lambda state: {
        "result": "小说创作流程完成",
        "final_outline": state.validated_outline,
        "final_characters":state.validated_characters,
        "final_content": state.chapters_content
    })
    
    workflow.add_node("failure", lambda state: {
        "result": "生成失败", 
        "final_error": state.outline_validated_error or state.characters_validated_error or state.current_chapter_validated_error or state.evaluation_validated_error
    })
    
    
    # -------------------- 创建边 --------------------
    # 大纲
    workflow.set_entry_point("generate_outline")
    workflow.add_edge("generate_outline", "validate_outline")
    workflow.add_conditional_edges(
        "validate_outline",
        check_outline_node,
        {
            "success": "generate_characters",
            "retry": "generate_outline",
            "failure": "failure"
        }
    )
    
    # 角色档案
    workflow.add_edge("generate_characters", "validate_characters")
    workflow.add_conditional_edges(
        "validate_characters",
        check_characters_node,
        {
            "success": "write_chapter",
            "retry": "generate_characters",
            "failure": "failure"
        }
    )
    
    # 写作
    workflow.add_edge("write_chapter", "validate_chapter")
    workflow.add_conditional_edges(
        "validate_chapter",
        check_chapter_node,
        {
            "success": "evaluate_chapter",
            "retry": "write_chapter",
            "failure": "failure"
        }
    )
    
    
    # 评估
    workflow.add_edge("evaluate_chapter", "validate_evaluate")
    workflow.add_conditional_edges(
        "validate_evaluate",
        check_evaluation_node,
        {
            "success": "evaluate2wirte",
            "retry": "evaluate_chapter",
            "failure":"failure"
        }
    )
    workflow.add_conditional_edges(
        "evaluate2wirte",
        check_evaluation_chapter_node,
        {
            "accept":"accpet_chapter",
            "revise":"write_chapter",
            "force_accpet":"accpet_chapter"
        }
    )
    
    workflow.add_conditional_edges(
        "accpet_chapter",
        check_chapter_completion_node,
        {
            "complete":"success",
            "continue":"write_chapter"
        }
    )
    
    workflow.add_edge("success", END)
    workflow.add_edge("failure", END)
    logger.info("工作流图创建完成, 开始编译!")
    # 编译图
    return workflow.compile()
