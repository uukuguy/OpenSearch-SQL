#!/usr/bin/env python3
"""
测试脚本：演示增强的任务结果显示功能。
"""
from src_optimized.utils.task_result_formatter import TaskResultLogger

def test_successful_task():
    """测试成功完成的任务显示。"""
    logger = TaskResultLogger()
    
    logger.log_task_result(
        task_id="california_schools#1",
        question="What are the names of all schools in California with more than 1000 students?",
        generated_sql="SELECT school_name FROM schools WHERE state = 'California' AND student_count > 1000",
        ground_truth_sql="SELECT school_name FROM schools WHERE state = 'CA' AND student_count > 1000",
        execution_status="success",
        evaluation_results={
            "exec_res": 1,
            "execution_accuracy": 0.95,
            "exact_match": 0,
            "semantic_similarity": 0.88
        },
        processing_time=12.5,
        error_message=""
    )

def test_failed_task():
    """测试失败的任务显示。"""
    logger = TaskResultLogger()
    
    logger.log_task_result(
        task_id="bird_1#156",
        question="Find the average salary of employees in the engineering department who have worked for more than 5 years.",
        generated_sql="SELECT AVG(salary) FROM employee WHERE department = 'engineering' AND years_worked > 5",
        ground_truth_sql="SELECT AVG(e.salary) FROM employees e JOIN departments d ON e.dept_id = d.id WHERE d.name = 'Engineering' AND e.years_experience > 5",
        execution_status="failed",
        evaluation_results={
            "exec_res": 0,
            "execution_accuracy": 0.0,
            "exact_match": 0,
            "error": "Table 'employee' doesn't exist"
        },
        processing_time=8.3,
        error_message="Table 'employee' doesn't exist. Available tables: employees, departments"
    )

def test_partial_success():
    """测试部分成功的任务显示。"""
    logger = TaskResultLogger()
    
    logger.log_task_result(
        task_id="spider_dev#89",
        question="Show me the total number of products sold by each category, ordered by count descending.",
        generated_sql="SELECT category, SUM(quantity_sold) as total_sold FROM products p JOIN sales s ON p.id = s.product_id GROUP BY category ORDER BY total_sold DESC",
        ground_truth_sql="SELECT p.category, SUM(s.quantity) as total_quantity FROM products p JOIN sales s ON p.product_id = s.product_id GROUP BY p.category ORDER BY total_quantity DESC",
        execution_status="success",
        evaluation_results={
            "exec_res": 1,
            "execution_accuracy": 1.0,
            "exact_match": 0,
            "semantic_similarity": 0.92,
            "result_similarity": 0.85
        },
        processing_time=15.8,
        error_message=""
    )

def test_no_sql_generated():
    """测试没有生成SQL的情况。"""
    logger = TaskResultLogger()
    
    logger.log_task_result(
        task_id="complex_db#999",
        question="This is a very complex question that requires understanding of multiple table relationships and advanced SQL features.",
        generated_sql="",
        ground_truth_sql="SELECT COMPLEX_QUERY_HERE",
        execution_status="failed",
        evaluation_results={
            "exec_res": 0,
            "execution_accuracy": 0.0,
            "generation_failed": True
        },
        processing_time=30.2,
        error_message="SQL generation timeout - query too complex"
    )

def test_exact_match():
    """测试完全匹配的情况。"""
    logger = TaskResultLogger()
    
    sql = "SELECT name, age FROM users WHERE age > 21 ORDER BY name"
    
    logger.log_task_result(
        task_id="simple_query#42",
        question="Get names and ages of users older than 21, sorted by name.",
        generated_sql=sql,
        ground_truth_sql=sql,
        execution_status="success",
        evaluation_results={
            "exec_res": 1,
            "execution_accuracy": 1.0,
            "exact_match": 1,
            "semantic_similarity": 1.0
        },
        processing_time=3.1,
        error_message=""
    )

if __name__ == "__main__":
    print("="*100)
    print("演示：增强的任务结果显示功能")
    print("="*100)
    
    print("\n📋 测试场景 1: 成功执行但SQL不完全匹配")
    test_successful_task()
    
    print("\n📋 测试场景 2: 执行失败，有错误信息")
    test_failed_task()
    
    print("\n📋 测试场景 3: 执行成功，语义相似")
    test_partial_success()
    
    print("\n📋 测试场景 4: SQL生成失败")
    test_no_sql_generated()
    
    print("\n📋 测试场景 5: 完全匹配")
    test_exact_match()
    
    print("\n" + "="*100)
    print("演示完成！")
    print("\n现在每个任务完成时都会显示：")
    print("✅ 问题内容（自动换行）")
    print("✅ 生成的SQL（格式化显示）") 
    print("✅ 标准SQL（如果有）")
    print("✅ SQL匹配状态（完全匹配/不匹配）")
    print("✅ 执行状态（成功/失败）")
    print("✅ 评估结果（准确率、得分等）")
    print("✅ 处理时间")
    print("✅ 错误信息（如果有）")
    print("="*100)