"""
Unified loguru configuration system for OpenSearch-SQL pipeline.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger


class LoguruConfig:
    """
    Centralized loguru configuration manager.
    Provides consistent logging setup across the entire pipeline.
    """
    
    _configured = False
    _log_directory = None
    
    @classmethod
    def setup(cls, 
              log_level: str = "INFO",
              log_directory: Optional[str] = None,
              log_to_file: bool = True,
              log_to_console: bool = True,
              rotation: str = "10 MB",
              retention: str = "7 days",
              compression: str = "zip",
              colorize: bool = True) -> None:
        """
        Configure loguru with optimized settings for OpenSearch-SQL pipeline.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            log_directory: Directory for log files (auto-generated if None)
            log_to_file: Whether to log to file
            log_to_console: Whether to log to console
            rotation: File rotation policy
            retention: How long to keep logs
            compression: Compression method for rotated logs
            colorize: Whether to colorize console output
        """
        if cls._configured:
            return
            
        # Remove default handler
        logger.remove()
        
        # Setup console logging
        if log_to_console:
            console_format = (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            )
            
            logger.add(
                sys.stdout,
                format=console_format,
                level=log_level,
                colorize=colorize,
                backtrace=True,
                diagnose=True,
                catch=True
            )
        
        # Setup file logging
        if log_to_file:
            if log_directory is None:
                # Create logs directory in results folder
                log_directory = Path("logs")
                log_directory.mkdir(exist_ok=True)
            else:
                log_directory = Path(log_directory)
                log_directory.mkdir(parents=True, exist_ok=True)
            
            cls._log_directory = log_directory
            
            # Main log file
            main_log_file = log_directory / "opensearch_sql.log"
            file_format = (
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}"
            )
            
            logger.add(
                str(main_log_file),
                format=file_format,
                level=log_level,
                rotation=rotation,
                retention=retention,
                compression=compression,
                backtrace=True,
                diagnose=True,
                catch=True,
                enqueue=True  # Thread-safe logging
            )
            
            # Error-only log file
            error_log_file = log_directory / "errors.log"
            logger.add(
                str(error_log_file),
                format=file_format,
                level="ERROR",
                rotation=rotation,
                retention=retention,
                compression=compression,
                backtrace=True,
                diagnose=True,
                catch=True,
                enqueue=True
            )
        
        cls._configured = True
        logger.info(f"Loguru configured successfully - Level: {log_level}, Directory: {cls._log_directory}")
    
    @classmethod
    def get_logger(cls, name: str = None):
        """
        Get a logger instance with optional name binding.
        
        Args:
            name: Logger name for identification
            
        Returns:
            Configured logger instance
        """
        if not cls._configured:
            cls.setup()
        
        if name:
            return logger.bind(name=name)
        return logger
    
    @classmethod
    def create_node_logger(cls, node_name: str):
        """
        Create a specialized logger for pipeline nodes.
        
        Args:
            node_name: Name of the pipeline node
            
        Returns:
            Logger configured for the specific node
        """
        return cls.get_logger(f"node.{node_name}")
    
    @classmethod
    def create_service_logger(cls, service_name: str):
        """
        Create a specialized logger for services.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Logger configured for the specific service
        """
        return cls.get_logger(f"service.{service_name}")
    
    @classmethod
    def create_performance_logger(cls):
        """
        Create a specialized logger for performance metrics.
        
        Returns:
            Logger configured for performance logging
        """
        if not cls._configured:
            cls.setup()
            
        if cls._log_directory:
            perf_log_file = cls._log_directory / "performance.log"
            
            # Add performance-specific handler
            logger.add(
                str(perf_log_file),
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | PERF | {message}",
                level="INFO",
                rotation="50 MB",
                retention="30 days",
                compression="zip",
                filter=lambda record: "PERF" in record.get("extra", {}),
                enqueue=True
            )
        
        return logger.bind(PERF=True)
    
    @classmethod
    def log_performance_metric(cls, metric_name: str, value: Any, unit: str = "", extra_data: Dict = None):
        """
        Log performance metrics in a structured format.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Unit of measurement
            extra_data: Additional context data
        """
        perf_logger = cls.create_performance_logger()
        extra_info = f" ({extra_data})" if extra_data else ""
        perf_logger.info(f"{metric_name}: {value}{unit}{extra_info}")
    
    @classmethod
    def get_log_directory(cls) -> Optional[Path]:
        """Get the configured log directory."""
        return cls._log_directory
    
    @classmethod
    def reset_configuration(cls):
        """Reset the configuration (mainly for testing)."""
        cls._configured = False
        cls._log_directory = None
        logger.remove()


# Convenience functions for easy import
def get_logger(name: str = None):
    """Get a configured logger instance."""
    return LoguruConfig.get_logger(name)


def setup_logging(log_level: str = "INFO", **kwargs):
    """Setup loguru with specified configuration."""
    LoguruConfig.setup(log_level=log_level, **kwargs)


def log_performance(metric_name: str, value: Any, unit: str = "", **extra):
    """Log a performance metric."""
    LoguruConfig.log_performance_metric(metric_name, value, unit, extra)


# Create commonly used loggers
pipeline_logger = lambda: LoguruConfig.get_logger("pipeline")
service_logger = lambda name: LoguruConfig.create_service_logger(name)
node_logger = lambda name: LoguruConfig.create_node_logger(name)