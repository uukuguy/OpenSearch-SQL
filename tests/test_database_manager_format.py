#!/usr/bin/env python3
"""
测试使用DatabaseManager真实返回格式的结果显示。
"""
from src_optimized.utils.task_result_formatter import TaskResultLogger

def test_database_manager_format():
    """测试DatabaseManager的validate_sql_query返回格式。"""
    logger = TaskResultLogger()
    
    # 模拟DatabaseManager.validate_sql_query的真实返回格式
    evaluation_results = {
        "overall_score": 0.8,
        "evaluation_summary": "✓ Execution: PASSED | ✓ Syntax: VALID | Overall Score: 0.80",
        "execution_match": True,
        "exec_res": 1,
        "predicted_result": {
            "SQL": "SELECT DISTINCT schools.Zip FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode WHERE frpm.`Charter School (Y/N)` = 1",
            "RESULT": [  # 大写的RESULT字段
                ["93650"],
                ["93701"], 
                ["93722"],
                ["93725"],
                ["93727"]
            ],
            "STATUS": "OK"  # 大写的STATUS字段
        },
        "ground_truth_result": {
            "SQL": "SELECT T2.Zip FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.`Charter School (Y/N)` = 1",
            "RESULT": [
                ["93650"],
                ["93701"],
                ["93722"], 
                ["93725"],
                ["93727"]
            ],
            "STATUS": "OK"
        },
        "syntax_evaluation": {
            "syntax_correct": True,
            "issues": []
        }
    }
    
    logger.log_task_result(
        task_id="california_schools#2",
        question="Please list the zip code of all the charter schools in Fresno County Office of Education.",
        generated_sql="SELECT DISTINCT schools.Zip FROM frpm JOIN schools ON frpm.CDSCode = schools.CDSCode WHERE frpm.`Charter School (Y/N)` = 1",
        ground_truth_sql="SELECT T2.Zip FROM frpm AS T1 INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode WHERE T1.`Charter School (Y/N)` = 1",
        execution_status="success",
        evaluation_results=evaluation_results,
        processing_time=50.22
    )

def test_database_manager_error():
    """测试DatabaseManager错误格式。"""
    logger = TaskResultLogger()
    
    evaluation_results = {
        "overall_score": 0.0,
        "evaluation_summary": "✗ Execution: FAILED (syntax error) | Score: 0.0",
        "execution_match": False,
        "exec_res": 0,
        "predicted_result": {
            "SQL": "SELCT zip FROM schools",
            "RESULT": "near \"SELCT\": syntax error",  # 错误信息在RESULT字段中
            "STATUS": "ERROR"  # STATUS为ERROR
        },
        "ground_truth_result": {
            "SQL": "SELECT zip FROM schools",
            "RESULT": [["93650"], ["93701"]],
            "STATUS": "OK"
        }
    }
    
    logger.log_task_result(
        task_id="syntax_error#2",
        question="List zip codes.",
        generated_sql="SELCT zip FROM schools",
        ground_truth_sql="SELECT zip FROM schools", 
        execution_status="failed",
        evaluation_results=evaluation_results,
        processing_time=3.5
    )

def test_mixed_case():
    """测试混合大小写的情况。"""
    logger = TaskResultLogger()
    
    evaluation_results = {
        "overall_score": 0.6,
        "evaluation_summary": "Partially correct",
        "execution_match": False,
        "predicted_result": {
            "SQL": "SELECT name FROM students LIMIT 5",
            "result": [  # 小写的result（某些情况下可能出现）
                ["Alice"],
                ["Bob"], 
                ["Carol"]
            ],
            "status": "success"
        },
        "ground_truth_result": {
            "SQL": "SELECT student_name FROM students LIMIT 5", 
            "RESULT": [  # 大写的RESULT
                ["Alice Smith"],
                ["Bob Jones"],
                ["Carol Brown"]
            ],
            "STATUS": "OK"
        }
    }
    
    logger.log_task_result(
        task_id="mixed_case#1",
        question="Get 5 student names.",
        generated_sql="SELECT name FROM students LIMIT 5",
        ground_truth_sql="SELECT student_name FROM students LIMIT 5",
        execution_status="success", 
        evaluation_results=evaluation_results,
        processing_time=2.1
    )

if __name__ == "__main__":
    print("="*100)
    print("测试DatabaseManager真实返回格式的结果显示")
    print("="*100)
    
    print("\n🔧 测试场景 1: DatabaseManager成功格式 (RESULT + STATUS)")
    test_database_manager_format()
    
    print("\n🔧 测试场景 2: DatabaseManager错误格式")
    test_database_manager_error()
    
    print("\n🔧 测试场景 3: 混合大小写格式")
    test_mixed_case()
    
    print("\n" + "="*100)
    print("修复说明：")
    print("✅ 支持DatabaseManager的RESULT/STATUS格式（大写）")
    print("✅ 支持标准的result/status格式（小写）")
    print("✅ 正确处理DatabaseManager的错误格式")
    print("✅ 显示实际的SQL执行结果数据")
    print("="*100)