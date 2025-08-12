"""
Enhanced Logger implementation using loguru for OpenSearch-SQL pipeline.
"""
import json
from threading import Lock
from pathlib import Path
from typing import Any, List, Dict, Union

from ..utils.loguru_config import get_logger, LoguruConfig
from ..utils.progress_tracker import ErrorFilter, SQLFormatter


def make_serial(obj):
    """
    Recursively converts objects to JSON-serializable format.
    
    Args:
        obj: Object to serialize
        
    Returns:
        JSON-serializable object
    """
    if isinstance(obj, (str, int, float, bool, type(None))):
        # Basic types return as-is
        return obj
    elif isinstance(obj, list):
        # Recursively process each element in list
        return [make_serial(item) for item in obj]
    elif isinstance(obj, tuple):
        # Convert tuple to list
        return [make_serial(item) for item in obj]
    elif isinstance(obj, set):
        # Convert set to list
        return [make_serial(item) for item in obj]
    elif isinstance(obj, dict):
        # Recursively process each key-value pair in dict
        return {make_serial(key): make_serial(value) for key, value in obj.items()}
    else:
        # Other types try to convert to string
        try:
            return str(obj)
        except Exception as e:
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable") from e


class Logger:
    """
    Singleton Logger class for pipeline execution logging.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls, db_id: str = None, question_id: str = None, result_directory: str = None):
        """
        Ensures a singleton instance of Logger.

        Args:
            db_id (str, optional): The database ID.
            question_id (str, optional): The question ID.
            result_directory (str, optional): The directory to store results.

        Returns:
            Logger: The singleton instance of the class.

        Raises:
            ValueError: If the Logger instance has not been initialized.
        """
        with cls._lock:
            if (db_id is not None) and (question_id is not None):
                cls._instance = super(Logger, cls).__new__(cls)
                cls._instance._init(db_id, question_id, result_directory)
            else:
                if cls._instance is None:
                    raise ValueError("Logger instance has not been initialized.")
            return cls._instance

    def _init(self, db_id: str, question_id: str, result_directory: str):
        """
        Initializes the Logger instance with the provided parameters.

        Args:
            db_id (str): The database ID.
            question_id (str): The question ID.
            result_directory (str): The directory to store results.
        """
        self.db_id = db_id
        self.question_id = question_id
        self.result_directory = Path(result_directory)
        self.logger = get_logger(f"pipeline.{db_id}.{question_id}")
        self.error_filter = ErrorFilter()
        self.sql_formatter = SQLFormatter()

    def _set_log_level(self, log_level: str):
        """
        Sets the logging level (now handled by loguru config).

        Args:
            log_level (str): The logging level to set.
        """
        # Log level is now handled by loguru configuration
        pass

    def log(self, message: str, log_level: str = "info"):
        """
        Logs a message at the specified log level using loguru.

        Args:
            message (str): The message to log.
            log_level (str): The log level to use.
        """
        # Map level to loguru methods
        level_map = {
            "debug": self.logger.debug,
            "info": self.logger.info,
            "warning": self.logger.warning,
            "warn": self.logger.warning,
            "error": self.logger.error,
            "critical": self.logger.critical
        }
        
        log_method = level_map.get(log_level.lower(), self.logger.info)
        log_method(message)

    def log_conversation(self, text: Union[str, List[Any], Dict[str, Any], bool], _from: str, step: str):
        """
        Logs a conversation text to a file.

        Args:
            text (Union[str, List[Any], Dict[str, Any], bool]): The conversation text to log.
            _from (str): The source of the text.
            step (str): The step identifier.
        """
        log_file_path = self.result_directory / "logs" / f"{self.question_id}_{self.db_id}.log"
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        with log_file_path.open("a", encoding='utf-8') as file:
            file.write(f"############################## {_from} at step {step} ##############################\n\n")
            if isinstance(text, str):
                # Special formatting for SQL strings
                if _from.lower() in ["sql", "generated_sql", "candidate_sql", "vote", "final_sql"]:
                    formatted_sql = self.sql_formatter.format_sql(text, max_length=500)
                    file.write(formatted_sql)
                else:
                    file.write(text)
            elif isinstance(text, (list, dict)):
                formatted_text = json.dumps(text, indent=4, ensure_ascii=False)
                file.write(formatted_text)
            elif isinstance(text, bool):
                file.write(str(text))
            file.write("\n\n")

    def dump_history_to_file(self, execution_history: List[Dict[str, Any]]):
        """
        Dumps the execution history to a JSON file.

        Args:
            execution_history (List[Dict[str, Any]]): The execution history to dump.
        """
        execution_history_tmp = make_serial(execution_history)

        file_path = self.result_directory / f"{self.question_id}_{self.db_id}.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding='utf-8') as file:
            json.dump(execution_history_tmp, file, indent=4, ensure_ascii=False)

    def log_error(self, error: Exception, context: str = "", node_type: str = ""):
        """
        Logs an error with context information, filtering expected SQL errors.
        
        Args:
            error (Exception): The error to log.
            context (str): Additional context information.
            node_type (str): Pipeline node where error occurred.
        """
        error_str = str(error)
        
        # Check if error should be logged based on filtering
        if not self.error_filter.should_log_error(error_str, node_type):
            # Log as debug instead of error for expected SQL generation errors
            self.log(f"Expected error in {context}: {error_str[:100]}...", "debug")
            return
            
        error_message = f"Error in {context}: {type(error).__name__}: {error_str}"
        self.log(error_message, "error")

    def log_debug(self, message: str, data: Any = None):
        """
        Logs a debug message with optional data.
        
        Args:
            message (str): Debug message.
            data (Any): Optional data to log.
        """
        debug_message = message
        if data is not None:
            debug_message += f" | Data: {json.dumps(make_serial(data), ensure_ascii=False)}"
        self.log(debug_message, "debug")

    def log_info(self, message: str):
        """
        Logs an info message.
        
        Args:
            message (str): Info message.
        """
        self.log(message, "info")

    def log_warning(self, message: str):
        """
        Logs a warning message.
        
        Args:
            message (str): Warning message.
        """
        self.log(message, "warning")

    # Backward compatibility methods for standard logging interface
    def info(self, message: str):
        """Standard logging interface - info level."""
        self.log(message, "info")
    
    def debug(self, message: str):
        """Standard logging interface - debug level."""
        self.log(message, "debug")
    
    def warning(self, message: str):
        """Standard logging interface - warning level."""
        self.log(message, "warning")
    
    def error(self, message: str):
        """Standard logging interface - error level."""
        self.log(message, "error")
    
    def critical(self, message: str):
        """Standard logging interface - critical level."""
        self.log(message, "critical")
    
    def log_sql(self, sql: str, context: str = "Generated SQL"):
        """
        Logs SQL with special formatting.
        
        Args:
            sql (str): SQL query to log.
            context (str): Context for the SQL.
        """
        formatted_sql = self.sql_formatter.format_sql(sql)
        self.log(f"{context}: {formatted_sql}", "info")

    def __str__(self) -> str:
        """String representation of the Logger."""
        return f"Logger(db_id={self.db_id}, question_id={self.question_id})"

    def __repr__(self) -> str:
        """Detailed representation of the Logger."""
        return self.__str__()