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
    _error_patterns_to_suppress = [
        # SQL syntax errors during generation
        "syntax error",
        "parse error", 
        "unexpected token",
        # Schema exploration errors
        "column .* does not exist",
        "table .* does not exist",
        "no such column",
        "no such table",
        # SQL construction errors
        "ambiguous column",
        "aggregate function",
        "group by clause",
    ]
    
    @classmethod
    def setup(cls, 
              log_level: str = "INFO",
              log_directory: Optional[str] = None,
              log_to_file: bool = True,
              log_to_console: bool = True,
              rotation: str = "10 MB",
              retention: str = "7 days",
              compression: str = "zip",
              colorize: bool = True,
              verbose: bool = False) -> None:
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
            verbose: Verbose mode for detailed pipeline node logging
        """
        if cls._configured:
            return
            
        # Remove default handler
        logger.remove()
        
        # Setup console logging with filtering
        if log_to_console:
            console_format = (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            )
            
            # Add filter function for console output
            def console_filter(record):
                """Filter console output based on verbose mode and content type."""
                message = record["message"].lower()
                module_name = record["name"]
                level = record["level"].name
                
                # Always show critical errors and warnings
                if level in ["ERROR", "CRITICAL"]:
                    return True
                    
                # In verbose mode, show everything except suppressed patterns
                if verbose:
                    # Still filter out expected SQL generation errors
                    for pattern in cls._error_patterns_to_suppress:
                        if pattern in message:
                            return False
                    return True
                
                # In non-verbose mode, apply stricter filtering
                # Always show final node results
                if any(node in module_name for node in ["vote", "evaluation", "task_result_formatter"]):
                    return True
                    
                # Show important pipeline progress info
                if any(keyword in message for keyword in [
                    "processing task:", "task completed:", "pipeline built", 
                    "total number of tasks", "running", "tasks", "finished"
                ]):
                    return True
                
                # Filter out routine pipeline node logs
                if any(node in module_name for node in [
                    "generate_db_schema", "extract_col_value", "extract_query_noun",
                    "column_retrieve_and_other_info", "candidate_generate", "align_correct"
                ]):
                    return level in ["WARNING", "ERROR"]
                
                # Filter expected SQL generation errors
                for pattern in cls._error_patterns_to_suppress:
                    if pattern in message:
                        return False
                
                return True
            
            logger.add(
                sys.stdout,
                format=console_format,
                level=log_level,
                colorize=colorize,
                backtrace=True,
                diagnose=True,
                catch=True,
                filter=console_filter
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


# Convenience functions for backward compatibility
def setup_logging(log_level: str = "INFO", 
                 log_directory: Optional[str] = None,
                 verbose: bool = False,
                 **kwargs) -> None:
    """
    Convenience function to setup logging via LoguruConfig.
    
    Args:
        log_level: Logging level 
        log_directory: Directory for log files
        verbose: Verbose mode for detailed logging
        **kwargs: Additional arguments passed to LoguruConfig.setup()
    """
    LoguruConfig.setup(
        log_level=log_level,
        log_directory=log_directory,
        verbose=verbose,
        **kwargs
    )


def get_logger(name: str = None):
    """
    Convenience function to get a logger instance.
    
    Args:
        name: Logger name for identification
        
    Returns:
        Configured logger instance
    """
    return LoguruConfig.get_logger(name)