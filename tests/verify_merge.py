#!/usr/bin/env python
"""Quick verification script for the model_manager merge."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all key imports work."""
    print("Testing imports...")

    # Test create_model_manager
    from src.model_manager import create_model_manager
    print("  create_model_manager: OK")

    # Test PooledManager alias
    from src.model_manager import PooledManager
    print("  PooledManager: OK")

    # Test MultiKeyManager
    from src.model_manager import MultiKeyManager
    print("  MultiKeyManager: OK")

    # Test APIModelManager
    from src.model_manager import APIModelManager
    print("  APIModelManager: OK")

    # Test LocalModelManager
    from src.model_manager import LocalModelManager
    print("  LocalModelManager: OK")

    print("\nAll imports successful!")
    return True

def test_workflow_imports():
    """Test workflow.py imports."""
    print("\nTesting workflow imports...")

    from src.workflow import create_workflow
    print("  create_workflow: OK")

    print("\nWorkflow imports successful!")
    return True

if __name__ == "__main__":
    try:
        test_imports()
        test_workflow_imports()
        print("\n=== ALL TESTS PASSED ===")
        sys.exit(0)
    except Exception as e:
        print(f"\n=== TEST FAILED: {e} ===")
        sys.exit(1)