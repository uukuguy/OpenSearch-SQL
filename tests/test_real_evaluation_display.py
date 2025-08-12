#!/usr/bin/env python3
"""
测试脚本：使用真实的evaluation数据格式测试结果显示。
"""
from src_optimized.utils.task_result_formatter import TaskResultLogger

def test_real_evaluation_data():
    """使用真实evaluation节点数据测试显示。"""
    logger = TaskResultLogger()
    
    # 基于您提供的真实数据格式
    evaluation_results = {
        "exec_err": "incorrect answer",
        "execution_match": False,
        "predicted_sql": "SELECT \n    f.`School Name`, \n    f.`District Name`, \n    f.`County Name` \nFROM frpm AS f \nJOIN satscores AS s ON f.CDSCode = s.cds \nJOIN schools AS sc ON f.CDSCode = sc.CDSCode \nWHERE s.NumTstTakr > 500 \n  AND sc.Magnet = 1",
        "ground_truth_sql": "SELECT T2.School FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode WHERE T2.Magnet = 1 AND T1.NumTstTakr > 500",
        "predicted_result": {
            "SQL": "SELECT \n    f.`School Name`, \n    f.`District Name`, \n    f.`County Name` \nFROM frpm AS f \nJOIN satscores AS s ON f.CDSCode = s.cds \nJOIN schools AS sc ON f.CDSCode = sc.CDSCode \nWHERE s.NumTstTakr > 500 \n  AND sc.Magnet = 1",
            "result": [
                ["Lowell High", "San Francisco Unified", "San Francisco"],
                ["Lincoln High", "San Francisco Unified", "San Francisco"],
                ["Washington High", "Fremont Unified", "Alameda"]
            ],
            "execution_time": 0.15,
            "status": "success"
        },
        "ground_truth_result": {
            "SQL": "SELECT T2.School FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode WHERE T2.Magnet = 1 AND T1.NumTstTakr > 500",
            "result": [
                ["Lowell High"],
                ["Lincoln High"],
                ["Washington High"],
                ["Roosevelt High"],
                ["Jefferson High"]
            ],
            "execution_time": 0.08,
            "status": "success"
        },
        "syntax_evaluation": {
            "syntax_correct": True,
            "issues": [],
            "sql_length": 245,
            "complexity_score": 0.7
        },
        "overall_score": 0.2,
        "evaluation_summary": "✗ Execution: FAILED (incorrect answer) | ✓ Syntax: CORRECT | Score: 0.2/1.0"
    }
    
    logger.log_task_result(
        task_id="california_schools#6",
        question="Among the schools with the SAT test takers of over 500, please list the schools that are magnet schools or offer a magnet program. Magnet schools or offer a magnet program means that Magnet = 1",
        generated_sql="SELECT f.`School Name`, f.`District Name`, f.`County Name` FROM frpm AS f JOIN satscores AS s ON f.CDSCode = s.cds JOIN schools AS sc ON f.CDSCode = sc.CDSCode WHERE s.NumTstTakr > 500 AND sc.Magnet = 1",
        ground_truth_sql="SELECT T2.School FROM satscores AS T1 INNER JOIN schools AS T2 ON T1.cds = T2.CDSCode WHERE T2.Magnet = 1 AND T1.NumTstTakr > 500",
        execution_status="failed",
        evaluation_results=evaluation_results,
        processing_time=54.53
    )

def test_high_score_example():
    """测试高分例子。"""
    logger = TaskResultLogger()
    
    evaluation_results = {
        "execution_match": True,
        "predicted_result": {
            "result": [
                ["John Smith", 25],
                ["Jane Doe", 30],
                ["Bob Johnson", 35]
            ],
            "status": "success"
        },
        "ground_truth_result": {
            "result": [
                ["John Smith", 25],
                ["Jane Doe", 30], 
                ["Bob Johnson", 35]
            ],
            "status": "success"
        },
        "syntax_evaluation": {
            "syntax_correct": True,
            "issues": [],
            "sql_length": 56
        },
        "overall_score": 0.95,
        "evaluation_summary": "✓ Execution: SUCCESS (perfect match) | ✓ Syntax: CORRECT | Score: 0.95/1.0",
        "f1_score": 0.95,
        "precision": 1.0,
        "recall": 0.9
    }
    
    logger.log_task_result(
        task_id="simple_query#123",
        question="List all employees with their ages.",
        generated_sql="SELECT name, age FROM employees",
        ground_truth_sql="SELECT name, age FROM employees",
        execution_status="success",
        evaluation_results=evaluation_results,
        processing_time=3.2
    )

def test_syntax_error_example():
    """测试语法错误例子。"""
    logger = TaskResultLogger()
    
    evaluation_results = {
        "execution_match": False,
        "exec_err": "syntax error",
        "predicted_result": {
            "error": "syntax error near 'SELCT'",
            "status": "error"
        },
        "ground_truth_result": {
            "result": [["Product A", 1000], ["Product B", 1500]],
            "status": "success"
        },
        "syntax_evaluation": {
            "syntax_correct": False,
            "issues": [
                "Invalid keyword 'SELCT' (should be 'SELECT')",
                "Missing FROM clause"
            ],
            "sql_length": 45
        },
        "overall_score": 0.0,
        "evaluation_summary": "✗ Execution: FAILED (syntax error) | ✗ Syntax: INCORRECT | Score: 0.0/1.0"
    }
    
    logger.log_task_result(
        task_id="syntax_error#456",
        question="Get total sales by product.",
        generated_sql="SELCT product, SUM(sales) GROUP BY product",
        ground_truth_sql="SELECT product, SUM(sales) FROM sales GROUP BY product",
        execution_status="failed",
        evaluation_results=evaluation_results,
        processing_time=8.7,
        error_message="SQL syntax error: 'SELCT' is not a valid keyword"
    )

if __name__ == "__main__":
    print("="*100)
    print("演示：基于真实evaluation数据的结果显示")
    print("="*100)
    
    print("\n📊 测试场景 1: 真实evaluation数据 (score=0.2, 执行结果不匹配)")
    test_real_evaluation_data()
    
    print("\n📊 测试场景 2: 高分例子 (score=0.95, 完美匹配)")
    test_high_score_example()
    
    print("\n📊 测试场景 3: 语法错误 (score=0.0, 语法错误)")
    test_syntax_error_example()
    
    print("\n" + "="*100)
    print("现在显示的信息包括：")
    print("✅ evaluation节点的overall_score (带颜色标识)")
    print("✅ evaluation_summary (完整的评估摘要)")
    print("✅ 实际SQL执行结果对比 (predicted_result vs ground_truth_result)")
    print("✅ 语法检查结果 (syntax_evaluation)")
    print("✅ 执行错误类型 (exec_err)")
    print("✅ 其他评估指标 (F1分数、精确率等)")
    print("="*100)