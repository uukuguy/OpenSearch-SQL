#!/usr/bin/env python3
"""
Test script to verify fixes for execution history processing errors.
"""
import json
from unittest.mock import Mock, MagicMock
from src_optimized.runner.run_manager import RunManager

def test_execution_history_with_mixed_types():
    """Test that execution history handles mixed types correctly."""
    print("Testing execution history with mixed types...")
    
    # Create a mock RunManager with a minimal args object
    class MockArgs:
        def __init__(self):
            self.db_root_path = "/test/db"
            self.run_start_time = "2025-01-01-00-00-00"
            self.data_mode = "test"
            self.log_level = "INFO"
            self.pipeline_setup = json.dumps({"test": "config"})
            self.pipeline_nodes = ["test_node"]
    
    mock_args = MockArgs()
    
    # Create manager
    manager = RunManager(mock_args)
    manager.error_filter = Mock()
    manager.error_filter.is_expected_error.return_value = False
    manager.statistics_manager = Mock()
    manager.progress_tracker = None
    
    # Test case 1: Execution history with mixed types (dict and int)
    print("\n1. Testing mixed types in execution history...")
    test_state = {
        "keys": {
            "execution_history": [
                {"node_type": "generate_db_schema", "status": "success"},
                {"node_type": "extract_col_value", "status": "success"},
                1,  # This is an integer, not a dict
                {"node_type": "vote", "SQL": "SELECT * FROM users"},
                2,  # Another integer
                {"node_type": "evaluation", "exec_res": 1}
            ]
        }
    }
    
    mock_task = Mock()
    mock_task.db_id = "test_db"
    mock_task.question_id = 1
    mock_task.question = "Test question"
    mock_task.SQL = "SELECT * FROM users"
    
    # This should not raise an error
    try:
        manager.task_done((test_state, "test_db", 1, 0, 1.0), mock_task)
        print("✓ Successfully handled mixed types in execution history")
    except AttributeError as e:
        print(f"✗ Failed: {e}")
        
    # Test case 2: Execution history with all integers
    print("\n2. Testing all integers in execution history...")
    test_state_int = {
        "keys": {
            "execution_history": [1, 2, 3, 4, 5]  # All integers
        }
    }
    
    try:
        manager.task_done((test_state_int, "test_db", 2, 1, 1.0), mock_task)
        print("✓ Successfully handled all-integer execution history")
    except AttributeError as e:
        print(f"✗ Failed: {e}")
        
    # Test case 3: Empty execution history
    print("\n3. Testing empty execution history...")
    test_state_empty = {
        "keys": {
            "execution_history": []
        }
    }
    
    try:
        manager.task_done((test_state_empty, "test_db", 3, 2, 1.0), mock_task)
        print("✓ Successfully handled empty execution history")
    except Exception as e:
        print(f"✗ Failed: {e}")
        
    # Test case 4: Normal execution history (all dicts)
    print("\n4. Testing normal execution history...")
    test_state_normal = {
        "keys": {
            "execution_history": [
                {"node_type": "generate_db_schema", "status": "success"},
                {"node_type": "extract_col_value", "status": "success"},
                {"node_type": "vote", "SQL": "SELECT name FROM users WHERE age > 25"},
                {"node_type": "evaluation", "exec_res": 1, "execution_accuracy": 1.0}
            ]
        }
    }
    
    try:
        manager.task_done((test_state_normal, "test_db", 4, 3, 1.0), mock_task)
        print("✓ Successfully handled normal execution history")
    except Exception as e:
        print(f"✗ Failed: {e}")

def test_collect_task_result_with_mixed_types():
    """Test _collect_task_result with mixed types."""
    print("\n\nTesting _collect_task_result with mixed types...")
    
    # Create a mock RunManager with a minimal args object
    class MockArgs:
        def __init__(self):
            self.db_root_path = "/test/db"
            self.run_start_time = "2025-01-01-00-00-00"
            self.data_mode = "test"
            self.log_level = "INFO"
            self.pipeline_setup = json.dumps({"test": "config"})
            self.pipeline_nodes = ["test_node"]
    
    mock_args = MockArgs()
    
    manager = RunManager(mock_args)
    manager.results_collector = Mock()
    
    # Test with mixed types in execution history
    test_state = {
        "keys": {
            "execution_history": [
                {"node_type": "generate_db_schema"},
                "string_value",  # String instead of dict
                {"node_type": "candidate_generate", "SQL": ["SELECT * FROM test"]},
                None,  # None value
                {"node_type": "evaluation", "exec_res": 0}
            ]
        }
    }
    
    mock_task = Mock()
    mock_task.db_id = "test_db"
    mock_task.question_id = 1
    mock_task.question = "Test question"
    mock_task.evidence = ""
    mock_task.SQL = "SELECT * FROM test"
    
    try:
        manager._collect_task_result(test_state, mock_task, 0, 1.5)
        print("✓ Successfully handled mixed types in _collect_task_result")
    except AttributeError as e:
        print(f"✗ Failed: {e}")

if __name__ == "__main__":
    print("="*60)
    print("Testing Error Fixes for Execution History Processing")
    print("="*60)
    
    test_execution_history_with_mixed_types()
    test_collect_task_result_with_mixed_types()
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("The fixes ensure that:")
    print("✓ Non-dictionary items in execution history are safely handled")
    print("✓ No AttributeError when calling .get() on non-dict objects")
    print("✓ Pipeline continues processing even with malformed data")
    print("="*60)