"""
Agent 插件系统单元测试
"""
import pytest
from unittest.mock import MagicMock

from src.agents.base import BaseAgent, AgentConfig
from src.agents.registry import AgentRegistry, register_agent
from src.agents.setup import register_builtin_agents


class MockAgent(BaseAgent):
    """测试用 Agent"""

    def __init__(self, model_manager=None, config=None):
        super().__init__(model_manager, config)
        self.call_count = 0

    def generate(self, *args, **kwargs):
        self.call_count += 1
        return "mock_response"

    async def async_generate(self, *args, **kwargs):
        self.call_count += 1
        return "mock_response"


class TestAgentConfig:
    """AgentConfig 测试"""

    def test_config_creation(self):
        config = AgentConfig(name="test", description="test agent")
        assert config.name == "test"
        assert config.description == "test agent"
        assert config.enabled is True

    def test_config_defaults(self):
        config = AgentConfig(name="minimal")
        assert config.name == "minimal"
        assert config.description == ""
        assert config.enabled is True


class TestAgentRegistry:
    """AgentRegistry 测试"""

    def setup_method(self):
        """每个测试前清空注册表"""
        AgentRegistry.clear()

    def test_register_agent(self):
        """测试注册 Agent"""
        AgentRegistry.register("test", MockAgent)
        assert AgentRegistry.is_registered("test")
        assert "test" in AgentRegistry.list_agents()

    def test_register_with_config(self):
        """测试带配置注册 Agent"""
        config = AgentConfig(name="test", description="test agent")
        AgentRegistry.register("test", MockAgent, config)
        retrieved_config = AgentRegistry.get_config("test")
        assert retrieved_config.name == "test"
        assert retrieved_config.description == "test agent"

    def test_register_invalid_class(self):
        """测试注册非 Agent 类"""
        with pytest.raises(TypeError, match="must inherit from BaseAgent"):
            AgentRegistry.register("invalid", object)

    def test_get_agent(self):
        """测试获取 Agent 实例"""
        AgentRegistry.register("test", MockAgent)
        agent = AgentRegistry.get("test", model_manager=None, config=None)
        assert isinstance(agent, MockAgent)
        assert agent.call_count == 0

    def test_get_agent_new_instance(self):
        """测试每次 get 返回新实例"""
        AgentRegistry.register("test", MockAgent)
        agent1 = AgentRegistry.get("test", model_manager=None, config=None)
        agent2 = AgentRegistry.get("test", model_manager=None, config=None)
        assert agent1 is not agent2

    def test_get_unregistered_agent(self):
        """测试获取未注册的 Agent"""
        with pytest.raises(KeyError, match="not registered"):
            AgentRegistry.get("nonexistent")

    def test_list_agents(self):
        """测试列出所有 Agent"""
        AgentRegistry.register("agent1", MockAgent)
        AgentRegistry.register("agent2", MockAgent)
        agents = AgentRegistry.list_agents()
        assert len(agents) == 2
        assert "agent1" in agents
        assert "agent2" in agents

    def test_clear(self):
        """测试清空注册表"""
        AgentRegistry.register("test", MockAgent)
        AgentRegistry.clear()
        assert not AgentRegistry.is_registered("test")
        assert len(AgentRegistry.list_agents()) == 0


class TestRegisterDecorator:
    """@register_agent 装饰器测试"""

    def setup_method(self):
        AgentRegistry.clear()

    def test_decorator_registers_agent(self):
        """测试装饰器注册 Agent"""
        @register_agent("decorated")
        class DecoratedAgent(MockAgent):
            pass

        assert AgentRegistry.is_registered("decorated")

    def test_decorator_with_config(self):
        """测试带配置的装饰器"""
        config = AgentConfig(name="decorated", description="decorated agent")

        @register_agent("decorated", config)
        class DecoratedAgent(MockAgent):
            pass

        retrieved_config = AgentRegistry.get_config("decorated")
        assert retrieved_config.description == "decorated agent"


class TestBuiltinAgents:
    """内置 Agent 注册测试"""

    def setup_method(self):
        AgentRegistry.clear()

    def test_register_builtin_agents(self):
        """测试注册内置 Agent"""
        register_builtin_agents()

        expected = ["outline", "character", "writer", "reflect", "entity"]
        for name in expected:
            assert AgentRegistry.is_registered(name), f"{name} should be registered"

    def test_builtin_agents_have_config(self):
        """测试内置 Agent 有配置"""
        register_builtin_agents()

        for name in ["outline", "character", "writer", "reflect", "entity"]:
            config = AgentRegistry.get_config(name)
            assert config is not None
            assert config.name == name
