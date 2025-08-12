"""
SQL candidate generation node for OpenSearch-SQL pipeline.
"""
import json
from ...utils.loguru_config import get_logger
from typing import Any, Dict, List
from pathlib import Path

from ...core import DatabaseManager, PipelineManager, Logger
from ...llm import model_chose, get_sql_from_response
from ..utils import node_decorator, get_last_node_result, make_newprompt


logger = get_logger(__name__)

@node_decorator(check_schema_status=False)
def candidate_generate(task: Any, execution_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate SQL query candidates for the given task.
    
    Args:
        task: Task object containing question and database information.
        execution_history: History of pipeline execution.
        
    Returns:
        Dict[str, Any]: Generated SQL candidates and related information.
    """
    try:
        # Get configuration
        config, node_name = PipelineManager().get_model_para()
        paths = DatabaseManager()
        
        # Load few-shot examples
        fewshot_path = paths.db_fewshot_path
        try:
            with open(fewshot_path, 'r', encoding='utf-8') as f:
                df_fewshot = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load few-shot examples: {e}")
            df_fewshot = {"questions": {}}
        
        # Initialize chat model
        engine = config.get("engine", "gpt-4o")
        chat_model = model_chose(node_name, engine)
        
        # Get information from previous nodes
        column_info_result = get_last_node_result(execution_history, "column_retrieve_and_other_info")
        if not column_info_result:
            logger.error("No column information found in execution history")
            return {"status": "error", "error": "Missing column information"}
        
        column = column_info_result.get("column", "")
        foreign_keys = column_info_result.get("foreign_keys", "")
        l_values = column_info_result.get("L_values", [])
        q_order = column_info_result.get("q_order", "")
        
        # Format values for prompt
        values = [f"{x[0]}: '{x[1]}'" for x in l_values]
        key_col_des = "#Values in Database:\n" + '\n'.join(values) if values else ""
        
        # Create database info string
        db = task.db_id
        new_db_info = f"Database Management System: SQLite\n#Database name: {db}\n{column}\n\n#Foreign keys:\n{foreign_keys}\n"
        
        # Get few-shot examples for this question
        question_id_str = str(task.question_id)
        if question_id_str in df_fewshot.get("questions", {}):
            fewshot = df_fewshot["questions"][question_id_str].get('prompt', '')
        else:
            fewshot = ""  # No few-shot examples available
        
        # Create the prompt
        from ...llm.prompts import db_check_prompts
        prompt_manager = db_check_prompts()
        
        new_prompt = make_newprompt(
            prompt_manager.new_prompt, 
            fewshot,
            key_col_des, 
            new_db_info, 
            task.question,
            task.evidence,
            q_order
        )
        
        # Generate SQL candidates
        single = config.get('single', 'true').lower() == 'true'
        return_question = config.get('return_question', 'false') == 'true'
        temperature = float(config.get('temperature', 0.0))
        n = int(config.get('n', 1))
        
        sql_candidates, question_analysis = get_sql_from_response_wrapper(
            chat_model, new_prompt, temperature, return_question, n, single
        )
        
        response = {
            "SQL": sql_candidates,
            "question_analysis": question_analysis,
            "prompt_used": new_prompt,
            "generation_params": {
                "temperature": temperature,
                "n": n,
                "single": single,
                "return_question": return_question
            },
            "candidate_count": len(sql_candidates) if isinstance(sql_candidates, list) else 1
        }
        
        logger.info(f"Generated SQL candidates for task {task.db_id}_{task.question_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error in candidate_generate: {e}")
        return {
            "SQL": "",
            "status": "error", 
            "error": str(e)
        }


def get_sql_from_response_wrapper(chat_model, prompt: str, temperature: float,
                                 return_question: bool = False, n: int = 1, 
                                 single: bool = True) -> tuple:
    """
    Wrapper function to get SQL from model response with retries.
    
    Args:
        chat_model: Chat model instance.
        prompt (str): Input prompt.
        temperature (float): Sampling temperature.
        return_question (bool): Whether to return question analysis.
        n (int): Number of candidates to generate.
        single (bool): Whether to return single response.
        
    Returns:
        tuple: (SQL candidates, question analysis)
    """
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Get response from model
            response = chat_model.get_ans(
                prompt, 
                temperature=temperature,
                n=n,
                single=single
            )
            
            # Extract SQL from response
            if isinstance(response, list):
                # Multiple responses
                sql_candidates = []
                question_analysis = None
                
                for resp in response:
                    sql, qa = get_sql_from_response(resp, return_question, n=1, single=True)
                    if sql:
                        sql_candidates.append(sql)
                    if qa and not question_analysis:
                        question_analysis = qa
                
                return sql_candidates, question_analysis
            else:
                # Single response
                sql, question_analysis = get_sql_from_response(
                    response, return_question, n, single
                )
                return sql, question_analysis
                
        except Exception as e:
            retry_count += 1
            logger.warning(f"Error getting SQL response (attempt {retry_count}): {e}")
            
            if retry_count >= max_retries:
                logger.error(f"Failed to get SQL after {max_retries} attempts")
                return ("" if single else [], None)
            
            # Adjust parameters for retry
            temperature = min(temperature + 0.1, 0.7)  # Slightly increase temperature
    
    return ("" if single else [], None)


def validate_sql_candidates(sql_candidates, db_manager: DatabaseManager) -> List[Dict[str, Any]]:
    """
    Validate generated SQL candidates.
    
    Args:
        sql_candidates: SQL candidates (string or list).
        db_manager (DatabaseManager): Database manager instance.
        
    Returns:
        List[Dict[str, Any]]: Validated SQL candidates with metadata.
    """
    if isinstance(sql_candidates, str):
        sql_candidates = [sql_candidates]
    
    validated_candidates = []
    
    for i, sql in enumerate(sql_candidates):
        if not sql or not sql.strip():
            continue
            
        try:
            # Basic syntax validation
            sql = sql.strip()
            if not sql.upper().startswith('SELECT'):
                logger.warning(f"SQL candidate {i} does not start with SELECT: {sql[:50]}...")
                continue
            
            # Try to execute the SQL (with LIMIT to prevent large results)
            limited_sql = add_limit_to_sql(sql, limit=1)
            result = db_manager.validate_sql_query(limited_sql)
            
            validated_candidates.append({
                "sql": sql,
                "index": i,
                "valid": result["STATUS"] == "OK",
                "error": result.get("RESULT") if result["STATUS"] == "ERROR" else None,
                "validation_result": result
            })
            
        except Exception as e:
            logger.warning(f"Error validating SQL candidate {i}: {e}")
            validated_candidates.append({
                "sql": sql,
                "index": i,
                "valid": False,
                "error": str(e),
                "validation_result": None
            })
    
    return validated_candidates


def add_limit_to_sql(sql: str, limit: int = 10) -> str:
    """
    Add LIMIT clause to SQL query if not present.
    
    Args:
        sql (str): SQL query.
        limit (int): Limit value.
        
    Returns:
        str: SQL with LIMIT clause.
    """
    sql = sql.strip()
    if sql.endswith(';'):
        sql = sql[:-1]
    
    # Check if LIMIT already exists
    if 'LIMIT' not in sql.upper():
        sql += f" LIMIT {limit}"
    
    return sql


def rank_sql_candidates(validated_candidates: List[Dict[str, Any]], 
                       task, execution_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rank SQL candidates based on various criteria.
    
    Args:
        validated_candidates (List[Dict[str, Any]]): Validated SQL candidates.
        task: Task object.
        execution_history (List[Dict[str, Any]]): Execution history.
        
    Returns:
        List[Dict[str, Any]]: Ranked SQL candidates.
    """
    for candidate in validated_candidates:
        score = 0.0
        
        # Valid syntax gets high score
        if candidate["valid"]:
            score += 0.5
        
        # Shorter queries might be better (simple heuristic)
        sql_length = len(candidate["sql"])
        if sql_length < 200:
            score += 0.1
        elif sql_length > 500:
            score -= 0.1
        
        # Queries with appropriate complexity
        sql_upper = candidate["sql"].upper()
        
        # Check for expected SQL patterns based on question
        question_lower = task.question.lower()
        
        # COUNT queries for counting questions
        if any(word in question_lower for word in ['how many', 'count', 'number of']):
            if 'COUNT' in sql_upper:
                score += 0.2
        
        # ORDER BY for questions asking for highest/lowest
        if any(word in question_lower for word in ['highest', 'lowest', 'maximum', 'minimum']):
            if 'ORDER BY' in sql_upper:
                score += 0.2
        
        # GROUP BY for aggregation questions
        if any(word in question_lower for word in ['each', 'every', 'per', 'average', 'total']):
            if 'GROUP BY' in sql_upper:
                score += 0.2
        
        candidate["rank_score"] = score
    
    # Sort by rank score descending
    validated_candidates.sort(key=lambda x: x["rank_score"], reverse=True)
    return validated_candidates