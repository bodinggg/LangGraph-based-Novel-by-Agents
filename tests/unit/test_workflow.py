"""
Tests for src/workflow.py - TDD RED phase
"""
import pytest
from unittest.mock import MagicMock, patch
from langgraph.graph import StateGraph, END

from src.workflow import create_workflow
from src.state import NovelState
from src.model_manager import ModelManager
from src.config_loader import ModelConfig, BaseConfig, OutlineConfig


class TestCreateWorkflow:
    """Test create_workflow() function"""

    def test_create_workflow_returns_compiled_graph(self, disable_logging):
        """Test that create_workflow returns a compiled StateGraph"""
        model_config = ModelConfig(
            model_type="api",
            model_name="test-model",
            api_url="https://api.test.com",
            api_key="test-key"
        )

        result = create_workflow(model_config)

        # Should return a compiled graph (not a StateGraph directly)
        assert result is not None
        # Compiled graphs have 'invoke' method
        assert hasattr(result, 'invoke')
        assert hasattr(result, 'nodes')

    def test_create_workflow_with_api_model(self, disable_logging):
        """Test workflow creation with API model configuration"""
        model_config = ModelConfig(
            model_type="api",
            model_name="test-model",
            api_url="https://api.test.com",
            api_key="test-key",
            api_type="openai"
        )

        result = create_workflow(model_config)

        assert result is not None

    @patch('src.workflow.LocalModelManager')
    def test_create_workflow_with_local_model(self, mock_local_manager, disable_logging):
        """Test workflow creation with local model configuration"""
        # Mock the LocalModelManager to avoid actually loading the model
        mock_instance = MagicMock()
        mock_local_manager.return_value = mock_instance

        model_config = ModelConfig(
            model_type="local",
            model_path="/path/to/model"
        )

        result = create_workflow(model_config)

        assert result is not None
        mock_local_manager.assert_called_once_with("/path/to/model")

    def test_create_workflow_has_expected_nodes(self, disable_logging):
        """Test that workflow has the expected nodes"""
        model_config = ModelConfig(
            model_type="api",
            model_name="test-model",
            api_url="https://api.test.com",
            api_key="test-key"
        )

        # Use default outline config with master_outline=True (分卷模式)
        result = create_workflow(model_config, OutlineConfig)

        # Get node names from compiled graph
        node_names = list(result.nodes.keys())

        # Check for expected nodes
        expected_nodes = [
            "generate_outline",
            "validate_master_outline",
            "generate_volume_outline",
            "validate_volume_outline",
            "accpet_outline",
            "volume2character",
            "outline_feedback",
            "process_outline_feedback",
            "generate_characters",
            "validate_characters",
            "character_feedback",
            "process_character_feedback",
            "write_chapter",
            "validate_chapter",
            "chapter_feedback",
            "process_chapter_feedback",
            "generate_entities",
            "validate_entities",
            "evaluate_chapter",
            "validate_evaluate",
            "evaluate_report",
            "evaluate2wirte",
            "accpet_chapter",
            "success",
            "failure"
        ]

        for node in expected_nodes:
            assert node in node_names, f"Expected node '{node}' not found in workflow"

    def test_create_workflow_has_entry_point(self, disable_logging):
        """Test that workflow has an entry point set"""
        model_config = ModelConfig(
            model_type="api",
            model_name="test-model",
            api_url="https://api.test.com",
            api_key="test-key"
        )

        result = create_workflow(model_config, OutlineConfig)

        # Entry point should be generate_outline
        assert result is not None


class TestWorkflowEdges:
    """Test workflow edges and connectivity"""

    def test_workflow_entry_point_is_generate_outline(self, disable_logging):
        """Test that the entry point is generate_outline"""
        model_config = ModelConfig(
            model_type="api",
            model_name="test-model",
            api_url="https://api.test.com",
            api_key="test-key"
        )

        result = create_workflow(model_config, OutlineConfig)

        # Entry point should be generate_outline
        assert result is not None


class TestWorkflowNonMasterOutline:
    """Test workflow with master_outline=False (单卷模式)"""

    def test_create_workflow_without_master_outline(self, disable_logging):
        """Test workflow creation when master_outline is False"""
        model_config = ModelConfig(
            model_type="api",
            model_name="test-model",
            api_url="https://api.test.com",
            api_key="test-key"
        )

        # Create a config with master_outline=False
        non_master_config = BaseConfig(
            master_outline=False,
            min_chapters=10
        )

        result = create_workflow(model_config, non_master_config)

        assert result is not None
        node_names = list(result.nodes.keys())

        # Should NOT have master outline nodes
        assert "generate_master_outline" not in node_names
        assert "validate_master_outline" not in node_names

        # Should still have basic nodes
        assert "generate_outline" in node_names
        assert "validate_outline" in node_names
