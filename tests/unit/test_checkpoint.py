"""
Tests for StateManager checkpoint/resume functionality
"""
import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.core.state_manager import StateManager, WorkflowInfo
from src.core.progress import WorkflowStatus


@pytest.fixture
def temp_storage_dir():
    """Create a temporary storage directory for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def state_manager(temp_storage_dir):
    """Create a StateManager instance with temporary storage"""
    return StateManager(storage_dir=temp_storage_dir)


class TestCheckpointOperations:
    """Tests for checkpoint save/load operations"""

    def test_save_checkpoint_creates_file(self, state_manager, temp_storage_dir):
        """Test that save_checkpoint creates a checkpoint file"""
        workflow_id = "test_workflow_001"
        state_data = {
            "current_chapter_index": 3,
            "completed_chapters": [0, 1, 2],
            "current_node": "generate_chapter",
            "user_intent": "写一个科幻小说",
            "min_chapters": 10,
            "novel_title": "test_novel"
        }

        state_manager.save_checkpoint(workflow_id, state_data)

        # Verify checkpoint file exists
        checkpoint_path = Path(temp_storage_dir) / f"{workflow_id}_checkpoint.json"
        assert checkpoint_path.exists(), "Checkpoint file should exist"

    def test_save_checkpoint_contains_required_fields(self, state_manager, temp_storage_dir):
        """Test that checkpoint contains all required fields"""
        workflow_id = "test_workflow_002"
        state_data = {
            "current_chapter_index": 5,
            "completed_chapters": [0, 1, 2, 3, 4],
            "current_node": "validate_chapter",
            "user_intent": "武侠小说",
            "min_chapters": 20,
            "novel_title": "wuxia_novel"
        }

        state_manager.save_checkpoint(workflow_id, state_data)

        checkpoint_path = Path(temp_storage_dir) / f"{workflow_id}_checkpoint.json"
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify required fields exist
        assert data["workflow_id"] == workflow_id
        assert data["current_chapter_index"] == 5
        assert data["completed_chapters"] == [0, 1, 2, 3, 4]
        assert data["current_node"] == "validate_chapter"
        assert data["user_intent"] == "武侠小说"
        assert "saved_at" in data

    def test_load_checkpoint_returns_data(self, state_manager, temp_storage_dir):
        """Test that load_checkpoint returns the saved data"""
        workflow_id = "test_workflow_003"
        state_data = {
            "current_chapter_index": 7,
            "completed_chapters": [0, 1, 2, 3, 4, 5, 6],
            "current_node": "quality_check",
            "user_intent": "爱情小说",
            "min_chapters": 15
        }

        state_manager.save_checkpoint(workflow_id, state_data)
        loaded = state_manager.load_checkpoint(workflow_id)

        assert loaded is not None
        assert loaded["current_chapter_index"] == 7
        assert loaded["completed_chapters"] == [0, 1, 2, 3, 4, 5, 6]
        assert loaded["current_node"] == "quality_check"

    def test_load_checkpoint_returns_none_for_nonexistent(self, state_manager):
        """Test that load_checkpoint returns None for nonexistent workflow"""
        result = state_manager.load_checkpoint("nonexistent_workflow")
        assert result is None

    def test_has_checkpoint_returns_true_when_exists(self, state_manager, temp_storage_dir):
        """Test that has_checkpoint returns True when checkpoint exists"""
        workflow_id = "test_workflow_004"
        state_data = {"current_chapter_index": 1}

        state_manager.save_checkpoint(workflow_id, state_data)

        assert state_manager.has_checkpoint(workflow_id) is True

    def test_has_checkpoint_returns_false_when_not_exists(self, state_manager):
        """Test that has_checkpoint returns False when checkpoint does not exist"""
        result = state_manager.has_checkpoint("nonexistent_workflow")
        assert result is False

    def test_clear_checkpoint_removes_file(self, state_manager, temp_storage_dir):
        """Test that clear_checkpoint removes the checkpoint file"""
        workflow_id = "test_workflow_005"
        state_data = {"current_chapter_index": 2}

        state_manager.save_checkpoint(workflow_id, state_data)
        assert state_manager.has_checkpoint(workflow_id) is True

        result = state_manager.clear_checkpoint(workflow_id)

        assert result is True
        assert state_manager.has_checkpoint(workflow_id) is False

    def test_clear_checkpoint_returns_false_when_not_exists(self, state_manager):
        """Test that clear_checkpoint returns False when checkpoint doesn't exist"""
        result = state_manager.clear_checkpoint("nonexistent_workflow")
        assert result is False

    def test_save_checkpoint_with_empty_completed_chapters(self, state_manager, temp_storage_dir):
        """Test checkpoint save with no completed chapters"""
        workflow_id = "test_workflow_006"
        state_data = {
            "current_chapter_index": 0,
            "completed_chapters": [],
            "current_node": "start",
            "user_intent": "测试",
            "min_chapters": 10
        }

        state_manager.save_checkpoint(workflow_id, state_data)

        loaded = state_manager.load_checkpoint(workflow_id)
        assert loaded is not None
        assert loaded["completed_chapters"] == []
        assert loaded["current_chapter_index"] == 0

    def test_save_checkpoint_handles_none_values(self, state_manager, temp_storage_dir):
        """Test checkpoint save handles None values correctly"""
        workflow_id = "test_workflow_007"
        state_data = {
            "current_chapter_index": 1,
            "completed_chapters": None,
            "current_node": None,
            "user_intent": "测试",
            "min_chapters": 10
        }

        state_manager.save_checkpoint(workflow_id, state_data)

        loaded = state_manager.load_checkpoint(workflow_id)
        assert loaded is not None
        # None values should be handled gracefully


class TestGetInterruptedWorkflows:
    """Tests for get_interrupted_workflows method"""

    def test_get_interrupted_workflows_returns_list(self, state_manager, temp_storage_dir):
        """Test that get_interrupted_workflows returns a list of workflows"""
        # Create a checkpoint
        workflow_id = "interrupted_workflow_001"
        state_data = {
            "current_chapter_index": 5,
            "completed_chapters": [0, 1, 2, 3, 4],
            "current_node": "generate_chapter",
            "user_intent": "测试中断工作流",
            "min_chapters": 10
        }
        state_manager.save_checkpoint(workflow_id, state_data)

        # Also create workflow state file
        workflow_state = {
            "_created_at": datetime.now().isoformat(),
            "_saved_at": datetime.now().isoformat(),
            "user_intent": "测试中断工作流",
            "status": "running",
            "progress": 0.5
        }
        state_manager.save_state(workflow_id, workflow_state)

        interrupted = state_manager.get_interrupted_workflows()

        assert isinstance(interrupted, list)
        assert len(interrupted) >= 1

        # Find our workflow
        found = any(w.workflow_id == workflow_id for w in interrupted)
        assert found, "Created interrupted workflow should be in list"

    def test_get_interrupted_workflows_empty_when_no_checkpoints(self, state_manager):
        """Test that get_interrupted_workflows returns empty list when no checkpoints"""
        result = state_manager.get_interrupted_workflows()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_interrupted_workflows_returns_workflow_info(self, state_manager, temp_storage_dir):
        """Test that returned items are WorkflowInfo objects with correct data"""
        workflow_id = "interrupted_workflow_002"
        state_data = {
            "current_chapter_index": 3,
            "completed_chapters": [0, 1, 2],
            "current_node": "validate_outline",
            "user_intent": "另一个测试",
            "min_chapters": 15
        }
        state_manager.save_checkpoint(workflow_id, state_data)

        workflow_state = {
            "_created_at": datetime.now().isoformat(),
            "_saved_at": datetime.now().isoformat(),
            "user_intent": "另一个测试",
            "status": "running",
            "progress": 0.3
        }
        state_manager.save_state(workflow_id, workflow_state)

        interrupted = state_manager.get_interrupted_workflows()

        # Should have at least our workflow
        our_workflow = next((w for w in interrupted if w.workflow_id == workflow_id), None)
        assert our_workflow is not None
        assert isinstance(our_workflow, WorkflowInfo)
        assert our_workflow.user_intent == "另一个测试"
        assert our_workflow.current_node == "validate_outline"


class TestCheckpointEdgeCases:
    """Tests for edge cases in checkpoint handling"""

    def test_save_checkpoint_overwrites_existing(self, state_manager, temp_storage_dir):
        """Test that saving checkpoint overwrites existing one"""
        workflow_id = "overwrite_test"

        state_data_v1 = {
            "current_chapter_index": 1,
            "completed_chapters": [],
            "current_node": "node_v1"
        }
        state_manager.save_checkpoint(workflow_id, state_data_v1)

        state_data_v2 = {
            "current_chapter_index": 5,
            "completed_chapters": [0, 1, 2, 3, 4],
            "current_node": "node_v2"
        }
        state_manager.save_checkpoint(workflow_id, state_data_v2)

        loaded = state_manager.load_checkpoint(workflow_id)
        assert loaded["current_chapter_index"] == 5
        assert loaded["current_node"] == "node_v2"
        assert loaded["completed_chapters"] == [0, 1, 2, 3, 4]

    def test_checkpoint_file_is_valid_json(self, state_manager, temp_storage_dir):
        """Test that checkpoint file contains valid JSON"""
        workflow_id = "json_test"
        state_data = {"current_chapter_index": 1, "user_intent": "测试"}

        state_manager.save_checkpoint(workflow_id, state_data)

        checkpoint_path = Path(temp_storage_dir) / f"{workflow_id}_checkpoint.json"
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, dict)
        assert "workflow_id" in data

    def test_concurrent_save_checkpoint(self, state_manager, temp_storage_dir):
        """Test that concurrent checkpoint saves work correctly"""
        import threading

        workflow_ids = [f"concurrent_test_{i}" for i in range(5)]
        results = []

        def save_checkpoint(wf_id):
            state_data = {
                "current_chapter_index": 1,
                "completed_chapters": [],
                "current_node": f"node_{wf_id}"
            }
            state_manager.save_checkpoint(wf_id, state_data)
            results.append(wf_id)

        threads = [threading.Thread(target=save_checkpoint, args=(wf_id,)) for wf_id in workflow_ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All saves should complete without error
        assert len(results) == 5

        # All checkpoints should exist
        for wf_id in workflow_ids:
            assert state_manager.has_checkpoint(wf_id)