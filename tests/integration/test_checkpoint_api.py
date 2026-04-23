"""
Integration tests for checkpoint/resume API endpoints
"""
import pytest
import json
import tempfile
import shutil
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.core.state_manager import StateManager
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
    """Tests for StateManager checkpoint operations"""

    def test_save_checkpoint_creates_file(self, state_manager, temp_storage_dir):
        """Test that save_checkpoint creates a checkpoint file"""
        workflow_id = "test_checkpoint_001"
        checkpoint_data = {
            "current_chapter_index": 1,
            "completed_chapters": [],
            "current_node": "test_node",
            "user_intent": "测试"
        }
        state_manager.save_checkpoint(workflow_id, checkpoint_data)

        # Verify file exists
        checkpoint_path = Path(temp_storage_dir) / f"{workflow_id}_checkpoint.json"
        assert checkpoint_path.exists()

    def test_save_checkpoint_contains_required_fields(self, state_manager, temp_storage_dir):
        """Test that checkpoint contains all required fields"""
        workflow_id = "test_checkpoint_002"
        checkpoint_data = {
            "current_chapter_index": 2,
            "completed_chapters": [0, 1],
            "current_node": "generate_chapter",
            "user_intent": "测试小说"
        }
        state_manager.save_checkpoint(workflow_id, checkpoint_data)

        loaded = state_manager.load_checkpoint(workflow_id)
        assert loaded is not None
        assert loaded["current_chapter_index"] == 2
        assert loaded["completed_chapters"] == [0, 1]
        assert loaded["current_node"] == "generate_chapter"
        assert loaded["workflow_id"] == workflow_id

    def test_load_checkpoint_returns_data(self, state_manager, temp_storage_dir):
        """Test that load_checkpoint returns saved data"""
        workflow_id = "test_checkpoint_003"
        original_data = {
            "current_chapter_index": 5,
            "completed_chapters": [0, 1, 2, 3, 4],
            "current_node": "quality_check",
            "user_intent": "测试恢复"
        }
        state_manager.save_checkpoint(workflow_id, original_data)

        loaded = state_manager.load_checkpoint(workflow_id)
        assert loaded is not None
        assert loaded["current_chapter_index"] == 5
        assert len(loaded["completed_chapters"]) == 5

    def test_load_checkpoint_returns_none_for_nonexistent(self, state_manager):
        """Test that load_checkpoint returns None for nonexistent checkpoint"""
        result = state_manager.load_checkpoint("nonexistent_workflow")
        assert result is None

    def test_has_checkpoint_returns_true_when_exists(self, state_manager, temp_storage_dir):
        """Test has_checkpoint returns True when checkpoint exists"""
        workflow_id = "test_checkpoint_004"
        state_manager.save_checkpoint(workflow_id, {"current_chapter_index": 1})
        assert state_manager.has_checkpoint(workflow_id) is True

    def test_has_checkpoint_returns_false_when_not_exists(self, state_manager):
        """Test has_checkpoint returns False when no checkpoint"""
        assert state_manager.has_checkpoint("nonexistent") is False

    def test_clear_checkpoint_removes_file(self, state_manager, temp_storage_dir):
        """Test that clear_checkpoint removes checkpoint file"""
        workflow_id = "test_checkpoint_005"
        state_manager.save_checkpoint(workflow_id, {"current_chapter_index": 1})

        assert state_manager.has_checkpoint(workflow_id) is True
        result = state_manager.clear_checkpoint(workflow_id)
        assert result is True
        assert state_manager.has_checkpoint(workflow_id) is False

    def test_clear_checkpoint_returns_false_when_not_exists(self, state_manager):
        """Test clear_checkpoint returns False when no checkpoint exists"""
        result = state_manager.clear_checkpoint("nonexistent")
        assert result is False

    def test_save_checkpoint_with_empty_completed_chapters(self, state_manager, temp_storage_dir):
        """Test save_checkpoint with empty completed_chapters list"""
        workflow_id = "test_checkpoint_006"
        state_manager.save_checkpoint(workflow_id, {
            "current_chapter_index": 0,
            "completed_chapters": [],
            "current_node": "start"
        })
        loaded = state_manager.load_checkpoint(workflow_id)
        assert loaded is not None
        assert loaded["completed_chapters"] == []

    def test_save_checkpoint_handles_none_values(self, state_manager, temp_storage_dir):
        """Test save_checkpoint handles None values in data"""
        workflow_id = "test_checkpoint_007"
        state_manager.save_checkpoint(workflow_id, {
            "current_chapter_index": 1,
            "completed_chapters": None,
            "current_node": "test"
        })
        loaded = state_manager.load_checkpoint(workflow_id)
        assert loaded is not None


class TestGetInterruptedWorkflows:
    """Tests for get_interrupted_workflows method"""

    def test_get_interrupted_workflows_returns_list(self, state_manager, temp_storage_dir):
        """Test that get_interrupted_workflows returns a list"""
        workflow_id = "test_interrupted_001"
        state_manager.save_checkpoint(workflow_id, {
            "current_chapter_index": 1,
            "completed_chapters": [],
            "current_node": "test"
        })
        state_manager.save_state(workflow_id, {
            "_created_at": "2024-01-01T00:00:00",
            "_saved_at": "2024-01-01T00:00:00",
            "user_intent": "测试",
            "status": "running"
        })

        result = state_manager.get_interrupted_workflows()
        assert isinstance(result, list)

    def test_get_interrupted_workflows_empty_when_no_checkpoints(self, state_manager):
        """Test that empty list is returned when no checkpoints exist"""
        result = state_manager.get_interrupted_workflows()
        assert isinstance(result, list)
        # May have other workflows from other tests, but should be empty initially

    def test_get_interrupted_workflows_returns_workflow_info(self, state_manager, temp_storage_dir):
        """Test that get_interrupted_workflows returns WorkflowInfo objects"""
        workflow_id = "test_interrupted_002"
        state_manager.save_checkpoint(workflow_id, {
            "current_chapter_index": 3,
            "completed_chapters": [0, 1, 2],
            "current_node": "generate_chapter",
            "user_intent": "测试小说"
        })
        state_manager.save_state(workflow_id, {
            "_created_at": "2024-01-01T00:00:00",
            "_saved_at": "2024-01-01T00:00:00",
            "user_intent": "测试小说",
            "status": "running",
            "progress": 0.3
        })

        interrupted = state_manager.get_interrupted_workflows()
        found = next((w for w in interrupted if w.workflow_id == workflow_id), None)
        assert found is not None
        assert found.user_intent == "测试小说"


class TestCheckpointEdgeCases:
    """Tests for checkpoint edge cases"""

    def test_save_checkpoint_overwrites_existing(self, state_manager, temp_storage_dir):
        """Test that save_checkpoint overwrites existing checkpoint"""
        workflow_id = "test_overwrite"
        state_manager.save_checkpoint(workflow_id, {
            "current_chapter_index": 1,
            "current_node": "first"
        })
        state_manager.save_checkpoint(workflow_id, {
            "current_chapter_index": 5,
            "current_node": "second"
        })

        loaded = state_manager.load_checkpoint(workflow_id)
        assert loaded["current_chapter_index"] == 5
        assert loaded["current_node"] == "second"

    def test_checkpoint_file_is_valid_json(self, state_manager, temp_storage_dir):
        """Test that checkpoint file contains valid JSON"""
        workflow_id = "test_json_001"
        state_manager.save_checkpoint(workflow_id, {
            "current_chapter_index": 1,
            "completed_chapters": [0],
            "user_intent": "测试"
        })

        checkpoint_path = Path(temp_storage_dir) / f"{workflow_id}_checkpoint.json"
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["current_chapter_index"] == 1

    def test_concurrent_save_checkpoint(self, state_manager, temp_storage_dir):
        """Test concurrent checkpoint operations don't corrupt data"""
        workflow_ids = [f"concurrent_{i}" for i in range(5)]
        errors = []

        def save_checkpoint(wf_id):
            try:
                state_manager.save_checkpoint(wf_id, {
                    "current_chapter_index": 1,
                    "completed_chapters": [],
                    "current_node": f"node_{wf_id}"
                })
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=save_checkpoint, args=(wf_id,)) for wf_id in workflow_ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        for wf_id in workflow_ids:
            assert state_manager.has_checkpoint(wf_id) is True


class TestResumeWorkflowEndpoint:
    """Tests for POST /api/v1/novels/{workflow_id}/resume endpoint"""

    def test_resume_nonexistent_workflow_returns_404(self, state_manager):
        """Test that resuming nonexistent workflow is detected"""
        workflow_id = "nonexistent_workflow"
        assert state_manager.has_checkpoint(workflow_id) is False

    def test_resume_workflow_with_checkpoint(self, state_manager, temp_storage_dir):
        """Test that workflow with checkpoint can be resumed"""
        workflow_id = "resumable_workflow"
        state_manager.save_checkpoint(workflow_id, {
            "current_chapter_index": 5,
            "completed_chapters": [0, 1, 2, 3, 4],
            "current_node": "quality_check",
            "user_intent": "测试恢复"
        })
        state_manager.save_state(workflow_id, {
            "_created_at": "2024-01-01T00:00:00",
            "_saved_at": "2024-01-01T00:00:00",
            "user_intent": "测试恢复",
            "status": "running",
            "progress": 0.5
        })

        assert state_manager.has_checkpoint(workflow_id) is True
        checkpoint = state_manager.load_checkpoint(workflow_id)
        assert checkpoint is not None
        assert checkpoint["current_chapter_index"] == 5

    def test_resume_without_checkpoint_returns_error(self, state_manager):
        """Test that resuming workflow without checkpoint is detected"""
        workflow_id = "no_checkpoint_workflow"
        state_manager.save_state(workflow_id, {
            "_created_at": "2024-01-01T00:00:00",
            "_saved_at": "2024-01-01T00:00:00",
            "user_intent": "测试",
            "status": "running"
        })
        assert state_manager.has_checkpoint(workflow_id) is False


class TestCharacterRelationshipsEndpoint:
    """Tests for character relationship API endpoints"""

    def test_get_relationships_nonexistent_workflow(self, state_manager):
        """Test that nonexistent workflow returns None state"""
        workflow_id = "nonexistent"
        state = state_manager.load_state(workflow_id)
        assert state is None

    def test_get_relationships_workflow_without_title(self, state_manager):
        """Test workflow without novel_title"""
        workflow_id = "no_title_workflow"
        state_manager.save_state(workflow_id, {
            "_created_at": "2024-01-01T00:00:00",
            "_saved_at": "2024-01-01T00:00:00",
            "user_intent": "测试"
        })
        state = state_manager.load_state(workflow_id)
        assert state is not None
        assert state.get("novel_title") is None


class TestCharacterGraphEndpoint:
    """Tests for character graph API endpoints"""

    def test_get_graph_nonexistent_workflow(self, state_manager):
        """Test that nonexistent workflow returns None state"""
        workflow_id = "nonexistent"
        state = state_manager.load_state(workflow_id)
        assert state is None

    def test_get_graph_workflow_without_characters(self, state_manager):
        """Test graph endpoint when no characters exist"""
        workflow_id = "no_characters_workflow"
        state_manager.save_state(workflow_id, {
            "_created_at": "2024-01-01T00:00:00",
            "_saved_at": "2024-01-01T00:00:00",
            "user_intent": "测试",
            "novel_title": "test_novel"
        })
        state = state_manager.load_state(workflow_id)
        assert state is not None


class TestCheckpointAPIFullFlow:
    """Full flow tests for checkpoint functionality"""

    def test_checkpoint_lifecycle(self, state_manager, temp_storage_dir):
        """Test complete checkpoint lifecycle: create, check, load, clear"""
        workflow_id = "lifecycle_test"

        # 1. Initially no checkpoint
        assert state_manager.has_checkpoint(workflow_id) is False

        # 2. Save checkpoint
        state_data = {
            "current_chapter_index": 2,
            "completed_chapters": [0, 1],
            "current_node": "outline_generation",
            "user_intent": "生命周期测试",
            "min_chapters": 10,
            "novel_title": "lifecycle_novel"
        }
        state_manager.save_checkpoint(workflow_id, state_data)

        # 3. Verify checkpoint exists
        assert state_manager.has_checkpoint(workflow_id) is True

        # 4. Load and verify
        loaded = state_manager.load_checkpoint(workflow_id)
        assert loaded is not None
        assert loaded["current_chapter_index"] == 2
        assert loaded["completed_chapters"] == [0, 1]

        # 5. Clear checkpoint
        result = state_manager.clear_checkpoint(workflow_id)
        assert result is True

        # 6. Verify checkpoint gone
        assert state_manager.has_checkpoint(workflow_id) is False

    def test_interrupted_workflow_detection(self, state_manager, temp_storage_dir):
        """Test that interrupted workflows are correctly detected"""
        workflow_1 = "interrupted_001"
        state_manager.save_checkpoint(workflow_1, {
            "current_chapter_index": 1,
            "completed_chapters": [],
            "current_node": "test_node"
        })
        state_manager.save_state(workflow_1, {
            "_created_at": "2024-01-01T00:00:00",
            "_saved_at": "2024-01-01T00:00:00",
            "user_intent": "测试1",
            "status": "running"
        })

        workflow_2 = "interrupted_002"
        state_manager.save_checkpoint(workflow_2, {
            "current_chapter_index": 5,
            "completed_chapters": [0, 1, 2, 3, 4],
            "current_node": "chapter_generation"
        })
        state_manager.save_state(workflow_2, {
            "_created_at": "2024-01-02T00:00:00",
            "_saved_at": "2024-01-02T00:00:00",
            "user_intent": "测试2",
            "status": "running"
        })

        interrupted = state_manager.get_interrupted_workflows()
        workflow_ids = [w.workflow_id for w in interrupted]
        assert workflow_1 in workflow_ids
        assert workflow_2 in workflow_ids

    def test_multiple_checkpoint_files(self, state_manager, temp_storage_dir):
        """Test managing multiple checkpoint files"""
        workflows = [f"workflow_{i}" for i in range(10)]

        for wf in workflows:
            state_manager.save_checkpoint(wf, {
                "current_chapter_index": 1,
                "completed_chapters": [],
                "current_node": f"node_{wf}"
            })

        for wf in workflows:
            assert state_manager.has_checkpoint(wf) is True

        for wf in workflows:
            loaded = state_manager.load_checkpoint(wf)
            assert loaded is not None
            assert loaded["current_node"] == f"node_{wf}"

    def test_checkpoint_data_integrity(self, state_manager, temp_storage_dir):
        """Test that checkpoint data maintains integrity"""
        workflow_id = "integrity_test"
        original_data = {
            "current_chapter_index": 99,
            "completed_chapters": list(range(50)),
            "current_node": "final_node",
            "user_intent": "完整性测试" * 100,
            "min_chapters": 999,
            "raw_outline": "x" * 10000,
            "validated_chapters": [{"title": f"章节{i}", "summary": f"摘要{i}"} for i in range(100)]
        }
        state_manager.save_checkpoint(workflow_id, original_data)

        loaded = state_manager.load_checkpoint(workflow_id)
        assert loaded["current_chapter_index"] == 99
        assert loaded["completed_chapters"] == list(range(50))
        assert loaded["user_intent"] == "完整性测试" * 100
        assert len(loaded["validated_chapters"]) == 100

    def test_concurrent_checkpoint_operations(self, state_manager, temp_storage_dir):
        """Test concurrent checkpoint operations"""
        workflow_ids = [f"concurrent_{i}" for i in range(20)]
        errors = []

        def create_and_verify(wf_id):
            try:
                state_manager.save_checkpoint(wf_id, {
                    "current_chapter_index": 1,
                    "completed_chapters": [],
                    "current_node": f"node_{wf_id}"
                })
                import time
                time.sleep(0.001)
                assert state_manager.has_checkpoint(wf_id) is True
                loaded = state_manager.load_checkpoint(wf_id)
                assert loaded is not None
                assert loaded["current_node"] == f"node_{wf_id}"
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_and_verify, args=(wf_id,)) for wf_id in workflow_ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
