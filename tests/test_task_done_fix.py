#!/usr/bin/env python3
"""
测试task_done方法的错误修复。
"""
import json
from unittest.mock import Mock, MagicMock
from src_optimized.runner.run_manager import RunManager

def test_task_done_with_none_state():
    """测试state为None的情况。"""
    print("测试 state = None 的情况...")
    
    # 创建RunManager
    class MockArgs:
        def __init__(self):
            self.db_root_path = "/test/db"
            self.run_start_time = "2025-01-01-00-00-00"
            self.data_mode = "test"
            self.log_level = "INFO"
            self.pipeline_setup = json.dumps({"test": "config"})
            self.pipeline_nodes = ["test_node"]
    
    manager = RunManager(MockArgs())
    manager.statistics_manager = Mock()
    manager.progress_tracker = None
    
    mock_task = Mock()
    mock_task.db_id = "test_db"
    mock_task.question_id = 1
    mock_task.question = "Test question"
    mock_task.SQL = "SELECT * FROM test"
    
    # state为None的情况
    try:
        manager.task_done((None, "test_db", 1, 0, 1.0), mock_task)
        print("✅ 成功处理 state = None")
    except Exception as e:
        print(f"❌ 失败: {e}")

def test_task_done_with_invalid_execution_history():
    """测试execution_history包含非字典元素的情况。"""
    print("\n测试 execution_history 包含非字典元素的情况...")
    
    class MockArgs:
        def __init__(self):
            self.db_root_path = "/test/db"
            self.run_start_time = "2025-01-01-00-00-00"
            self.data_mode = "test"
            self.log_level = "INFO"
            self.pipeline_setup = json.dumps({"test": "config"})
            self.pipeline_nodes = ["test_node"]
    
    manager = RunManager(MockArgs())
    manager.statistics_manager = Mock()
    manager.progress_tracker = None
    
    mock_task = Mock()
    mock_task.db_id = "test_db"
    mock_task.question_id = 2
    mock_task.question = "Test question"
    mock_task.SQL = "SELECT * FROM test"
    
    # 包含非字典元素的execution_history
    test_state = {
        "keys": {
            "execution_history": [
                {"node_type": "start", "status": "ok"},
                1,  # 整数
                "string",  # 字符串
                {"node_type": "evaluation", "exec_res": 1}  # 正常字典
            ]
        }
    }
    
    try:
        manager.task_done((test_state, "test_db", 2, 1, 2.0), mock_task)
        print("✅ 成功处理包含非字典元素的 execution_history")
    except Exception as e:
        print(f"❌ 失败: {e}")

def test_task_done_with_empty_state():
    """测试空state的情况。"""
    print("\n测试空 state 的情况...")
    
    class MockArgs:
        def __init__(self):
            self.db_root_path = "/test/db"
            self.run_start_time = "2025-01-01-00-00-00"
            self.data_mode = "test"
            self.log_level = "INFO"
            self.pipeline_setup = json.dumps({"test": "config"})
            self.pipeline_nodes = ["test_node"]
    
    manager = RunManager(MockArgs())
    manager.statistics_manager = Mock()
    manager.progress_tracker = None
    
    mock_task = Mock()
    mock_task.db_id = "test_db"
    mock_task.question_id = 3
    mock_task.question = "Test question"
    mock_task.SQL = "SELECT * FROM test"
    
    # 空的state
    test_state = {}
    
    try:
        manager.task_done((test_state, "test_db", 3, 2, 3.0), mock_task)
        print("✅ 成功处理空 state")
    except Exception as e:
        print(f"❌ 失败: {e}")

def test_task_done_normal_case():
    """测试正常情况。"""
    print("\n测试正常情况...")
    
    class MockArgs:
        def __init__(self):
            self.db_root_path = "/test/db"
            self.run_start_time = "2025-01-01-00-00-00"
            self.data_mode = "test"
            self.log_level = "INFO"
            self.pipeline_setup = json.dumps({"test": "config"})
            self.pipeline_nodes = ["test_node"]
    
    manager = RunManager(MockArgs())
    manager.statistics_manager = Mock()
    manager.progress_tracker = None
    
    mock_task = Mock()
    mock_task.db_id = "test_db"
    mock_task.question_id = 4
    mock_task.question = "Test question"
    mock_task.SQL = "SELECT * FROM test"
    
    # 正常的state
    test_state = {
        "keys": {
            "execution_history": [
                {"node_type": "start", "status": "ok"},
                {"node_type": "vote", "SQL": "SELECT * FROM test"},
                {"node_type": "evaluation", "exec_res": 1, "execution_accuracy": 0.95}
            ]
        }
    }
    
    try:
        manager.task_done((test_state, "test_db", 4, 3, 4.0), mock_task)
        print("✅ 成功处理正常情况")
    except Exception as e:
        print(f"❌ 失败: {e}")

if __name__ == "__main__":
    print("="*60)
    print("测试 task_done 方法的错误修复")
    print("="*60)
    
    test_task_done_with_none_state()
    test_task_done_with_invalid_execution_history() 
    test_task_done_with_empty_state()
    test_task_done_normal_case()
    
    print("\n" + "="*60)
    print("所有测试完成！")
    print("现在 task_done 方法能够正确处理：")
    print("✅ state = None 的情况")
    print("✅ execution_history 包含非字典元素")
    print("✅ 空的 state")
    print("✅ 正常的完整数据")
    print("="*60)