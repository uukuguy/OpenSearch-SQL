"""
Utility functions for OpenSearch-SQL pipeline nodes.
"""
from functools import wraps
from typing import Dict, List, Any, Callable
from ..core import Logger, DatabaseManager


def node_decorator(check_schema_status: bool = False) -> Callable:
    """
    A decorator to add logging and error handling to pipeline node functions.

    Args:
        check_schema_status (bool, optional): Whether to check the schema status. Defaults to False.

    Returns:
        Callable: The decorated function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            node_name = func.__name__
            Logger().log(f"---{node_name.upper()}---")
            result = {"node_type": node_name}

            try:
                task = state["keys"]["task"]
                execution_history = state["keys"]["execution_history"]
                
                # Check if this node has already been executed
                for x in execution_history:
                    if x["node_type"] == node_name:
                        return state
                
                # Execute the node function
                output = func(task, execution_history)
                result.update(output)
                result["status"] = "success"
                
            except Exception as e:
                Logger().log(f"Node '{node_name}': {task.db_id}_{task.question_id}\n{type(e)}: {e}\n", "error")
                result.update({
                    "status": "error",
                    "error": f"{type(e)}: <{e}>",
                })
            
            execution_history.append(result)
            Logger().dump_history_to_file(execution_history)
            
            return state
        return wrapper
    return decorator


def get_last_node_result(execution_history: List[Dict[str, Any]], node_type: str) -> Dict[str, Any]:
    """
    Retrieves the last result for a specific node type from the execution history.

    Args:
        execution_history (List[Dict[str, Any]]): The execution history.
        node_type (str): The type of node to look for.

    Returns:
        Dict[str, Any]: The result of the last node of the specified type, or None if not found.
    """
    # Handle case where execution_history might not be a list
    if not isinstance(execution_history, list):
        return None
        
    for node in reversed(execution_history):
        if isinstance(node, dict) and node.get("node_type") == node_type:
            return node
    return None


def safe_get_node_result(execution_history: List[Dict[str, Any]], node_type: str) -> Dict[str, Any]:
    """
    Safely retrieves the last result for a specific node type from the execution history.
    Returns empty dict if not found or if there are any issues.

    Args:
        execution_history (List[Dict[str, Any]]): The execution history.
        node_type (str): The type of node to look for.

    Returns:
        Dict[str, Any]: The result of the last node of the specified type, or empty dict if not found.
    """
    try:
        result = get_last_node_result(execution_history, node_type)
        return result if result is not None else {}
    except Exception:
        return {}


def make_newprompt(new_prompt: str, fewshot: str, key_col_des: str, db_info: str, 
                   question: str, hint: str = "", q_order: str = "") -> str:
    """
    Creates a new prompt by formatting the template with provided parameters.
    
    Args:
        new_prompt (str): The prompt template.
        fewshot (str): Few-shot examples.
        key_col_des (str): Key column descriptions.
        db_info (str): Database information.
        question (str): The question text.
        hint (str): Additional hints.
        q_order (str): Query order information.
        
    Returns:
        str: The formatted prompt.
    """
    n_prompt = new_prompt.format(
        fewshot=fewshot,
        db_info=db_info,
        question=question,
        hint=hint,
        key_col_des=key_col_des,
        q_order=q_order
    )
    return n_prompt


def safe_get_node_result(execution_history: List[Dict[str, Any]], node_type: str, 
                        key: str, default: Any = None) -> Any:
    """
    Safely gets a specific value from a node result in the execution history.
    
    Args:
        execution_history (List[Dict[str, Any]]): The execution history.
        node_type (str): The type of node to look for.
        key (str): The key to retrieve from the node result.
        default (Any): Default value if not found.
        
    Returns:
        Any: The value or default if not found.
    """
    node_result = get_last_node_result(execution_history, node_type)
    if node_result is None:
        return default
    return node_result.get(key, default)


def validate_node_dependencies(execution_history: List[Dict[str, Any]], 
                               required_nodes: List[str]) -> List[str]:
    """
    Validates that required node dependencies are present in execution history.
    
    Args:
        execution_history (List[Dict[str, Any]]): The execution history.
        required_nodes (List[str]): List of required node types.
        
    Returns:
        List[str]: List of missing nodes.
    """
    executed_nodes = {node["node_type"] for node in execution_history}
    missing_nodes = [node for node in required_nodes if node not in executed_nodes]
    return missing_nodes


def log_node_start(node_name: str, task, logger: Logger = None):
    """
    Logs the start of a node execution.
    
    Args:
        node_name (str): Name of the node.
        task: The task being processed.
        logger (Logger): Logger instance.
    """
    if logger is None:
        logger = Logger()
    logger.log(f"Starting {node_name} for task {task.db_id}_{task.question_id}", "info")


def log_node_complete(node_name: str, task, result: Dict[str, Any], logger: Logger = None):
    """
    Logs the completion of a node execution.
    
    Args:
        node_name (str): Name of the node.
        task: The task being processed.
        result (Dict[str, Any]): The node execution result.
        logger (Logger): Logger instance.
    """
    if logger is None:
        logger = Logger()
    status = result.get("status", "unknown")
    logger.log(f"Completed {node_name} for task {task.db_id}_{task.question_id} with status: {status}", "info")


def format_database_info(db_schema: Dict[str, Any], db_id: str) -> str:
    """
    Formats database information into a readable string.
    
    Args:
        db_schema (Dict[str, Any]): Database schema information.
        db_id (str): Database identifier.
        
    Returns:
        str: Formatted database information.
    """
    info = f"Database Management System: SQLite\n#Database name: {db_id}\n"
    
    if "tables" in db_schema:
        for table_name, table_info in db_schema["tables"].items():
            info += f"\n# Table: {table_name}\n"
            if "columns" in table_info:
                for col in table_info["columns"]:
                    info += f"  {col}\n"
    
    return info


def extract_sql_from_response(response: str) -> str:
    """
    Extracts SQL query from LLM response text.
    
    Args:
        response (str): Response text from LLM.
        
    Returns:
        str: Extracted SQL query.
    """
    # Look for SQL code blocks
    if "```sql" in response.lower():
        start = response.lower().find("```sql") + 6
        end = response.find("```", start)
        if end != -1:
            return response[start:end].strip()
    
    # Look for SELECT statements
    if "SELECT" in response.upper():
        lines = response.split('\n')
        sql_lines = []
        collecting = False
        for line in lines:
            if "SELECT" in line.upper():
                collecting = True
            if collecting:
                sql_lines.append(line.strip())
                if line.strip().endswith(';'):
                    break
        if sql_lines:
            return ' '.join(sql_lines)
    
    return response.strip()


def clean_sql_query(sql: str) -> str:
    """
    Cleans and normalizes SQL query.
    
    Args:
        sql (str): Raw SQL query.
        
    Returns:
        str: Cleaned SQL query.
    """
    # Remove extra whitespace and normalize
    sql = ' '.join(sql.split())
    
    # Remove trailing semicolon if present
    if sql.endswith(';'):
        sql = sql[:-1]
    
    # Ensure it starts with SELECT (for basic validation)
    sql = sql.strip()
    
    return sql


def merge_execution_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merges multiple execution results into a single result.
    
    Args:
        results (List[Dict[str, Any]]): List of results to merge.
        
    Returns:
        Dict[str, Any]: Merged result.
    """
    if not results:
        return {}
    
    merged = results[0].copy()
    
    for result in results[1:]:
        for key, value in result.items():
            if key == "node_type":
                continue  # Don't merge node_type
            if key in merged:
                # If it's a list, extend it
                if isinstance(merged[key], list) and isinstance(value, list):
                    merged[key].extend(value)
                # If it's a dict, update it
                elif isinstance(merged[key], dict) and isinstance(value, dict):
                    merged[key].update(value)
                else:
                    # Otherwise, keep the first value
                    continue
            else:
                merged[key] = value
    
    return merged