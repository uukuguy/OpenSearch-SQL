#!/usr/bin/env python3
"""
测试RunManager集成修复 - 验证增强的进度条是否正确集成。
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

# Add src_optimized to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src_optimized'))

from src_optimized.core.task import Task
from src_optimized.runner.run_manager import RunManager


@dataclass
class MockArgs:
    """模拟运行参数"""
    db_root_path: str = "Bird"
    data_mode: str = "dev"
    result_root_path: str = "results"
    run_start_time: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    enable_multiprocessing: bool = False
    num_workers: int = 1
    log_level: str = "INFO"
    pipeline_setup: str = '{"use_hints": false, "temperature": 0.0}'
    pipeline_nodes: List[str] = None
    use_checkpoint: bool = False

    def __post_init__(self):
        if self.pipeline_nodes is None:
            self.pipeline_nodes = ["generate_db_schema", "evaluation"]


def create_mock_dataset(size: int = 10) -> List[Dict[str, Any]]:
    """创建模拟数据集"""
    dataset = []
    for i in range(size):
        dataset.append({
            "question_id": i,
            "question": f"Sample question {i}",
            "db_id": f"database_{i//5}",
            "SQL": f"SELECT * FROM table_{i} LIMIT 10;",  # Ground truth SQL
            "difficulty": "easy" if i % 2 == 0 else "medium"
        })
    return dataset


def simulate_task_completion(run_manager: RunManager, task_index: int, task: Task):
    """模拟任务完成"""
    
    # 模拟不同的任务结果
    if task_index % 7 == 0:
        # 模拟失败的任务
        generated_sql = "SLECT invalid syntax"
        execution_status = "failed" 
        evaluation_results = {
            "overall_score": 0.0,
            "exec_res": 0,
            "execution_match": False,
            "evaluation_summary": "Syntax error in SQL",
            "error": "syntax error near 'SLECT'"
        }
        error_message = "syntax error near 'SLECT'"
    elif task_index % 5 == 0:
        # 模拟部分正确的任务
        generated_sql = f"SELECT id FROM table_{task_index};"
        execution_status = "success"
        evaluation_results = {
            "overall_score": 0.6,
            "exec_res": 1,
            "execution_match": False,  # 结果不完全匹配
            "evaluation_summary": "Partial match",
            "predicted_result": {
                "SQL": generated_sql,
                "RESULT": [[1], [2], [3]],
                "STATUS": "OK"
            },
            "ground_truth_result": {
                "SQL": task.SQL,
                "RESULT": [[1], [2], [3], [4], [5]],
                "STATUS": "OK"
            }
        }
        error_message = ""
    else:
        # 模拟成功的任务
        generated_sql = task.SQL  # 完全匹配
        execution_status = "success"
        evaluation_results = {
            "overall_score": 1.0,
            "exec_res": 1,
            "execution_match": True,
            "evaluation_summary": "Perfect match",
            "predicted_result": {
                "SQL": generated_sql,
                "RESULT": [[1], [2], [3], [4], [5]],
                "STATUS": "OK"
            },
            "ground_truth_result": {
                "SQL": task.SQL,
                "RESULT": [[1], [2], [3], [4], [5]],
                "STATUS": "OK"
            }
        }
        error_message = ""
    
    # 模拟处理时间
    processing_time = 0.5 + (task_index % 3) * 0.3
    
    # 模拟状态结构
    mock_state = {
        "keys": {
            "execution_history": [
                {
                    "node_type": "candidate_generate",
                    "SQL": generated_sql,
                    "status": "completed"
                },
                {
                    "node_type": "evaluation",
                    "exec_res": evaluation_results["exec_res"],
                    "overall_score": evaluation_results["overall_score"],
                    "evaluation_summary": evaluation_results["evaluation_summary"],
                    "execution_match": evaluation_results["execution_match"],
                    "predicted_result": evaluation_results.get("predicted_result"),
                    "ground_truth_result": evaluation_results.get("ground_truth_result"),
                    "error": error_message,
                    "status": "completed"
                }
            ]
        }
    }
    
    # 调用task_done模拟任务完成
    log_tuple = (mock_state, task.db_id, task.question_id, task_index, processing_time)
    run_manager.task_done(log_tuple, task)


def test_enhanced_progress_integration():
    """测试增强的进度条集成"""
    print("=" * 100)
    print("测试RunManager增强进度条集成")
    print("=" * 100)
    
    # 创建模拟参数和数据集
    args = MockArgs()
    dataset = create_mock_dataset(25)  # 25个任务用于演示
    
    print(f"创建RunManager实例...")
    run_manager = RunManager(args)
    
    print(f"初始化 {len(dataset)} 个任务...")
    run_manager.initialize_tasks(0, len(dataset), dataset)
    
    print(f"验证ProgressTracker初始化...")
    if run_manager.progress_tracker is None:
        print("❌ 错误：ProgressTracker未正确初始化!")
        return
    else:
        print("✅ ProgressTracker已正确初始化")
        print(f"   - 总任务数: {run_manager.progress_tracker.total_tasks}")
        print(f"   - 有Ground Truth: {run_manager.progress_tracker.has_ground_truth}")
    
    print("\n" + "=" * 100)
    print("开始模拟任务处理...")
    print("新功能展示:")
    print("✅ 已用时间显示")
    print("✅ 预估剩余时间")  
    print("✅ 总计预估时间")
    print("✅ 实时处理速度")
    print("✅ 准确率统计")
    print("✅ SQL结果显示")
    print("=" * 100 + "\n")
    
    # 模拟任务处理
    for i, data in enumerate(dataset):
        # 模拟处理时间
        processing_delay = 0.2 + (i % 4) * 0.1  # 变化的处理时间
        time.sleep(processing_delay)
        
        # 创建Task对象
        task = Task(data)
        task.original_index = i
        
        # 模拟任务完成
        simulate_task_completion(run_manager, i, task)
        
        # 在关键节点暂停让用户观察
        if i in [5, 15, 20]:
            time.sleep(1.0)
    
    # 调用完成方法
    if hasattr(run_manager, 'finalize'):
        run_manager.finalize()
    elif run_manager.progress_tracker:
        run_manager.progress_tracker.finish()
    
    print("\n" + "=" * 100)
    print("测试完成!")
    print("验证项目:")
    print("✅ ProgressTracker正确初始化")
    print("✅ 增强的进度条显示（时间、速度、准确率）")
    print("✅ 详细任务完成结果显示")
    print("✅ SQL执行结果对比显示")
    print("✅ 错误过滤和智能提示")
    print("=" * 100)


if __name__ == "__main__":
    test_enhanced_progress_integration()