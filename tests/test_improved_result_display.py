#!/usr/bin/env python3
"""
测试脚本：演示基于evaluation节点的改进结果显示。
"""
from src_optimized.utils.task_result_formatter import TaskResultLogger

def test_execution_success():
    """测试SQL执行验证成功的情况。"""
    logger = TaskResultLogger()
    
    logger.log_task_result(
        task_id="california_schools#15",
        question="Find all schools in California that have more than 1000 students and their average test scores.",
        generated_sql="SELECT school_name, student_count, avg_test_score FROM schools WHERE state = 'CA' AND student_count > 1000",
        ground_truth_sql="SELECT name, enrollment, average_score FROM educational_institutions WHERE state_code = 'CA' AND enrollment > 1000",
        execution_status="success",
        evaluation_results={
            "exec_res": 1,  # 关键指标：执行结果一致
            "execution_accuracy": 0.95,
            "f1_score": 0.88,
            "precision": 0.92,
            "recall": 0.85,
            "result_similarity": 0.94
        },
        processing_time=18.3
    )

def test_execution_failure():
    """测试SQL执行验证失败的情况。"""
    logger = TaskResultLogger()
    
    logger.log_task_result(
        task_id="bird_db#234", 
        question="What is the total revenue for each product category in 2023?",
        generated_sql="SELECT category, SUM(price * quantity) FROM products p JOIN sales s ON p.id = s.product_id WHERE year = 2023 GROUP BY category",
        ground_truth_sql="SELECT c.category_name, SUM(s.amount) FROM categories c JOIN products p ON c.id = p.category_id JOIN sales s ON p.id = s.product_id WHERE YEAR(s.sale_date) = 2023 GROUP BY c.category_name",
        execution_status="failed",
        evaluation_results={
            "exec_res": 0,  # 关键指标：执行结果不一致
            "execution_accuracy": 0.0,
            "error": "Column 'year' doesn't exist in sales table",
            "generated_result_count": 0,
            "expected_result_count": 8
        },
        processing_time=12.7,
        error_message="Column 'year' doesn't exist in sales table. Available columns: sale_date, amount, product_id"
    )

def test_partial_correctness():
    """测试部分正确的情况（生成了结果，但与标准答案有差异）。"""
    logger = TaskResultLogger()
    
    logger.log_task_result(
        task_id="spider_dev#156",
        question="Show the names and ages of the top 5 oldest employees.",
        generated_sql="SELECT name, age FROM employees ORDER BY age DESC LIMIT 5",
        ground_truth_sql="SELECT first_name, last_name, age FROM employees ORDER BY age DESC LIMIT 5",
        execution_status="success", 
        evaluation_results={
            "exec_res": 0,  # 执行成功但结果不完全匹配
            "execution_accuracy": 0.6,  # 部分正确
            "f1_score": 0.75,
            "precision": 0.8,
            "recall": 0.7,
            "result_similarity": 0.75,
            "generated_result_count": 5,
            "expected_result_count": 5,
            "matching_rows": 3  # 5行中有3行匹配
        },
        processing_time=8.9
    )

def test_syntax_error():
    """测试SQL语法错误的情况。"""
    logger = TaskResultLogger()
    
    logger.log_task_result(
        task_id="complex_db#789",
        question="Find customers who have made purchases in both 2022 and 2023.",
        generated_sql="SELECT customer_id FROM orders WHERE YEAR(order_date) = 2022 INTERSECT SELECT customer_id FROM orders WHERE YEAR(order_date) = 2023",
        ground_truth_sql="SELECT DISTINCT o1.customer_id FROM orders o1 JOIN orders o2 ON o1.customer_id = o2.customer_id WHERE YEAR(o1.order_date) = 2022 AND YEAR(o2.order_date) = 2023",
        execution_status="failed",
        evaluation_results={
            "exec_res": 0,
            "execution_accuracy": 0.0,
            "error": "INTERSECT is not supported in this SQL engine",
            "syntax_valid": False,
            "execution_time": 0.0
        },
        processing_time=15.2,
        error_message="SQL syntax not supported: INTERSECT operator not available in SQLite"
    )

def test_perfect_match():
    """测试完全匹配的情况。"""
    logger = TaskResultLogger()
    
    sql = "SELECT customer_name, total_orders FROM customers c JOIN (SELECT customer_id, COUNT(*) as total_orders FROM orders GROUP BY customer_id) o ON c.id = o.customer_id ORDER BY total_orders DESC"
    
    logger.log_task_result(
        task_id="benchmark#001",
        question="List customers and their total number of orders, sorted by order count descending.",
        generated_sql=sql,
        ground_truth_sql=sql,
        execution_status="success",
        evaluation_results={
            "exec_res": 1,  # 完全匹配
            "execution_accuracy": 1.0,
            "f1_score": 1.0,
            "precision": 1.0,
            "recall": 1.0,
            "result_similarity": 1.0,
            "exact_match": 1,
            "generated_result_count": 47,
            "expected_result_count": 47
        },
        processing_time=6.8
    )

if __name__ == "__main__":
    print("="*100)
    print("演示：基于evaluation节点的改进任务结果显示")
    print("="*100)
    
    print("\n🎯 测试场景 1: SQL执行验证成功（生成SQL与标准SQL执行结果一致）")
    test_execution_success()
    
    print("\n🎯 测试场景 2: SQL执行验证失败（结果不一致）")
    test_execution_failure()
    
    print("\n🎯 测试场景 3: 部分正确（执行成功但结果有差异）")
    test_partial_correctness()
    
    print("\n🎯 测试场景 4: SQL语法错误")
    test_syntax_error()
    
    print("\n🎯 测试场景 5: 完全匹配")
    test_perfect_match()
    
    print("\n" + "="*100)
    print("改进总结")
    print("="*100)
    print("✅ 重点展示evaluation节点的执行验证结果")
    print("✅ 显示SQL执行结果是否与标准SQL一致（exec_res）")
    print("✅ 展示有意义的评估指标（F1分数、精确率、召回率等）")
    print("✅ 移除了无意义的字面SQL文本比较")
    print("✅ 突出显示实际的执行错误和结果差异")
    print("✅ 提供更有价值的性能评估信息")
    print("="*100)