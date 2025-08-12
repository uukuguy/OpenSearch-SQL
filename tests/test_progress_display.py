#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced progress display and SQL formatting.
"""
import time
import random
from src_optimized.utils.progress_tracker import ProgressTracker, SQLFormatter, ErrorFilter

def generate_sample_sql():
    """Generate a sample SQL query."""
    queries = [
        "SELECT name, age FROM users WHERE age > 25 ORDER BY age DESC",
        "SELECT COUNT(*) as total, AVG(price) as avg_price FROM products GROUP BY category HAVING COUNT(*) > 10",
        "SELECT u.name, o.order_date, o.total FROM users u LEFT JOIN orders o ON u.id = o.user_id WHERE o.status = 'completed'",
        "SELECT * FROM employees WHERE department IN (SELECT id FROM departments WHERE location = 'NYC')",
        "SELECT product_name, SUM(quantity) as total_sold FROM sales GROUP BY product_name ORDER BY total_sold DESC LIMIT 10"
    ]
    return random.choice(queries)

def generate_sample_error():
    """Generate a sample error message."""
    errors = [
        "column users.email does not exist",
        "syntax error near 'SELCT'",
        "table orders_2024 does not exist",
        "ambiguous column reference: name",
        "aggregate function requires GROUP BY clause",
        ""  # No error
    ]
    return random.choice(errors)

def test_progress_tracker():
    """Test the enhanced progress tracker."""
    print("Testing Enhanced Progress Tracker")
    print("=" * 80)
    print("\nThis demonstrates:")
    print("1. Real-time progress with ETA calculation")
    print("2. Accuracy tracking (when ground truth is available)")
    print("3. Clear SQL display with truncation")
    print("4. Filtered error messages")
    print("\n" + "=" * 80 + "\n")
    
    # Initialize tracker
    total_tasks = 50
    tracker = ProgressTracker(total_tasks=total_tasks, has_ground_truth=True)
    
    # Simulate task processing
    for i in range(total_tasks):
        # Simulate task processing time
        time.sleep(random.uniform(0.1, 0.3))
        
        # Generate sample data
        task_id = f"db_{i//10}#q_{i}"
        sql = generate_sample_sql()
        error = generate_sample_error()
        
        # Determine execution status
        if error:
            status = "failed"
            is_exact = False
        else:
            status = "success"
            is_exact = random.random() > 0.7  # 30% exact match
        
        # Update tracker
        tracker.update(
            task_id=task_id,
            generated_sql=sql,
            execution_status=status,
            is_exact_match=is_exact,
            error_message=error
        )
    
    # Show final summary
    tracker.finish()
    
def test_sql_formatter():
    """Test SQL formatting."""
    print("\n\nTesting SQL Formatter")
    print("=" * 80)
    
    formatter = SQLFormatter()
    
    test_queries = [
        "select name, age from users where age > 25 order by age desc",
        "SELECT COUNT(*) as total, AVG(price) as avg_price FROM products GROUP BY category HAVING COUNT(*) > 10",
        "SELECT u.name, o.order_date, o.total FROM users u LEFT JOIN orders o ON u.id = o.user_id WHERE o.status = 'completed' AND o.order_date > '2024-01-01' ORDER BY o.order_date DESC LIMIT 100"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\nQuery {i} (Original):")
        print(query)
        print(f"\nQuery {i} (Formatted):")
        print(formatter.format_sql(query))
        print("-" * 40)

def test_error_filter():
    """Test error filtering."""
    print("\n\nTesting Error Filter")
    print("=" * 80)
    
    filter = ErrorFilter()
    
    test_errors = [
        ("syntax error near SELECT", "candidate_generate"),
        ("column users.email does not exist", "candidate_generate"),
        ("division by zero", "evaluation"),
        ("table not found", "align_correct"),
        ("connection timeout", "vote")
    ]
    
    for error, node in test_errors:
        should_log = filter.should_log_error(error, node)
        is_expected = filter.is_expected_error(error)
        print(f"\nError: '{error}'")
        print(f"Node: {node}")
        print(f"Is Expected: {is_expected}")
        print(f"Should Log: {should_log}")
        print("-" * 40)

if __name__ == "__main__":
    # Run tests
    test_progress_tracker()
    test_sql_formatter()
    test_error_filter()
    
    print("\n\nAll tests completed!")
    print("The enhanced display system provides:")
    print("✓ Clear progress visualization with ETA")
    print("✓ Real-time accuracy tracking")
    print("✓ Formatted SQL output for better readability")
    print("✓ Intelligent error filtering to reduce noise")