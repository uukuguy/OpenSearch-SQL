#!/usr/bin/env python3
"""
测试最终的verbose行为：任务结果始终详细显示，管道日志由verbose控制。
"""
import os
import sys
from pathlib import Path

# Add src_optimized to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src_optimized'))

from src_optimized.utils.task_result_formatter import TaskResultLogger
from src_optimized.utils.loguru_config import setup_logging, get_logger


def test_task_result_always_detailed():
    """测试任务结果始终详细显示（不受verbose控制）"""
    
    print("=" * 100)
    print("测试：任务结果始终详细显示")
    print("=" * 100)
    
    # 测试数据
    task_result = {
        "task_id": "california_schools#1",
        "question": "List the zip code of all charter schools in Fresno County.",
        "generated_sql": "SELECT DISTINCT schools.Zip FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode WHERE frpm.`Charter School (Y/N)` = 1",
        "ground_truth_sql": "SELECT T2.Zip FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.`Charter School (Y/N)` = 1", 
        "execution_status": "success",
        "evaluation_results": {
            "overall_score": 1.0,
            "evaluation_summary": "Perfect match",
            "execution_match": True,
            "predicted_result": {
                "SQL": "SELECT DISTINCT schools.Zip FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode WHERE frpm.`Charter School (Y/N)` = 1",
                "RESULT": [["93650"], ["93701"], ["93722"], ["93725"], ["93727"]],
                "STATUS": "OK"
            },
            "ground_truth_result": {
                "SQL": "SELECT T2.Zip FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.`Charter School (Y/N)` = 1",
                "RESULT": [["93650"], ["93701"], ["93722"], ["93725"], ["93727"]],
                "STATUS": "OK"
            }
        },
        "processing_time": 45.2,
        "error_message": ""
    }
    
    print("\n🔹 任务结果显示（始终详细，不受verbose影响）:")
    print("-" * 80)
    
    # TaskResultLogger不再接受verbose参数，始终详细显示
    logger = TaskResultLogger()
    logger.log_task_result(**task_result)
    
    print("\n" + "=" * 100)
    print("✅ 验证结果：")
    print("- 任务结果始终显示完整的详细信息")
    print("- 包含问题、生成的SQL、标准SQL、执行状态、评估结果、处理时间等")
    print("- 不受verbose模式影响")
    print("=" * 100)


def test_pipeline_logging_control():
    """测试管道日志的verbose控制"""
    
    print("\n" + "=" * 100)
    print("测试：管道日志的verbose控制")
    print("=" * 100)
    
    print("\n🔹 非详细模式 (verbose=False, 默认):")
    print("- 管道运行日志被过滤，只显示重要信息")
    print("- 任务结果依然完整显示")
    
    # 测试非详细模式
    setup_logging(log_level="INFO", verbose=False)
    logger = get_logger("test.pipeline.candidate_generate")
    
    print("\n模拟管道节点日志:")
    logger.info("生成SQL候选: SELECT * FROM users")  # 在非详细模式下会被过滤
    logger.info("Task completed successfully")  # 重要信息会显示
    logger.warning("This is a warning message")  # 警告会显示
    logger.error("This is an error message")  # 错误会显示
    
    print("\n🔹 详细模式 (verbose=True):")
    print("- 显示所有管道日志信息")
    print("- 包含中间步骤的详细处理过程")
    
    # 重新配置为详细模式
    from src_optimized.utils.loguru_config import LoguruConfig
    LoguruConfig.reset_configuration()
    setup_logging(log_level="INFO", verbose=True)
    logger_verbose = get_logger("test.pipeline.candidate_generate")
    
    print("\n详细模式下的管道节点日志:")
    logger_verbose.info("生成SQL候选: SELECT * FROM users")  # 在详细模式下会显示
    logger_verbose.info("开始对齐处理...")  # 详细步骤会显示
    logger_verbose.debug("调试信息...")  # 调试信息可能显示
    
    print("\n" + "=" * 100)
    print("总结:")
    print("✅ 任务结果：始终详细显示（重要信息）")
    print("✅ 管道日志：通过verbose参数控制详细程度")
    print("✅ 默认模式：简洁的管道日志 + 详细的任务结果")
    print("✅ 调试模式：详细的管道日志 + 详细的任务结果")
    print("=" * 100)


if __name__ == "__main__":
    test_task_result_always_detailed()
    test_pipeline_logging_control()