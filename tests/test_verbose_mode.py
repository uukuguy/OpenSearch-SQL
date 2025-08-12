#!/usr/bin/env python3
"""
测试详细模式和简洁模式的日志输出控制。
"""
import os
import sys
from pathlib import Path

# Add src_optimized to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src_optimized'))

from src_optimized.utils.task_result_formatter import TaskResultLogger
from src_optimized.utils.loguru_config import LoguruConfig


def test_verbose_modes():
    """测试详细模式和简洁模式的区别"""
    
    print("=" * 100)
    print("测试日志输出模式控制")
    print("=" * 100)
    
    # 测试数据
    task_results = [
        {
            "task_id": "california_schools#1",
            "question": "List the zip code of all the charter schools in Fresno County Office of Education.",
            "generated_sql": "SELECT DISTINCT schools.Zip FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode WHERE frpm.`Charter School (Y/N)` = 1",
            "ground_truth_sql": "SELECT T2.Zip FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.`Charter School (Y/N)` = 1", 
            "execution_status": "success",
            "evaluation_results": {
                "overall_score": 1.0,
                "evaluation_summary": "Perfect match",
                "execution_match": True,
                "predicted_result": {
                    "SQL": "SELECT DISTINCT schools.Zip FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode WHERE frpm.`Charter School (Y/N)` = 1",
                    "RESULT": [["93650"], ["93701"], ["93722"]],
                    "STATUS": "OK"
                }
            },
            "processing_time": 45.2,
            "error_message": ""
        },
        {
            "task_id": "student_db#5", 
            "question": "What is the average age of students?",
            "generated_sql": "SLECT AVG(age) FROM students",
            "ground_truth_sql": "SELECT AVG(age) FROM students",
            "execution_status": "failed",
            "evaluation_results": {
                "overall_score": 0.0,
                "evaluation_summary": "Syntax error",
                "execution_match": False
            },
            "processing_time": 2.3,
            "error_message": "syntax error near 'SLECT'"
        },
        {
            "task_id": "company_db#8",
            "question": "How many employees work in each department?", 
            "generated_sql": "SELECT department, COUNT(*) FROM employees GROUP BY dept",
            "ground_truth_sql": "SELECT department, COUNT(*) FROM employees GROUP BY department",
            "execution_status": "success",
            "evaluation_results": {
                "overall_score": 0.6,
                "evaluation_summary": "Partial match - column name mismatch",
                "execution_match": False
            },
            "processing_time": 12.8,
            "error_message": ""
        }
    ]
    
    # 测试简洁模式
    print("\n🔹 简洁模式 (verbose=False) - 适合实际运行:")
    print("-" * 60)
    logger_compact = TaskResultLogger(verbose=False)
    
    for result in task_results:
        logger_compact.log_task_result(**result)
    
    print("\n" + "=" * 100)
    
    # 测试详细模式  
    print("\n🔹 详细模式 (verbose=True) - 适合调试:")
    print("-" * 60)
    logger_verbose = TaskResultLogger(verbose=True)
    
    # 只展示第一个任务的详细信息作为示例
    print("(仅展示第一个任务的详细模式，其他类似)")
    logger_verbose.log_task_result(**task_results[0])
    
    print("\n" + "=" * 100)
    print("总结:")
    print("✅ 简洁模式: 每个任务一行摘要，突出关键信息")
    print("✅ 详细模式: 完整的任务信息，包括问题、SQL、评估结果等")
    print("✅ 管道节点日志: 通过loguru配置的verbose参数控制")
    print("=" * 100)


def test_pipeline_logging():
    """演示管道日志控制"""
    print("\n" + "=" * 100)
    print("管道运行日志控制演示")
    print("=" * 100)
    
    print("\n🔹 非详细模式 (默认):")
    print("- 只显示重要的管道进度信息")
    print("- 过滤掉中间节点的常规日志")
    print("- 保留错误和警告信息")
    
    print("\n🔹 详细模式 (--verbose):")  
    print("- 显示所有管道节点的处理日志")
    print("- 包含SQL生成、对齐、投票等中间步骤")
    print("- 适合调试和开发使用")
    
    print("\n设置方法:")
    print("1. 在运行脚本中添加: args.verbose = True/False")
    print("2. 或在命令行参数中支持: --verbose 选项")
    print("=" * 100)


if __name__ == "__main__":
    test_verbose_modes()
    test_pipeline_logging()