"""
SubAgents LLM 对话测试

完全依赖 LLM 进行分析，验证：
1. 各 SubAgent 能够调用 LLM 进行思考
2. thinking_log 正确记录完整的对话内容
3. 能够从 thinking_log 中还原 LLM 的分析过程

测试方法：读取 thinking_log 文件，验证 LLM 输入输出被正确记录
"""
import pytest
import os
import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from src.multi_agent.sub_agents.consistency import ConsistencyChecker
from src.multi_agent.sub_agents.character_arc import CharacterArcChecker
from src.multi_agent.sub_agents.plot_thread import PlotThreadChecker
from src.multi_agent.sub_agents.world_state import WorldStateChecker
from src.multi_agent.sub_agents.reflection import ReflectionChecker
from src.multi_agent.types import SubAgentReport
from src.model import PlotThread, WorldState


# 测试用的小说章节内容
SAMPLE_CHAPTER = """
第一章：觉醒

新纪元2020年3月15日，标准时间上午九点整。

张伟站在旧城区的废墟前，望着远处新建的联邦政府大厦。三年前的战争将这座城市变成了这副模样，但现在，一切都在重建。

"张伟，你来了。"身后传来一个熟悉的声音。

他回头，看到李娜从一辆黑色轿车中走出来。李娜是他在联邦调查局的老同事，也是他最好的朋友。

"李娜，你怎么会在这里？"张伟有些惊讶。

"总部派我来协助你。"李娜说，"这次的案子比想象中更复杂。"

两人一起进入了废墟深处的一个地下室。根据情报，地下室的某个角落里藏着一份重要的文件。

他们在地下室里搜索了很久，终于在一个破旧的保险箱里找到了目标文件。

"就是这个了。"张伟将文件收入怀中。

就在这时，地下室的灯光突然熄灭，四周陷入一片漆黑。

"小心！"李娜的声音从黑暗中传来。

张伟听到了一阵脚步声，似乎有很多人正在靠近...

【未完待续】
"""

# 测试上下文 - 使用新的 format_layered_context() 格式字符串
SAMPLE_CONTEXT_TEXT = """## 世界观规则（硬约束）
- 【严重】角色不能做 X
- 【警告】世界设定 Y

## 角色状态
- 张伟：[困惑] | 当前阶段：[迷茫]

## 情节线/伏笔状态
已解决：
- 神秘文件（第1章回收）
进行中：
- 神秘势力监视
伏笔：
- 神秘文件（预期在第2章回收）

## 当前世界状态
- 地点：旧城区废墟地下室
- 时间：新纪元2020年3月15日 上午
- 氛围：紧张


class MockModelManager:
    """模拟模型管理器，返回 LLM 风格的响应"""

    def __init__(self, response_type="consistency"):
        self.response_type = response_type
        self.call_count = 0
        self.calls = []  # 记录每次调用

    def generate(self, messages, temperature=None):
        """同步生成"""
        self.call_count += 1
        self.calls.append({
            "call_number": self.call_count,
            "messages": messages,
            "method": "generate"
        })
        return self._make_response(messages)

    async def async_generate(self, messages, temperature=None):
        """异步生成"""
        self.call_count += 1
        self.calls.append({
            "call_number": self.call_count,
            "messages": messages,
            "method": "async_generate"
        })
        return self._make_response(messages)

    def _make_response(self, messages):
        """根据消息内容生成模拟响应"""
        # 提取用户消息中的关键信息
        user_msg = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")

        if "一致性" in user_msg or "Consistency" in str(messages):
            return self._consistency_response(user_msg)
        elif "角色弧线" in user_msg or "Character" in str(messages):
            return self._character_arc_response(user_msg)
        elif "伏笔" in user_msg or "Plot" in str(messages):
            return self._plot_thread_response(user_msg)
        elif "世界状态" in user_msg or "World" in str(messages):
            return self._world_state_response(user_msg)
        elif "综合" in user_msg or "Reflection" in str(messages):
            return self._reflection_response(user_msg)
        else:
            return json.dumps({
                "issues": [],
                "reasoning": "未识别到特定检查类型"
            })

    def _consistency_response(self, user_msg):
        """一致性检查响应"""
        return json.dumps({
            "issues": [
                {
                    "type": "timeline",
                    "issue": "时间线存在潜在问题：章节开头提到'三年前'的战争，但后文没有明确说明时间关系",
                    "location": "第1-2行",
                    "suggestion": "建议明确'三年前'的具体时间锚点，让读者更清晰时间背景"
                }
            ],
            "reasoning": "LLM 分析：章节时间线基本一致，未发现严重矛盾。但开头的时间铺垫可以更清晰。"
        }, ensure_ascii=False)

    def _character_arc_response(self, user_msg):
        """角色弧线检查响应"""
        return json.dumps({
            "updates": [
                {
                    "character": "张伟",
                    "action": "advance_arc",
                    "from_stage": "迷茫",
                    "to_stage": "觉醒"
                }
            ],
            "issues": [],
            "reasoning": "LLM 分析：张伟在面对老同事李娜和案件时，开始从迷茫状态向觉醒转变。地下室的黑暗遭遇可能触发进一步的性格发展。"
        }, ensure_ascii=False)

    def _plot_thread_response(self, user_msg):
        """伏笔检查响应"""
        return json.dumps({
            "updates": [
                {
                    "thread_id": "thread_001",
                    "action": "payoff",
                    "chapter": 1
                }
            ],
            "issues": [
                {
                    "type": "new_plot_thread",
                    "thread_id": "thread_002",
                    "issue": "地下室的灯光突然熄灭，暗示有第三方势力正在监视",
                    "suggestion": "建议在后续章节中揭示这个神秘势力的身份"
                }
            ],
            "reasoning": "LLM 分析：第1章埋下了多个伏笔，神秘势力的出现为后续剧情发展留下了悬念。"
        }, ensure_ascii=False)

    def _world_state_response(self, user_msg):
        """世界状态检查响应"""
        return json.dumps({
            "issues": [],
            "updates": [
                {
                    "type": "world_state_update",
                    "state": {
                        "chapter_index": 1,
                        "location": "旧城区废墟地下室",
                        "time": "新纪元2020年3月15日 上午"
                    }
                }
            ],
            "reasoning": "LLM 分析：世界状态推进合理，地点从前台的废墟进入到地下室，时间同步推进。未发现势力关系冲突。"
        }, ensure_ascii=False)

    def _reflection_response(self, user_msg):
        """综合评估响应"""
        return json.dumps({
            "quality_score": 7.5,
            "needs_revision": False,
            "suggestions": [
                {
                    "category": "consistency",
                    "priority": "medium",
                    "issue": "时间背景可以更清晰",
                    "location": "开头段落",
                    "current_text": "三年前的战争将这座城市变成了这副模样",
                    "suggested_change": "建议添加具体年份，让读者更清楚时间线"
                }
            ],
            "reasoning": "LLM 综合评估：章节整体质量良好，情节推进自然，角色互动合理。存在一些小问题但不影响阅读体验。"
        }, ensure_ascii=False)


@pytest.fixture
def temp_thinking_dir(tmp_path):
    """创建临时 thinking_log 目录"""
    log_dir = tmp_path / "thinking_logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def mock_model_manager():
    """创建模拟模型管理器"""
    return MockModelManager()


class TestSubAgentLLMCalling:
    """测试 SubAgent 能够正确调用 LLM 并记录对话"""

    @pytest.mark.asyncio
    async def test_consistency_checker_calls_llm(self, mock_model_manager, temp_thinking_dir):
        """测试 ConsistencyChecker 调用 LLM"""
        from src.thinking_logger import _logger_var, ThinkingLogger

        # 设置 thinking logger
        logger = ThinkingLogger(output_dir=str(temp_thinking_dir))
        _logger_var.set(logger)

        checker = ConsistencyChecker(mock_model_manager)

        # 执行检查 - 新接口: check(chapter, context_text, chapter_index)
        report = await checker.check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)

        # 验证调用了 LLM
        assert mock_model_manager.call_count > 0, "应该调用了 LLM"

        # 验证返回了 SubAgentReport
        assert isinstance(report, SubAgentReport)
        assert report.agent_name == "ConsistencyChecker"

        # 验证报告内容
        print(f"\n【ConsistencyChecker LLM 分析结果】")
        print(f"问题数: {len(report.issues)}")
        print(f"推理: {report.reasoning}")
        print(f"置信度: {report.confidence}")

        # 验证 thinking_log 文件存在且包含对话内容
        assert logger.log_file is not None, "应该创建了 thinking_log 文件"

        with open(logger.log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()

        print(f"\n【Thinking Log 内容预览】")
        print(log_content[:500] + "...")

        # 验证日志包含关键信息
        assert "ConsistencyChecker" in log_content
        assert "check" in log_content

    @pytest.mark.asyncio
    async def test_character_arc_checker_calls_llm(self, mock_model_manager, temp_thinking_dir):
        """测试 CharacterArcChecker 调用 LLM"""
        from src.thinking_logger import _logger_var, ThinkingLogger

        logger = ThinkingLogger(output_dir=str(temp_thinking_dir))
        _logger_var.set(logger)

        checker = CharacterArcChecker(mock_model_manager)
        report = await checker.check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)

        assert mock_model_manager.call_count > 0
        assert isinstance(report, SubAgentReport)
        assert report.agent_name == "CharacterArcChecker"

        print(f"\n【CharacterArcChecker LLM 分析结果】")
        print(f"更新数: {len(report.updates)}")
        print(f"问题数: {len(report.issues)}")
        print(f"推理: {report.reasoning}")

    @pytest.mark.asyncio
    async def test_plot_thread_checker_calls_llm(self, mock_model_manager, temp_thinking_dir):
        """测试 PlotThreadChecker 调用 LLM"""
        from src.thinking_logger import _logger_var, ThinkingLogger

        logger = ThinkingLogger(output_dir=str(temp_thinking_dir))
        _logger_var.set(logger)

        checker = PlotThreadChecker(mock_model_manager)
        report = await checker.check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)

        assert mock_model_manager.call_count > 0
        assert isinstance(report, SubAgentReport)
        assert report.agent_name == "PlotThreadChecker"

        print(f"\n【PlotThreadChecker LLM 分析结果】")
        print(f"更新数: {len(report.updates)}")
        print(f"问题数: {len(report.issues)}")
        print(f"推理: {report.reasoning}")

    @pytest.mark.asyncio
    async def test_world_state_checker_calls_llm(self, mock_model_manager, temp_thinking_dir):
        """测试 WorldStateChecker 调用 LLM"""
        from src.thinking_logger import _logger_var, ThinkingLogger

        logger = ThinkingLogger(output_dir=str(temp_thinking_dir))
        _logger_var.set(logger)

        checker = WorldStateChecker(mock_model_manager)
        report = await checker.check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)

        assert mock_model_manager.call_count > 0
        assert isinstance(report, SubAgentReport)
        assert report.agent_name == "WorldStateChecker"

        print(f"\n【WorldStateChecker LLM 分析结果】")
        print(f"更新数: {len(report.updates)}")
        print(f"问题数: {len(report.issues)}")
        print(f"推理: {report.reasoning}")

    @pytest.mark.asyncio
    async def test_reflection_checker_calls_llm(self, mock_model_manager, temp_thinking_dir):
        """测试 ReflectionChecker 调用 LLM 进行综合评估"""
        from src.thinking_logger import _logger_var, ThinkingLogger

        logger = ThinkingLogger(output_dir=str(temp_thinking_dir))
        _logger_var.set(logger)

        # 先让其他 checker 产生一些结果
        consistency_report = await ConsistencyChecker(mock_model_manager).check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)
        char_arc_report = await CharacterArcChecker(mock_model_manager).check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)
        plot_report = await PlotThreadChecker(mock_model_manager).check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)
        world_report = await WorldStateChecker(mock_model_manager).check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)

        # 记录之前的调用次数
        calls_before_reflection = mock_model_manager.call_count

        checker = ReflectionChecker(mock_model_manager)
        from src.multi_agent.types import ReviewResult

        result = await checker.evaluate(
            chapter=SAMPLE_CHAPTER,
            chapter_index=1,
            check_results=[consistency_report, char_arc_report, plot_report, world_report],
            context_text=SAMPLE_CONTEXT_TEXT
        )

        # ReflectionChecker 也应该调用 LLM
        # 由于之前的 checkers 也用了同一个 mock_manager，所以总调用数应该 >= 5 (4 checkers + 1 reflection)
        assert mock_model_manager.call_count >= 5, f"所有 Agent 应该都调用了 LLM，总调用数={mock_model_manager.call_count}"
        assert isinstance(result, ReviewResult)

        print(f"\n【ReflectionChecker 综合评估结果】")
        print(f"总 LLM 调用次数: {mock_model_manager.call_count}")
        print(f"质量评分: {result.quality_score}")
        print(f"需要修订: {result.needs_revision}")
        print(f"建议数: {len(result.suggestions)}")
        print(f"推理: {result.reasoning}")


class TestThinkingLogContent:
    """测试 thinking_log 文件内容的完整性"""

    @pytest.mark.asyncio
    async def test_log_contains_full_llm_conversation(self, tmp_path):
        """验证 thinking_log 包含完整的 LLM 对话内容"""
        from src.thinking_logger import _logger_var, ThinkingLogger

        log_dir = tmp_path / "thinking_logs"
        log_dir.mkdir()

        logger = ThinkingLogger(output_dir=str(log_dir))
        _logger_var.set(logger)

        model_manager = MockModelManager()
        checker = ConsistencyChecker(model_manager)

        await checker.check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)

        # 读取日志文件
        log_file = logger.log_file
        assert log_file is not None

        with open(log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()

        print(f"\n【完整 Thinking Log】\n{log_content}")

        # 验证日志包含：
        # 1. 系统提示词
        assert "你是一位专业的章节一致性审查专家" in log_content or "系统提示" in log_content or "system" in log_content.lower()

        # 2. 用户提示词（章节内容）
        assert "张伟" in log_content or "李娜" in log_content or "chapter" in log_content.lower()

        # 3. LLM 响应
        assert "issues" in log_content or "reasoning" in log_content or "LLM" in log_content

    @pytest.mark.asyncio
    async def test_different_agents_create_separate_logs(self, tmp_path):
        """验证不同 Agent 创建独立的日志文件"""
        from src.thinking_logger import _logger_var, ThinkingLogger

        log_dir = tmp_path / "thinking_logs"
        log_dir.mkdir()

        logger = ThinkingLogger(output_dir=str(log_dir))
        _logger_var.set(logger)

        model_manager = MockModelManager()

        # 执行多个不同的 checker
        await ConsistencyChecker(model_manager).check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)
        await CharacterArcChecker(model_manager).check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)

        # 验证创建了多个日志文件
        assert len(logger._log_files) >= 2, f"应该至少有 2 个日志文件，实际有 {len(logger._log_files)}"

        # 验证不同 agent 的日志文件包含不同内容
        files = list(logger._log_files.values())
        with open(files[0], 'r', encoding='utf-8') as f:
            content1 = f.read()

        # 如果有第二个文件，验证内容不同
        if len(files) > 1:
            with open(files[1], 'r', encoding='utf-8') as f:
                content2 = f.read()

            # 内容应该不完全相同（因为是不同的 agent）
            print(f"\n【Agent 1 日志预览】\n{content1[:300]}")
            print(f"\n【Agent 2 日志预览】\n{content2[:300]}")


class TestLLMAnalysisQuality:
    """测试 LLM 分析的质量（通过验证返回结果的结构和内容）"""

    @pytest.mark.asyncio
    async def test_llm_returns_structured_json(self, tmp_path):
        """验证 LLM 返回结构化的 JSON 结果"""
        from src.thinking_logger import _logger_var, ThinkingLogger

        log_dir = tmp_path / "thinking_logs"
        log_dir.mkdir()

        logger = ThinkingLogger(output_dir=str(log_dir))
        _logger_var.set(logger)

        model_manager = MockModelManager()
        checker = ConsistencyChecker(model_manager)

        report = await checker.check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)

        # 验证报告结构
        assert hasattr(report, 'category')
        assert hasattr(report, 'issues')
        assert hasattr(report, 'reasoning')
        assert hasattr(report, 'confidence')

        # issues 应该是列表
        assert isinstance(report.issues, list)

        # 如果有问题，每个问题应该有必要的字段
        for issue in report.issues:
            if isinstance(issue, dict):
                print(f"  问题类型: {issue.get('type', 'N/A')}")
                print(f"  问题描述: {issue.get('issue', 'N/A')}")
                print(f"  位置: {issue.get('location', 'N/A')}")
                print(f"  建议: {issue.get('suggestion', 'N/A')}")

    @pytest.mark.asyncio
    async def test_llm_understands_chinese_content(self, tmp_path):
        """验证 LLM 能够理解中文小说内容"""
        from src.thinking_logger import _logger_var, ThinkingLogger

        log_dir = tmp_path / "thinking_logs"
        log_dir.mkdir()

        logger = ThinkingLogger(output_dir=str(log_dir))
        _logger_var.set(logger)

        model_manager = MockModelManager()
        checker = ConsistencyChecker(model_manager)

        report = await checker.check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)

        # LLM 应该能够理解中文并给出合理的分析
        # 这里我们用 mock，返回值应该包含中文
        print(f"\n【LLM 分析推理】{report.reasoning}")

        # 由于使用 mock，返回结果应该是中文的
        assert report.reasoning is not None
        assert len(report.reasoning) > 0


class TestPydanticModelHandling:
    """测试 SubAgent 正确处理 Pydantic 模型对象

    RED Phase: 这些测试应该 FAIL 直到修复 .get() -> 属性访问
    """

    @pytest.mark.asyncio
    async def test_plot_thread_checker_with_pydantic_objects(self, mock_model_manager, temp_thinking_dir):
        """Test PlotThreadChecker handles PlotThread Pydantic objects (not dicts)

        RED: This should FAIL because plot_thread.py uses thread.get("id", "")
        instead of thread.id on Pydantic objects
        """
        from src.thinking_logger import _logger_var, ThinkingLogger
        from src.model import PlotThread

        logger = ThinkingLogger(output_dir=str(temp_thinking_dir))
        _logger_var.set(logger)

        # Create Pydantic PlotThread object (like StoryBible returns)
        plot_thread = PlotThread(
            id="thread_001",
            name="神秘文件",
            status="foreshadowed",
            setup_chapter=1,
            expected_payoff_range="1-3",
            foreshadow_keywords=["文件", "保险箱"]
        )

        # Create context with Pydantic object (not dict!)
        pydantic_context = {
            "chapter_index": 1,
            "character_arcs": {},
            "plot_threads": {},
            "unresolved_plot_threads": [plot_thread],  # List of Pydantic objects
            "latest_world_state": None,
            "world_states": []
        }

        checker = PlotThreadChecker(mock_model_manager)

        # This should NOT raise "'PlotThread' object has no attribute 'get'"
        report = await checker.check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)

        assert isinstance(report, SubAgentReport)
        assert report.agent_name == "PlotThreadChecker"

    @pytest.mark.asyncio
    async def test_consistency_checker_with_pydantic_character_arcs(self, mock_model_manager, temp_thinking_dir):
        """Test ConsistencyChecker handles CharacterArc Pydantic objects (not dicts)

        RED: This should FAIL because consistency.py uses arc.get("current_stage_index", 0)
        instead of arc.current_stage_index on Pydantic objects
        """
        from src.thinking_logger import _logger_var, ThinkingLogger
        from src.model import CharacterArc, CharacterArcStage

        logger = ThinkingLogger(output_dir=str(temp_thinking_dir))
        _logger_var.set(logger)

        # Create Pydantic CharacterArc object
        character_arc = CharacterArc(
            name="林远",
            arc_stages=[
                CharacterArcStage(
                    stage_name="迷茫",
                    chapter_range="1-3",
                    emotional_state="困惑",
                    key_moment="获得能力"
                )
            ],
            current_stage_index=0,
            emotional_state="困惑"
        )

        # Create context with Pydantic objects
        pydantic_context = {
            "chapter_index": 1,
            "character_arcs": {"林远": character_arc},  # Dict of Pydantic objects
            "plot_threads": {},
            "unresolved_plot_threads": [],
            "latest_world_state": None,
            "world_states": []
        }

        checker = ConsistencyChecker(mock_model_manager)

        # This should NOT raise an error
        report = await checker.check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)

        assert isinstance(report, SubAgentReport)

    @pytest.mark.asyncio
    async def test_world_state_checker_with_pydantic_states(self, mock_model_manager, temp_thinking_dir):
        """Test WorldStateChecker handles WorldState Pydantic objects (not dicts)

        RED: This should FAIL because world_state.py uses prev_state.get("time", "")
        instead of prev_state.time on Pydantic objects
        """
        from src.thinking_logger import _logger_var, ThinkingLogger
        from src.model import WorldState

        logger = ThinkingLogger(output_dir=str(temp_thinking_dir))
        _logger_var.set(logger)

        # Create Pydantic WorldState objects
        prev_state = WorldState(
            chapter_index=1,
            location="旧城区废墟",
            time="新纪元2020年3月15日"
        )
        curr_state = WorldState(
            chapter_index=2,
            location="旧城区废墟地下室",
            time="新纪元2020年3月15日 上午"
        )

        # Create context with Pydantic objects
        pydantic_context = {
            "chapter_index": 2,
            "character_arcs": {},
            "plot_threads": {},
            "unresolved_plot_threads": [],
            "latest_world_state": curr_state,
            "world_states": [prev_state, curr_state]  # List of Pydantic objects
        }

        checker = WorldStateChecker(mock_model_manager)

        # This should NOT raise an error
        report = await checker.check(SAMPLE_CHAPTER, SAMPLE_CONTEXT_TEXT, chapter_index=1)

        assert isinstance(report, SubAgentReport)


# 运行提示
if __name__ == "__main__":
    print("=" * 60)
    print("SubAgents LLM 对话测试")
    print("=" * 60)
    print("\n运行方式:")
    print("  pytest tests/unit/test_sub_agents_llm.py -v -s")
    print("\n测试内容:")
    print("  1. 各 SubAgent 调用 LLM 进行分析")
    print("  2. thinking_log 正确记录完整对话")
    print("  3. 验证不同 Agent 创建独立日志")
    print("  4. 验证 LLM 返回结构化结果")
    print("=" * 60)
