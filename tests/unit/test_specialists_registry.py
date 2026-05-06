"""
Tests for Specialist Agents Registry Registration (new WritingSupervisor architecture)

Tests:
1. register_specialist_agents() logs registration for each specialist
2. WritingSupervisor is initialized with all SubAgents
3. SubAgents can be accessed from WritingSupervisor
"""

import pytest
from unittest.mock import MagicMock, patch
from src.agents.registry import AgentRegistry


class TestSpecialistAgentsRegistryRegistration:
    """Tests for Specialist agents registration"""

    def test_register_specialist_agents_logs_consistency_agent(self):
        """register_specialist_agents() should log ConsistencyChecker registration"""
        with patch('src.agents.setup.logger') as mock_logger:
            from src.agents.setup import register_specialist_agents

            AgentRegistry.clear()
            register_specialist_agents()

            # Check that log contains consistency agent registration
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("consistency" in log for log in log_calls), f"Expected consistency agent log, got: {log_calls}"

    def test_register_specialist_agents_logs_all_four_specialists(self):
        """register_specialist_agents() should log all 4 specialist agents"""
        with patch('src.agents.setup.logger') as mock_logger:
            from src.agents.setup import register_specialist_agents

            AgentRegistry.clear()
            register_specialist_agents()

            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            all_logs = " ".join(log_calls)

            # New architecture has 4 SubAgents, not 5
            specialist_names = ["consistency", "character_arc", "plot_thread", "world_state"]
            for name in specialist_names:
                assert name in all_logs.lower(), f"Expected {name} in logs, got: {all_logs}"

    def test_writing_supervisor_has_all_check_agents(self):
        """WritingSupervisor should have all 4 check agents initialized"""
        from src.multi_agent import WritingSupervisor

        mock_manager = MagicMock()
        supervisor = WritingSupervisor(mock_manager)

        assert len(supervisor.check_agents) == 4
        agent_names = [agent.agent_name for agent in supervisor.check_agents]
        assert "ConsistencyChecker" in agent_names
        assert "CharacterArcChecker" in agent_names
        assert "PlotThreadChecker" in agent_names
        assert "WorldStateChecker" in agent_names

    def test_specialist_agents_not_registered_as_main_agents(self):
        """Specialist agents should NOT be registered in main AgentRegistry (they use separate system)"""
        from src.agents.setup import register_builtin_agents, register_specialist_agents

        AgentRegistry.clear()
        register_builtin_agents()

        # Main agents should be registered
        assert AgentRegistry.is_registered("outline")
        assert AgentRegistry.is_registered("character")
        assert AgentRegistry.is_registered("writer")
        assert AgentRegistry.is_registered("reflect")
        assert AgentRegistry.is_registered("entity")

        # Verify consistency agent is NOT in main registry (specialists use separate system)
        # This is intentional - specialists don't inherit from BaseAgent
        assert not AgentRegistry.is_registered("consistency")
        assert not AgentRegistry.is_registered("character_arc")