"""
Enhanced progress tracker with ETA, accuracy tracking, and SQL visualization.
"""
import time
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import deque
from opensearch_sql.utils.loguru_config import get_logger

logger = get_logger(__name__)


class ProgressTracker:
    """
    Enhanced progress tracker with ETA calculation, accuracy tracking,
    and clear SQL output display.
    """
    
    def __init__(self, total_tasks: int, has_ground_truth: bool = False):
        """
        Initialize the progress tracker.
        
        Args:
            total_tasks: Total number of tasks to process
            has_ground_truth: Whether ground truth SQL is available for accuracy calculation
        """
        self.total_tasks = total_tasks
        self.has_ground_truth = has_ground_truth
        self.processed_tasks = 0
        self.start_time = time.time()
        
        # Accuracy tracking
        self.correct_executions = 0
        self.failed_executions = 0
        self.exact_matches = 0
        
        # ETA calculation
        self.task_times = deque(maxlen=20)  # Keep last 20 task times for rolling average
        self.last_task_time = self.start_time
        
        # SQL display
        self.current_sql = ""
        self.last_error = ""
        
        # Display settings
        self.last_display_time = 0
        self.display_interval = 0.5  # Update display every 0.5 seconds
        
    def update(self, 
               task_id: str,
               generated_sql: str = "",
               execution_status: str = "",
               is_exact_match: bool = False,
               error_message: str = ""):
        """
        Update progress with task results.
        
        Args:
            task_id: ID of the completed task
            generated_sql: The generated SQL query
            execution_status: Status of SQL execution (success/failed)
            is_exact_match: Whether generated SQL exactly matches ground truth
            error_message: Error message if execution failed
        """
        current_time = time.time()
        task_duration = current_time - self.last_task_time
        self.task_times.append(task_duration)
        self.last_task_time = current_time
        
        self.processed_tasks += 1
        self.current_sql = generated_sql
        
        # Update accuracy stats
        if execution_status == "success":
            self.correct_executions += 1
        elif execution_status == "failed":
            self.failed_executions += 1
            if error_message and not self._is_expected_error(error_message):
                self.last_error = error_message
                
        if is_exact_match:
            self.exact_matches += 1
            
        # Display progress
        self._display_progress(task_id)
        
    def _is_expected_error(self, error: str) -> bool:
        """
        Check if error is expected during SQL generation process.
        
        Args:
            error: Error message
            
        Returns:
            bool: True if error is expected/normal
        """
        expected_patterns = [
            "syntax error",
            "column .* does not exist",
            "table .* does not exist",
            "no such column",
            "ambiguous column",
            "aggregate function",
            "group by",
        ]
        
        error_lower = error.lower()
        return any(pattern in error_lower for pattern in expected_patterns)
        
    def _calculate_eta(self) -> str:
        """
        Calculate estimated time of arrival.
        
        Returns:
            str: Formatted ETA string
        """
        if not self.task_times or self.processed_tasks == 0:
            return "Calculating..."
            
        # Calculate rolling average time per task
        avg_task_time = sum(self.task_times) / len(self.task_times)
        
        # Calculate remaining time
        remaining_tasks = self.total_tasks - self.processed_tasks
        remaining_seconds = remaining_tasks * avg_task_time
        
        if remaining_seconds < 60:
            return f"{int(remaining_seconds)}s"
        elif remaining_seconds < 3600:
            minutes = int(remaining_seconds / 60)
            seconds = int(remaining_seconds % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(remaining_seconds / 3600)
            minutes = int((remaining_seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
            
    def _calculate_speed(self) -> str:
        """
        Calculate processing speed.
        
        Returns:
            str: Formatted speed string (tasks/min)
        """
        elapsed_time = time.time() - self.start_time
        if elapsed_time == 0:
            return "0"
            
        tasks_per_second = self.processed_tasks / elapsed_time
        tasks_per_minute = tasks_per_second * 60
        return f"{tasks_per_minute:.1f}"
    
    def _format_time(self, seconds: int) -> str:
        """
        Format time duration in a readable format.
        
        Args:
            seconds: Time duration in seconds
            
        Returns:
            str: Formatted time string
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m{secs:02d}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h{minutes:02d}m"
    
    def _parse_eta_to_seconds(self, eta_str: str) -> int:
        """
        Parse ETA string back to seconds for calculation.
        
        Args:
            eta_str: ETA string (e.g., "5m 30s", "1h 15m")
            
        Returns:
            int: ETA in seconds
        """
        if eta_str == "Calculating...":
            return 0
            
        total_seconds = 0
        
        # Parse different formats
        if "h" in eta_str:
            parts = eta_str.split("h")
            total_seconds += int(parts[0]) * 3600
            if "m" in parts[1]:
                minutes = parts[1].replace("m", "").strip()
                if minutes:
                    total_seconds += int(minutes) * 60
        elif "m" in eta_str:
            parts = eta_str.split("m")
            total_seconds += int(parts[0]) * 60
            if "s" in parts[1]:
                seconds = parts[1].replace("s", "").strip()
                if seconds:
                    total_seconds += int(seconds)
        elif "s" in eta_str:
            total_seconds += int(eta_str.replace("s", ""))
            
        return total_seconds
        
    def _display_progress(self, task_id: str):
        """
        Display enhanced progress information.
        
        Args:
            task_id: Current task ID
        """
        current_time = time.time()
        if current_time - self.last_display_time < self.display_interval:
            return
            
        self.last_display_time = current_time
        
        # Clear previous lines (up to 6 lines now)
        if self.processed_tasks > 1:
            for _ in range(6):
                sys.stdout.write('\033[1A\033[K')  # Move up and clear line
        
        # Line 1: Progress bar
        progress_ratio = self.processed_tasks / self.total_tasks
        bar_length = 50
        filled_length = int(bar_length * progress_ratio)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        percentage = progress_ratio * 100
        
        print(f"Progress: [{bar}] {percentage:.1f}% ({self.processed_tasks}/{self.total_tasks})")
        
        # Line 2: Time information and speed
        eta = self._calculate_eta()
        speed = self._calculate_speed()
        elapsed_seconds = int(time.time() - self.start_time)
        elapsed = self._format_time(elapsed_seconds)
        
        # Calculate total estimated time
        if eta != "Calculating..." and self.processed_tasks > 0:
            eta_seconds = self._parse_eta_to_seconds(eta)
            total_estimated = self._format_time(elapsed_seconds + eta_seconds)
            print(f"⏱️  已用: {elapsed} | 剩余: {eta} | 总计: ~{total_estimated} | 速度: {speed}/min")
        else:
            print(f"⏱️  已用: {elapsed} | 剩余: {eta} | 速度: {speed}/min")
        
        # Line 3: Current task
        print(f"🔄 当前任务: {task_id}")
        
        # Line 4: Accuracy (if ground truth available)
        if self.has_ground_truth and self.processed_tasks > 0:
            exec_accuracy = (self.correct_executions / self.processed_tasks) * 100
            exact_accuracy = (self.exact_matches / self.processed_tasks) * 100
            print(f"📊 准确率: 执行 {exec_accuracy:.1f}% | 精确 {exact_accuracy:.1f}% | ✓ {self.correct_executions} ✗ {self.failed_executions}")
        else:
            print(f"📊 状态: ✓ {self.correct_executions} 成功 | ✗ {self.failed_executions} 失败")
            
        # Line 5: Generated SQL (truncated if too long)
        if self.current_sql:
            sql_display = self.current_sql.replace('\n', ' ').strip()
            if len(sql_display) > 80:
                sql_display = sql_display[:77] + "..."
            print(f"🔧 SQL: {sql_display}")
        else:
            print("🔧 SQL: 正在生成...")
            
        # Line 6: Last error (if any, filtered)
        if self.last_error:
            error_display = self.last_error.replace('\n', ' ').strip()
            if len(error_display) > 80:
                error_display = error_display[:77] + "..."
            print(f"⚠️  提示: {error_display}")
        else:
            print("")  # Empty line for consistent spacing
            
        sys.stdout.flush()
        
    def finish(self):
        """
        Display final summary.
        """
        print("\n" + "="*80)
        print("EXECUTION SUMMARY")
        print("="*80)
        
        total_time = time.time() - self.start_time
        print(f"Total Tasks: {self.processed_tasks}/{self.total_tasks}")
        print(f"Total Time: {str(timedelta(seconds=int(total_time)))}")
        print(f"Average Speed: {(self.processed_tasks / total_time * 60):.1f} tasks/min")
        
        if self.processed_tasks > 0:
            print(f"\nExecution Results:")
            print(f"  Successful: {self.correct_executions} ({(self.correct_executions/self.processed_tasks*100):.1f}%)")
            print(f"  Failed: {self.failed_executions} ({(self.failed_executions/self.processed_tasks*100):.1f}%)")
            
            if self.has_ground_truth:
                print(f"\nAccuracy Metrics:")
                print(f"  Execution Accuracy: {(self.correct_executions/self.processed_tasks*100):.1f}%")
                print(f"  Exact Match Accuracy: {(self.exact_matches/self.processed_tasks*100):.1f}%")
                
        print("="*80)


class SQLFormatter:
    """
    Formatter for SQL output to improve readability.
    """
    
    @staticmethod
    def format_sql(sql: str, max_length: int = 150) -> str:
        """
        Format SQL for better display.
        
        Args:
            sql: SQL query string
            max_length: Maximum length before truncation
            
        Returns:
            str: Formatted SQL string
        """
        if not sql:
            return ""
            
        # Remove excessive whitespace
        sql = ' '.join(sql.split())
        
        # Add highlighting for SQL keywords
        keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 
                   'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'UNION', 'EXCEPT', 
                   'INTERSECT', 'AS', 'ON', 'AND', 'OR', 'NOT', 'IN', 'EXISTS']
        
        for keyword in keywords:
            sql = sql.replace(f' {keyword} ', f' \033[1;36m{keyword}\033[0m ')
            sql = sql.replace(f' {keyword.lower()} ', f' \033[1;36m{keyword}\033[0m ')
            
        # Truncate if too long
        if len(sql) > max_length:
            sql = sql[:max_length-3] + "..."
            
        return sql
        
    @staticmethod
    def format_error(error: str, max_length: int = 100) -> str:
        """
        Format error message for display.
        
        Args:
            error: Error message
            max_length: Maximum length before truncation
            
        Returns:
            str: Formatted error string
        """
        if not error:
            return ""
            
        # Extract key error information
        if "syntax error" in error.lower():
            return "Syntax error in SQL generation"
        elif "no such column" in error.lower() or "column .* does not exist" in error.lower():
            return "Column reference error"
        elif "no such table" in error.lower() or "table .* does not exist" in error.lower():
            return "Table reference error"
        elif "ambiguous" in error.lower():
            return "Ambiguous column reference"
        elif "aggregate" in error.lower() or "group by" in error.lower():
            return "Aggregation error"
        else:
            # Truncate generic errors
            error = error.replace('\n', ' ').strip()
            if len(error) > max_length:
                error = error[:max_length-3] + "..."
            return error


class ErrorFilter:
    """
    Filter for reducing noise from expected SQL generation errors.
    """
    
    def __init__(self):
        """Initialize error filter."""
        self.expected_patterns = [
            # Syntax errors during iterative SQL generation
            "syntax error",
            "parse error",
            "unexpected token",
            
            # Schema exploration errors
            "column .* does not exist",
            "table .* does not exist", 
            "no such column",
            "no such table",
            "unknown column",
            "unknown table",
            
            # SQL construction errors
            "ambiguous column",
            "aggregate function",
            "group by clause",
            "having clause",
            "subquery",
            
            # Type errors
            "type mismatch",
            "invalid type",
            "cannot compare",
            
            # Intermediate generation artifacts
            "incomplete sql",
            "placeholder",
            "TODO",
        ]
        
    def is_expected_error(self, error: str) -> bool:
        """
        Check if error is expected during SQL generation.
        
        Args:
            error: Error message
            
        Returns:
            bool: True if error is expected
        """
        if not error:
            return False
            
        error_lower = error.lower()
        return any(pattern in error_lower for pattern in self.expected_patterns)
        
    def should_log_error(self, error: str, node_type: str = "") -> bool:
        """
        Determine if error should be logged.
        
        Args:
            error: Error message
            node_type: Pipeline node where error occurred
            
        Returns:
            bool: True if error should be logged
        """
        # Always log errors in final nodes
        if node_type in ["vote", "evaluation"]:
            return True
            
        # Don't log expected errors in intermediate nodes
        if node_type in ["candidate_generate", "align_correct"] and self.is_expected_error(error):
            return False
            
        # Log unexpected errors
        return not self.is_expected_error(error)