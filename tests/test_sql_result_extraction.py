#!/usr/bin/env python3
"""
测试SQL结果提取和显示。
"""
from src_optimized.utils.task_result_formatter import TaskResultLogger

def test_current_format_issue():
    """测试当前遇到的格式问题。"""
    logger = TaskResultLogger()
    
    # 模拟您遇到的真实数据格式
    evaluation_results = {
        "overall_score": 0.8,
        "evaluation_summary": "✓ Execution: PASSED | ✓ Syntax: VALID | Overall Score: 0.80",
        "execution_match": True,
        # 问题：predicted_result和ground_truth_result只包含SQL，没有实际的result数据
        "predicted_result": {
            "SQL": "SELECT DISTINCT schools.Zip\nFROM frpm\nJOIN schools ON frpm.CDSCode = schools.CDSCode\nWHERE frpm.`Charter School (Y/N)` = 1\n  AND LOWER(frpm.`County Name`) = 'fresno'\n  AND LOWER(frpm.`District Type`) LIKE '%county office of education%'"
        },
        "ground_truth_result": {
            "SQL": "SELECT T2.Zip FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.`District Name` = 'Fresno County Office of Education' AND T1.`Charter School (Y/N)` = 1"
        },
        "syntax_evaluation": {
            "syntax_correct": True,
            "issues": []
        }
    }
    
    logger.log_task_result(
        task_id="california_schools#2",
        question="Please list the zip code of all the charter schools in Fresno County Office of Education.",
        generated_sql="SELECT DISTINCT schools.Zip FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode WHERE frpm.`Charter School (Y/N)` = 1 AND LOWER(frpm.`County Name`) = 'fresno'",
        ground_truth_sql="SELECT T2.Zip FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.`District Name` = 'Fresno County Office of Education' AND T1.`Charter School (Y/N)` = 1",
        execution_status="success",
        evaluation_results=evaluation_results,
        processing_time=50.22
    )

def test_with_actual_results():
    """测试包含实际结果数据的情况。"""
    logger = TaskResultLogger()
    
    # 理想的数据格式，包含实际执行结果
    evaluation_results = {
        "overall_score": 0.85,
        "evaluation_summary": "✓ Execution: PASSED | ✓ Syntax: VALID | Overall Score: 0.85",
        "execution_match": True,
        "predicted_result": {
            "SQL": "SELECT zip_code FROM schools WHERE charter = 1",
            "result": [
                ["93650"], 
                ["93701"], 
                ["93722"], 
                ["93725"],
                ["93727"]
            ],
            "execution_time": 0.12,
            "status": "success"
        },
        "ground_truth_result": {
            "SQL": "SELECT T2.Zip FROM frpm AS T1 JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.charter = 1",
            "result": [
                ["93650"],
                ["93701"], 
                ["93722"],
                ["93725"],
                ["93727"]
            ],
            "execution_time": 0.08,
            "status": "success"
        }
    }
    
    logger.log_task_result(
        task_id="ideal_case#1",
        question="List zip codes of charter schools.",
        generated_sql="SELECT zip_code FROM schools WHERE charter = 1",
        ground_truth_sql="SELECT T2.Zip FROM frpm AS T1 JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.charter = 1",
        execution_status="success",
        evaluation_results=evaluation_results,
        processing_time=8.3
    )

def test_error_case():
    """测试SQL执行错误的情况。"""
    logger = TaskResultLogger()
    
    evaluation_results = {
        "overall_score": 0.0,
        "evaluation_summary": "✗ Execution: FAILED (syntax error) | ✗ Syntax: INCORRECT | Score: 0.0",
        "execution_match": False,
        "predicted_result": {
            "error": "syntax error near 'SELCT'",
            "status": "error"
        },
        "ground_truth_result": {
            "result": [["93650"], ["93701"]],
            "status": "success"
        }
    }
    
    logger.log_task_result(
        task_id="error_case#1",
        question="List zip codes.",
        generated_sql="SELCT zip FROM schools",
        ground_truth_sql="SELECT zip FROM schools",
        execution_status="failed",
        evaluation_results=evaluation_results,
        processing_time=2.1
    )

def test_empty_results():
    """测试空结果的情况。"""
    logger = TaskResultLogger()
    
    evaluation_results = {
        "overall_score": 1.0,
        "evaluation_summary": "✓ Execution: PASSED | Empty result set matched",
        "execution_match": True,
        "predicted_result": {
            "result": [],  # 空结果集
            "status": "success"
        },
        "ground_truth_result": {
            "result": [],  # 空结果集
            "status": "success"
        }
    }
    
    logger.log_task_result(
        task_id="empty_case#1",
        question="Find schools with impossible criteria.",
        generated_sql="SELECT name FROM schools WHERE enrollment < 0",
        ground_truth_sql="SELECT name FROM schools WHERE student_count < 0",
        execution_status="success",
        evaluation_results=evaluation_results,
        processing_time=1.5
    )

if __name__ == "__main__":
    print("="*100)
    print("测试SQL结果提取和显示")
    print("="*100)
    
    print("\n🔍 测试场景 1: 当前问题 - 只有SQL，没有实际结果数据")
    test_current_format_issue()
    
    print("\n🔍 测试场景 2: 理想情况 - 包含实际结果数据")
    test_with_actual_results()
    
    print("\n🔍 测试场景 3: 错误情况 - SQL执行失败")
    test_error_case()
    
    print("\n🔍 测试场景 4: 空结果集")
    test_empty_results()
    
    print("\n" + "="*100)
    print("改进说明：")
    print("✅ 智能识别不同的结果数据格式")
    print("✅ 过滤掉SQL字段，只显示实际执行结果")
    print("✅ 处理错误情况和空结果集")
    print("✅ 当没有实际结果数据时，提供适当的提示")
    print("="*100)