"""
Unit tests for src/core/ module
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from src.core.progress import ProgressEvent, ProgressEmitter, WorkflowStatus, get_progress_emitter, emit_progress
from src.core.state_manager import StateManager, WorkflowInfo


class TestProgressEvent:
    """Tests for ProgressEvent"""

    def test_create_progress_event(self):
        """Test creating a progress event"""
        event = ProgressEvent(
            workflow_id="test123",
            node="write_chapter",
            status=WorkflowStatus.RUNNING,
            message="正在撰写第5章",
            chapter_index=4,
            total_chapters=50
        )
        assert event.workflow_id == "test123"
        assert event.node == "write_chapter"
        assert event.status == WorkflowStatus.RUNNING
        assert event.chapter_index == 4
        assert event.total_chapters == 50
        assert event.timestamp is not None

    def test_to_dict(self):
        """Test converting to dictionary"""
        event = ProgressEvent(
            workflow_id="test123",
            node="write_chapter",
            status=WorkflowStatus.RUNNING,
            message="test"
        )
        d = event.to_dict()
        assert d["workflow_id"] == "test123"
        assert d["status"] == "running"
        assert isinstance(d["timestamp"], str)


class TestProgressEmitter:
    """Tests for ProgressEmitter"""

    def test_subscribe_and_emit(self):
        """Test subscribe and emit pattern"""
        emitter = ProgressEmitter()
        received = []

        def callback(event):
            received.append(event)

        emitter.subscribe(callback)
        event = ProgressEvent(
            workflow_id="test",
            node="test_node",
            status=WorkflowStatus.RUNNING,
            message="test"
        )
        emitter.emit(event)

        assert len(received) == 1
        assert received[0].workflow_id == "test"

    def test_unsubscribe(self):
        """Test unsubscribe"""
        emitter = ProgressEmitter()
        received = []

        def callback(event):
            received.append(event)

        emitter.subscribe(callback)
        emitter.unsubscribe(callback)

        event = ProgressEvent(
            workflow_id="test",
            node="test_node",
            status=WorkflowStatus.RUNNING,
            message="test"
        )
        emitter.emit(event)

        assert len(received) == 0

    def test_get_latest(self):
        """Test getting latest event"""
        emitter = ProgressEmitter()
        event = ProgressEvent(
            workflow_id="latest_test",
            node="test_node",
            status=WorkflowStatus.RUNNING,
            message="test"
        )
        emitter.emit(event)

        latest = emitter.get_latest("latest_test")
        assert latest is not None
        assert latest.workflow_id == "latest_test"

    def test_clear(self):
        """Test clearing latest event"""
        emitter = ProgressEmitter()
        event = ProgressEvent(
            workflow_id="clear_test",
            node="test_node",
            status=WorkflowStatus.RUNNING,
            message="test"
        )
        emitter.emit(event)
        emitter.clear("clear_test")

        latest = emitter.get_latest("clear_test")
        assert latest is None


class TestStateManager:
    """Tests for StateManager"""

    @pytest.fixture
    def temp_state_manager(self):
        """Create a temporary state manager for testing"""
        temp_dir = tempfile.mkdtemp()
        manager = StateManager(storage_dir=temp_dir)
        yield manager
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_save_and_load_state(self, temp_state_manager):
        """Test saving and loading state"""
        workflow_id = "test_workflow_001"
        state_data = {
            "user_intent": "创作一个科幻小说",
            "min_chapters": 10,
            "current_node": "write_chapter"
        }

        temp_state_manager.save_state(workflow_id, state_data)
        loaded = temp_state_manager.load_state(workflow_id)

        assert loaded is not None
        assert loaded["user_intent"] == "创作一个科幻小说"
        assert loaded["min_chapters"] == 10
        assert "_saved_at" in loaded

    def test_load_nonexistent(self, temp_state_manager):
        """Test loading nonexistent workflow returns None"""
        result = temp_state_manager.load_state("nonexistent_id")
        assert result is None

    def test_delete_state(self, temp_state_manager):
        """Test deleting state"""
        workflow_id = "delete_test"
        temp_state_manager.save_state(workflow_id, {"test": "data"})

        result = temp_state_manager.delete_state(workflow_id)
        assert result is True

        loaded = temp_state_manager.load_state(workflow_id)
        assert loaded is None

    def test_delete_nonexistent(self, temp_state_manager):
        """Test deleting nonexistent workflow"""
        result = temp_state_manager.delete_state("nonexistent")
        assert result is False

    def test_create_workflow_record(self, temp_state_manager):
        """Test creating a workflow record"""
        workflow_id = "create_test"
        user_intent = "测试创作意图"
        initial_state = {"user_intent": user_intent, "min_chapters": 5}

        temp_state_manager.create_workflow_record(workflow_id, user_intent, initial_state)

        loaded = temp_state_manager.load_state(workflow_id)
        assert loaded is not None
        assert loaded["user_intent"] == user_intent
        assert loaded["status"] == "pending"
        assert "_created_at" in loaded

    def test_update_status(self, temp_state_manager):
        """Test updating workflow status"""
        workflow_id = "status_test"
        temp_state_manager.save_state(workflow_id, {"user_intent": "test"})

        temp_state_manager.update_status(
            workflow_id,
            WorkflowStatus.RUNNING,
            current_node="write_chapter",
            progress=0.5
        )

        loaded = temp_state_manager.load_state(workflow_id)
        assert loaded["status"] == "running"
        assert loaded["current_node"] == "write_chapter"
        assert loaded["progress"] == 0.5

    def test_list_workflows(self, temp_state_manager):
        """Test listing workflows"""
        # Create multiple workflows (all start with PENDING status)
        for i in range(3):
            wf_id = f"list_test_{i}"
            temp_state_manager.create_workflow_record(
                wf_id,
                f"意图{i}",
                {"user_intent": f"意图{i}"}
            )

        workflows = temp_state_manager.list_workflows()
        assert len(workflows) == 3

        # All are PENDING initially
        pending_workflows = temp_state_manager.list_workflows(status=WorkflowStatus.PENDING)
        assert len(pending_workflows) == 3

        # Update status to RUNNING
        temp_state_manager.update_status("list_test_0", WorkflowStatus.RUNNING)
        running_workflows = temp_state_manager.list_workflows(status=WorkflowStatus.RUNNING)
        assert len(running_workflows) == 1

        # Update another one to COMPLETED
        temp_state_manager.update_status("list_test_1", WorkflowStatus.COMPLETED)
        completed_workflows = temp_state_manager.list_workflows(status=WorkflowStatus.COMPLETED)
        assert len(completed_workflows) == 1
        running_workflows = temp_state_manager.list_workflows(status=WorkflowStatus.RUNNING)
        assert len(running_workflows) == 1

    def test_workflow_info_model(self):
        """Test WorkflowInfo model"""
        from datetime import datetime
        info = WorkflowInfo(
            workflow_id="test",
            user_intent="科幻小说",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            status=WorkflowStatus.RUNNING,
            current_node="write_chapter",
            progress=0.5
        )
        assert info.workflow_id == "test"
        assert info.status == WorkflowStatus.RUNNING
        assert info.progress == 0.5
