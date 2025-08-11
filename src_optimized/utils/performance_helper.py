"""
Performance monitoring and profiling utilities for OpenSearch-SQL pipeline.
"""
import time
import logging
import functools
import psutil
import os
from typing import Dict, Any, Callable, Optional
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    execution_time: float
    memory_usage_mb: float
    cpu_percent: float
    peak_memory_mb: Optional[float] = None
    function_calls: int = 1


class PerformanceHelper:
    """
    Helper class for monitoring and profiling performance.
    """
    
    @staticmethod
    def get_memory_usage() -> float:
        """
        Get current memory usage in MB.
        
        Returns:
            float: Memory usage in MB.
        """
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            return memory_info.rss / 1024 / 1024  # Convert to MB
        except Exception:
            return 0.0
    
    @staticmethod
    def get_cpu_percent() -> float:
        """
        Get current CPU usage percentage.
        
        Returns:
            float: CPU usage percentage.
        """
        try:
            return psutil.cpu_percent(interval=0.1)
        except Exception:
            return 0.0
    
    @staticmethod
    def profile_function(func: Callable, track_memory: bool = True, 
                        track_cpu: bool = True) -> Callable:
        """
        Decorator to profile function execution.
        
        Args:
            func (Callable): Function to profile.
            track_memory (bool): Whether to track memory usage.
            track_cpu (bool): Whether to track CPU usage.
            
        Returns:
            Callable: Wrapped function with profiling.
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get initial metrics
            start_time = time.time()
            initial_memory = PerformanceHelper.get_memory_usage() if track_memory else 0.0
            peak_memory = initial_memory
            
            # Monitor memory usage during execution
            if track_memory:
                original_memory_check = PerformanceHelper._memory_monitor
                PerformanceHelper._memory_monitor = lambda: max(peak_memory, PerformanceHelper.get_memory_usage())
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Get final metrics
                end_time = time.time()
                execution_time = end_time - start_time
                
                final_memory = PerformanceHelper.get_memory_usage() if track_memory else 0.0
                memory_usage = max(0, final_memory - initial_memory)
                
                cpu_percent = PerformanceHelper.get_cpu_percent() if track_cpu else 0.0
                
                # Create metrics object
                metrics = PerformanceMetrics(
                    execution_time=execution_time,
                    memory_usage_mb=memory_usage,
                    cpu_percent=cpu_percent,
                    peak_memory_mb=peak_memory if track_memory else None
                )
                
                # Log performance info
                PerformanceHelper._log_performance(func.__name__, metrics)
                
                # Store metrics on the result if possible
                if hasattr(result, '__dict__'):
                    result._performance_metrics = metrics
                
                return result
                
            finally:
                # Reset memory monitor
                if track_memory:
                    PerformanceHelper._memory_monitor = original_memory_check
        
        return wrapper
    
    @staticmethod
    def _memory_monitor():
        """Default memory monitor function."""
        return PerformanceHelper.get_memory_usage()
    
    @staticmethod
    def _log_performance(function_name: str, metrics: PerformanceMetrics):
        """
        Log performance metrics.
        
        Args:
            function_name (str): Name of the function.
            metrics (PerformanceMetrics): Performance metrics.
        """
        logging.debug(
            f"Performance - {function_name}: "
            f"time={metrics.execution_time:.2f}s, "
            f"memory={metrics.memory_usage_mb:.1f}MB, "
            f"cpu={metrics.cpu_percent:.1f}%"
        )
    
    @staticmethod
    @contextmanager
    def performance_context(operation_name: str, log_level: str = "info"):
        """
        Context manager for measuring performance of code blocks.
        
        Args:
            operation_name (str): Name of the operation being measured.
            log_level (str): Logging level for results.
        """
        start_time = time.time()
        initial_memory = PerformanceHelper.get_memory_usage()
        
        try:
            yield
        finally:
            end_time = time.time()
            execution_time = end_time - start_time
            final_memory = PerformanceHelper.get_memory_usage()
            memory_usage = max(0, final_memory - initial_memory)
            
            log_func = getattr(logging, log_level.lower(), logging.info)
            log_func(
                f"Performance - {operation_name}: "
                f"time={execution_time:.2f}s, memory={memory_usage:.1f}MB"
            )
    
    @staticmethod
    def create_performance_report(metrics_list: list) -> Dict[str, Any]:
        """
        Create a comprehensive performance report.
        
        Args:
            metrics_list (list): List of PerformanceMetrics objects.
            
        Returns:
            Dict[str, Any]: Performance report.
        """
        if not metrics_list:
            return {"error": "No metrics provided"}
        
        execution_times = [m.execution_time for m in metrics_list]
        memory_usages = [m.memory_usage_mb for m in metrics_list]
        cpu_usages = [m.cpu_percent for m in metrics_list]
        
        report = {
            "total_operations": len(metrics_list),
            "execution_time": {
                "total": sum(execution_times),
                "average": sum(execution_times) / len(execution_times),
                "min": min(execution_times),
                "max": max(execution_times)
            },
            "memory_usage_mb": {
                "total": sum(memory_usages),
                "average": sum(memory_usages) / len(memory_usages),
                "min": min(memory_usages),
                "max": max(memory_usages)
            },
            "cpu_percent": {
                "average": sum(cpu_usages) / len(cpu_usages),
                "min": min(cpu_usages),
                "max": max(cpu_usages)
            }
        }
        
        # Add peak memory if available
        peak_memories = [m.peak_memory_mb for m in metrics_list if m.peak_memory_mb is not None]
        if peak_memories:
            report["peak_memory_mb"] = {
                "max": max(peak_memories),
                "average": sum(peak_memories) / len(peak_memories)
            }
        
        return report


def profile_function(track_memory: bool = True, track_cpu: bool = True):
    """
    Decorator function for profiling function execution.
    
    Args:
        track_memory (bool): Whether to track memory usage.
        track_cpu (bool): Whether to track CPU usage.
        
    Returns:
        Callable: Decorator function.
    """
    def decorator(func: Callable) -> Callable:
        return PerformanceHelper.profile_function(func, track_memory, track_cpu)
    return decorator


class PerformanceMonitor:
    """
    Class for monitoring pipeline performance over time.
    """
    
    def __init__(self):
        """Initialize the performance monitor."""
        self.metrics_history = []
        self.node_metrics = {}
        self.start_time = None
        self.end_time = None
    
    def start_monitoring(self):
        """Start monitoring performance."""
        self.start_time = time.time()
        logging.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring performance."""
        self.end_time = time.time()
        logging.info("Performance monitoring stopped")
    
    def record_node_metrics(self, node_name: str, metrics: PerformanceMetrics):
        """
        Record metrics for a specific pipeline node.
        
        Args:
            node_name (str): Name of the pipeline node.
            metrics (PerformanceMetrics): Performance metrics.
        """
        if node_name not in self.node_metrics:
            self.node_metrics[node_name] = []
        
        self.node_metrics[node_name].append(metrics)
        self.metrics_history.append((node_name, metrics))
    
    def get_node_summary(self, node_name: str) -> Optional[Dict[str, Any]]:
        """
        Get performance summary for a specific node.
        
        Args:
            node_name (str): Name of the pipeline node.
            
        Returns:
            Optional[Dict[str, Any]]: Performance summary or None if no data.
        """
        if node_name not in self.node_metrics:
            return None
        
        metrics_list = self.node_metrics[node_name]
        return PerformanceHelper.create_performance_report(metrics_list)
    
    def get_overall_summary(self) -> Dict[str, Any]:
        """
        Get overall performance summary.
        
        Returns:
            Dict[str, Any]: Overall performance summary.
        """
        all_metrics = []
        for metrics_list in self.node_metrics.values():
            all_metrics.extend(metrics_list)
        
        summary = PerformanceHelper.create_performance_report(all_metrics)
        
        if self.start_time and self.end_time:
            summary["total_pipeline_time"] = self.end_time - self.start_time
        
        summary["nodes_executed"] = list(self.node_metrics.keys())
        summary["total_node_executions"] = len(all_metrics)
        
        return summary
    
    def print_summary(self):
        """Print a formatted performance summary."""
        print("\n" + "="*60)
        print("PERFORMANCE SUMMARY")
        print("="*60)
        
        overall = self.get_overall_summary()
        
        if "total_pipeline_time" in overall:
            print(f"Total Pipeline Time: {overall['total_pipeline_time']:.2f}s")
        
        print(f"Total Node Executions: {overall['total_node_executions']}")
        print(f"Average Execution Time: {overall['execution_time']['average']:.2f}s")
        print(f"Total Memory Usage: {overall['memory_usage_mb']['total']:.1f}MB")
        
        print("\nPer-Node Performance:")
        for node_name in overall['nodes_executed']:
            node_summary = self.get_node_summary(node_name)
            if node_summary:
                print(f"  {node_name}:")
                print(f"    Executions: {node_summary['total_operations']}")
                print(f"    Avg Time: {node_summary['execution_time']['average']:.2f}s")
                print(f"    Avg Memory: {node_summary['memory_usage_mb']['average']:.1f}MB")
        
        print("="*60)


if __name__ == "__main__":
    # Example usage
    @profile_function(track_memory=True, track_cpu=True)
    def example_function(n: int = 1000000):
        """Example function to profile."""
        return sum(i * i for i in range(n))
    
    # Test the profiling
    with PerformanceHelper.performance_context("Example Operation"):
        result = example_function()
        print(f"Result: {result}")
    
    # Test performance monitor
    monitor = PerformanceMonitor()
    monitor.start_monitoring()
    
    # Simulate some work
    time.sleep(0.1)
    
    monitor.stop_monitoring()
    monitor.print_summary()