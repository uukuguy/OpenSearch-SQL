"""
Alignment and correction node for OpenSearch-SQL pipeline.
"""
from ...utils.loguru_config import get_logger
from typing import Any, Dict, List

from ...core import DatabaseManager, PipelineManager, Logger
from ...llm import model_chose
from ..utils import node_decorator, get_last_node_result


logger = get_logger(__name__)

@node_decorator(check_schema_status=False)  
def align_correct(task: Any, execution_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Apply alignment and correction to SQL candidates.
    
    Args:
        task: Task object containing question and database information.
        execution_history: History of pipeline execution.
        
    Returns:
        Dict[str, Any]: Corrected SQL and alignment information.
    """
    try:
        # Get configuration
        config, node_name = PipelineManager().get_model_para()
        
        # Get SQL candidates from previous node
        candidate_result = get_last_node_result(execution_history, "candidate_generate")
        if not candidate_result:
            logger.error("No SQL candidates found in execution history")
            return {"status": "error", "error": "Missing SQL candidates"}
        
        sql_candidates = candidate_result.get("SQL", "")
        if isinstance(sql_candidates, str):
            sql_candidates = [sql_candidates]
        elif not sql_candidates:
            logger.error("No valid SQL candidates to correct")
            return {"status": "error", "error": "No SQL candidates to correct"}
        
        # Get database schema information
        schema_result = get_last_node_result(execution_history, "generate_db_schema")
        db_schema = schema_result.get("db_list", "") if schema_result else ""
        
        # Initialize chat model
        engine = config.get("engine", "gpt-4o")
        chat_model = model_chose(node_name, engine)
        
        # Get alignment configuration
        alignment_methods = config.get("alignment_methods", ["style_align", "function_align"])
        temperature = float(config.get("temperature", 0.0))
        
        corrected_candidates = []
        
        # Apply alignment and correction to each candidate
        for i, sql_candidate in enumerate(sql_candidates):
            if not sql_candidate or not sql_candidate.strip():
                continue
                
            corrected_sql = sql_candidate
            correction_history = []
            
            # Apply each alignment method
            for method in alignment_methods:
                try:
                    if method == "style_align":
                        corrected_sql, style_corrections = apply_style_alignment(
                            corrected_sql, task, db_schema, chat_model, temperature
                        )
                        correction_history.extend(style_corrections)
                    
                    elif method == "function_align":
                        corrected_sql, function_corrections = apply_function_alignment(
                            corrected_sql, task, db_schema, chat_model, temperature
                        )
                        correction_history.extend(function_corrections)
                    
                    elif method == "agent_align":
                        corrected_sql, agent_corrections = apply_agent_alignment(
                            corrected_sql, task, db_schema, chat_model, temperature
                        )
                        correction_history.extend(agent_corrections)
                    
                except Exception as e:
                    logger.warning(f"Error applying {method} to candidate {i}: {e}")
            
            corrected_candidates.append({
                "original_sql": sql_candidate,
                "corrected_sql": corrected_sql,
                "corrections_applied": correction_history,
                "candidate_index": i
            })
        
        # Select the best corrected candidate
        if corrected_candidates:
            best_candidate = select_best_corrected_candidate(corrected_candidates, task)
            response = {
                "SQL": best_candidate["corrected_sql"],
                "original_SQL": best_candidate["original_sql"],
                "corrections_applied": best_candidate["corrections_applied"],
                "all_candidates": corrected_candidates,
                "selected_candidate_index": best_candidate["candidate_index"]
            }
        else:
            # Fallback to original if no corrections could be applied
            response = {
                "SQL": sql_candidates[0] if sql_candidates else "",
                "original_SQL": sql_candidates[0] if sql_candidates else "",
                "corrections_applied": [],
                "status": "warning",
                "message": "No corrections could be applied"
            }
        
        logger.info(f"Applied alignment corrections for task {task.db_id}_{task.question_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error in align_correct: {e}")
        return {
            "SQL": "",
            "status": "error",
            "error": str(e)
        }


def apply_style_alignment(sql: str, task, db_schema: str, chat_model, temperature: float) -> tuple:
    """
    Apply style alignment corrections to SQL.
    
    Args:
        sql (str): SQL query to correct.
        task: Task object.
        db_schema (str): Database schema.
        chat_model: Chat model instance.
        temperature (float): Sampling temperature.
        
    Returns:
        tuple: (corrected_sql, corrections_list)
    """
    corrections = []
    
    try:
        # Style alignment prompt
        style_prompt = f"""
Please review and improve the SQL query style and formatting:

Original Question: {task.question}
Database Schema: {db_schema}
Original SQL: {sql}

Please check and fix:
1. SQL formatting and indentation
2. Consistent naming conventions
3. Proper use of aliases
4. Unnecessary complexity
5. Standard SQL practices

Return only the improved SQL query:
"""
        
        response = chat_model.get_ans(style_prompt, temperature=temperature)
        corrected_sql = extract_sql_from_response(response)
        
        if corrected_sql and corrected_sql.strip() != sql.strip():
            corrections.append({
                "type": "style_alignment",
                "original": sql,
                "corrected": corrected_sql,
                "description": "Applied style formatting improvements"
            })
            return corrected_sql, corrections
        
    except Exception as e:
        logger.warning(f"Style alignment failed: {e}")
    
    return sql, corrections


def apply_function_alignment(sql: str, task, db_schema: str, chat_model, temperature: float) -> tuple:
    """
    Apply functional alignment corrections to SQL.
    
    Args:
        sql (str): SQL query to correct.
        task: Task object.
        db_schema (str): Database schema.
        chat_model: Chat model instance.
        temperature (float): Sampling temperature.
        
    Returns:
        tuple: (corrected_sql, corrections_list)
    """
    corrections = []
    
    try:
        # Function alignment prompt
        function_prompt = f"""
Please review and correct the SQL query for functional accuracy:

Question: {task.question}
Evidence: {task.evidence}
Database Schema: {db_schema}
Current SQL: {sql}

Please check and fix:
1. Correct table joins
2. Appropriate WHERE conditions
3. Proper aggregation functions
4. Correct column selections
5. Logical query structure

Return only the corrected SQL query:
"""
        
        response = chat_model.get_ans(function_prompt, temperature=temperature)
        corrected_sql = extract_sql_from_response(response)
        
        if corrected_sql and corrected_sql.strip() != sql.strip():
            corrections.append({
                "type": "function_alignment",
                "original": sql,
                "corrected": corrected_sql,
                "description": "Applied functional logic corrections"
            })
            return corrected_sql, corrections
        
    except Exception as e:
        logger.warning(f"Function alignment failed: {e}")
    
    return sql, corrections


def apply_agent_alignment(sql: str, task, db_schema: str, chat_model, temperature: float) -> tuple:
    """
    Apply agent-based alignment corrections to SQL.
    
    Args:
        sql (str): SQL query to correct.
        task: Task object.
        db_schema (str): Database schema.
        chat_model: Chat model instance.
        temperature (float): Sampling temperature.
        
    Returns:
        tuple: (corrected_sql, corrections_list)
    """
    corrections = []
    
    try:
        # Agent alignment prompt - more comprehensive review
        agent_prompt = f"""
As an expert SQL agent, please thoroughly review and correct this SQL query:

Question: {task.question}
Evidence: {task.evidence}
Database Schema: {db_schema}
Current SQL: {sql}

Perform a comprehensive review checking:
1. Query correctness and logic
2. Optimal performance considerations
3. Proper handling of edge cases
4. Completeness of the answer
5. SQL best practices

Provide the final corrected SQL query:
"""
        
        response = chat_model.get_ans(agent_prompt, temperature=temperature)
        corrected_sql = extract_sql_from_response(response)
        
        if corrected_sql and corrected_sql.strip() != sql.strip():
            corrections.append({
                "type": "agent_alignment",
                "original": sql,
                "corrected": corrected_sql,
                "description": "Applied comprehensive agent review corrections"
            })
            return corrected_sql, corrections
        
    except Exception as e:
        logger.warning(f"Agent alignment failed: {e}")
    
    return sql, corrections


def extract_sql_from_response(response: str) -> str:
    """
    Extract SQL query from model response.
    
    Args:
        response (str): Model response.
        
    Returns:
        str: Extracted SQL query.
    """
    import re
    
    if not response:
        return ""
    
    # Look for SQL code blocks
    sql_pattern = r'```sql\s*(.*?)\s*```'
    sql_match = re.search(sql_pattern, response, re.DOTALL | re.IGNORECASE)
    
    if sql_match:
        return sql_match.group(1).strip()
    
    # Look for SELECT statements
    select_pattern = r'(SELECT\s+.*?)(?:\n\n|\Z)'
    select_match = re.search(select_pattern, response, re.DOTALL | re.IGNORECASE)
    
    if select_match:
        return select_match.group(1).strip()
    
    # Return the response as-is if no pattern found
    lines = response.split('\n')
    for line in lines:
        if line.strip().upper().startswith('SELECT'):
            return line.strip()
    
    return response.strip()


def select_best_corrected_candidate(corrected_candidates: List[Dict[str, Any]], task) -> Dict[str, Any]:
    """
    Select the best corrected SQL candidate.
    
    Args:
        corrected_candidates (List[Dict[str, Any]]): List of corrected candidates.
        task: Task object.
        
    Returns:
        Dict[str, Any]: Best candidate.
    """
    if not corrected_candidates:
        return {}
    
    # Score candidates based on corrections applied and other factors
    scored_candidates = []
    
    for candidate in corrected_candidates:
        score = 0.0
        
        # More corrections might indicate more improvements
        corrections = candidate.get("corrections_applied", [])
        score += len(corrections) * 0.1
        
        # Prefer candidates with specific types of corrections
        for correction in corrections:
            if correction.get("type") == "function_alignment":
                score += 0.3  # Function corrections are important
            elif correction.get("type") == "agent_alignment":
                score += 0.2  # Agent corrections are valuable
            elif correction.get("type") == "style_alignment":
                score += 0.1  # Style corrections are nice to have
        
        # Basic SQL validation
        corrected_sql = candidate.get("corrected_sql", "")
        if corrected_sql and corrected_sql.strip().upper().startswith('SELECT'):
            score += 0.2
        
        scored_candidates.append({
            **candidate,
            "selection_score": score
        })
    
    # Sort by score and return the best candidate
    scored_candidates.sort(key=lambda x: x["selection_score"], reverse=True)
    return scored_candidates[0]


def validate_alignment_result(original_sql: str, corrected_sql: str, 
                            db_manager: DatabaseManager) -> Dict[str, Any]:
    """
    Validate that alignment correction didn't break the SQL.
    
    Args:
        original_sql (str): Original SQL query.
        corrected_sql (str): Corrected SQL query.
        db_manager (DatabaseManager): Database manager instance.
        
    Returns:
        Dict[str, Any]: Validation result.
    """
    try:
        # Validate both queries
        original_result = db_manager.validate_sql_query(original_sql + " LIMIT 1")
        corrected_result = db_manager.validate_sql_query(corrected_sql + " LIMIT 1")
        
        return {
            "original_valid": original_result["STATUS"] == "OK",
            "corrected_valid": corrected_result["STATUS"] == "OK",
            "original_error": original_result.get("RESULT") if original_result["STATUS"] == "ERROR" else None,
            "corrected_error": corrected_result.get("RESULT") if corrected_result["STATUS"] == "ERROR" else None,
            "improvement": corrected_result["STATUS"] == "OK" and original_result["STATUS"] == "ERROR"
        }
        
    except Exception as e:
        logger.warning(f"Error validating alignment result: {e}")
        return {
            "original_valid": False,
            "corrected_valid": False,
            "validation_error": str(e)
        }