"""
Evaluation node for OpenSearch-SQL pipeline.
"""
from ...utils.loguru_config import get_logger
from typing import Any, Dict, List

from ...core import DatabaseManager, PipelineManager, Logger
from ...llm import model_chose
from ..utils import node_decorator, get_last_node_result


logger = get_logger(__name__)

@node_decorator(check_schema_status=False)
def evaluation(task: Any, execution_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluate the final SQL query against the ground truth and provide metrics.
    
    Args:
        task: Task object containing question and database information.
        execution_history: History of pipeline execution.
        
    Returns:
        Dict[str, Any]: Evaluation results and metrics.
    """
    try:
        # Get configuration
        config, node_name = PipelineManager().get_model_para()
        db_manager = DatabaseManager()
        
        # Get the final SQL from voting node
        vote_result = get_last_node_result(execution_history, "vote")
        if not vote_result:
            logger.error("No voting result found in execution history")
            return {"status": "error", "error": "Missing voting result"}
        
        predicted_sql = vote_result.get("SQL", "")
        if not predicted_sql or not predicted_sql.strip():
            logger.error("No SQL query found in voting result")
            return {"status": "error", "error": "No SQL query to evaluate"}
        
        # Get ground truth SQL if available
        ground_truth_sql = task.SQL if hasattr(task, 'SQL') and task.SQL else None
        
        # Perform different types of evaluation
        results = {}
        
        # 1. Execution-based evaluation
        if ground_truth_sql:
            exec_result = evaluate_execution_match(predicted_sql, ground_truth_sql, db_manager)
            results.update(exec_result)
        else:
            # If no ground truth, just check if SQL is executable
            exec_result = evaluate_executability(predicted_sql, db_manager)
            results.update(exec_result)
        
        # 2. Syntax evaluation
        syntax_result = evaluate_syntax(predicted_sql)
        results["syntax_evaluation"] = syntax_result
        
        # 3. Semantic evaluation (if LLM evaluation is enabled)
        use_llm_eval = config.get("use_llm_evaluation", False)
        if use_llm_eval:
            try:
                schema_result = get_last_node_result(execution_history, "generate_db_schema")
                db_schema = schema_result.get("db_list", "") if schema_result else ""
                
                engine = config.get("engine", "gpt-4o")
                chat_model = model_chose(node_name, engine)
                
                semantic_result = evaluate_semantics(predicted_sql, task, db_schema, chat_model)
                results["semantic_evaluation"] = semantic_result
            except Exception as e:
                logger.warning(f"LLM semantic evaluation failed: {e}")
                results["semantic_evaluation"] = {"error": str(e)}
        
        # 4. Overall assessment
        overall_score = calculate_overall_score(results)
        results["overall_score"] = overall_score
        results["evaluation_summary"] = generate_evaluation_summary(results)
        
        logger.info(f"Evaluated SQL for task {task.db_id}_{task.question_id}: score={overall_score}")
        return results
        
    except Exception as e:
        logger.error(f"Error in evaluation: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def evaluate_execution_match(predicted_sql: str, ground_truth_sql: str, 
                           db_manager: DatabaseManager) -> Dict[str, Any]:
    """
    Evaluate by comparing execution results of predicted and ground truth SQL.
    
    Args:
        predicted_sql (str): Predicted SQL query.
        ground_truth_sql (str): Ground truth SQL query.
        db_manager (DatabaseManager): Database manager instance.
        
    Returns:
        Dict[str, Any]: Execution evaluation results.
    """
    try:
        # Use the database manager's comparison method
        comparison_result = db_manager.compare_sqls(predicted_sql, ground_truth_sql)
        
        exec_res = comparison_result.get("exec_res", 0)
        exec_err = comparison_result.get("exec_err", "unknown")
        
        result = {
            "exec_res": exec_res,
            "exec_err": exec_err,
            "execution_match": exec_res == 1,
            "predicted_sql": predicted_sql,
            "ground_truth_sql": ground_truth_sql
        }
        
        # Get additional execution details
        try:
            predicted_result = db_manager.validate_sql_query(predicted_sql, max_returned_rows=20)
            result["predicted_result"] = predicted_result
            
            ground_truth_result = db_manager.validate_sql_query(ground_truth_sql, max_returned_rows=20)
            result["ground_truth_result"] = ground_truth_result
            
        except Exception as e:
            logger.warning(f"Could not get detailed execution results: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in execution evaluation: {e}")
        return {
            "exec_res": 0,
            "exec_err": str(e),
            "execution_match": False,
            "evaluation_error": str(e)
        }


def evaluate_executability(predicted_sql: str, db_manager: DatabaseManager) -> Dict[str, Any]:
    """
    Evaluate if the SQL query is executable (when no ground truth is available).
    
    Args:
        predicted_sql (str): Predicted SQL query.
        db_manager (DatabaseManager): Database manager instance.
        
    Returns:
        Dict[str, Any]: Executability evaluation results.
    """
    try:
        result = db_manager.validate_sql_query(predicted_sql, max_returned_rows=10)
        
        is_executable = result["STATUS"] == "OK"
        
        return {
            "exec_res": 1 if is_executable else 0,
            "exec_err": "correct execution" if is_executable else result.get("RESULT", "execution failed"),
            "execution_match": is_executable,  # Consider executable as "correct" when no ground truth
            "predicted_sql": predicted_sql,
            "predicted_result": result,
            "evaluation_mode": "executability_only"
        }
        
    except Exception as e:
        logger.error(f"Error in executability evaluation: {e}")
        return {
            "exec_res": 0,
            "exec_err": str(e),
            "execution_match": False,
            "evaluation_error": str(e),
            "evaluation_mode": "executability_only"
        }


def evaluate_syntax(sql: str) -> Dict[str, Any]:
    """
    Evaluate SQL syntax correctness.
    
    Args:
        sql (str): SQL query to evaluate.
        
    Returns:
        Dict[str, Any]: Syntax evaluation results.
    """
    syntax_issues = []
    
    if not sql or not sql.strip():
        syntax_issues.append("Empty SQL query")
        return {"syntax_correct": False, "issues": syntax_issues}
    
    sql_upper = sql.upper().strip()
    
    # Basic syntax checks
    if not sql_upper.startswith('SELECT'):
        syntax_issues.append("Query does not start with SELECT")
    
    if 'FROM' not in sql_upper:
        syntax_issues.append("Missing FROM clause")
    
    # Check for balanced parentheses
    if sql.count('(') != sql.count(')'):
        syntax_issues.append("Unbalanced parentheses")
    
    # Check for balanced quotes
    single_quote_count = sql.count("'") - sql.count("\\'")
    double_quote_count = sql.count('"') - sql.count('\\"')
    
    if single_quote_count % 2 != 0:
        syntax_issues.append("Unbalanced single quotes")
    
    if double_quote_count % 2 != 0:
        syntax_issues.append("Unbalanced double quotes")
    
    # Check for common keywords in proper positions
    keywords_check = check_keyword_order(sql_upper)
    syntax_issues.extend(keywords_check)
    
    return {
        "syntax_correct": len(syntax_issues) == 0,
        "issues": syntax_issues,
        "sql_length": len(sql),
        "sql_uppercase": sql_upper
    }


def check_keyword_order(sql_upper: str) -> List[str]:
    """
    Check if SQL keywords are in the correct order.
    
    Args:
        sql_upper (str): Uppercase SQL query.
        
    Returns:
        List[str]: List of keyword order issues.
    """
    issues = []
    
    # Define expected keyword order
    keyword_order = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT']
    
    # Find positions of keywords in the SQL
    keyword_positions = {}
    for keyword in keyword_order:
        pos = sql_upper.find(keyword)
        if pos != -1:
            keyword_positions[keyword] = pos
    
    # Check if keywords are in the correct order
    previous_pos = -1
    for keyword in keyword_order:
        if keyword in keyword_positions:
            current_pos = keyword_positions[keyword]
            if current_pos < previous_pos:
                issues.append(f"Keyword {keyword} appears in wrong position")
            previous_pos = current_pos
    
    return issues


def evaluate_semantics(sql: str, task, db_schema: str, chat_model) -> Dict[str, Any]:
    """
    Evaluate SQL semantics using LLM.
    
    Args:
        sql (str): SQL query to evaluate.
        task: Task object.
        db_schema (str): Database schema.
        chat_model: Chat model instance.
        
    Returns:
        Dict[str, Any]: Semantic evaluation results.
    """
    try:
        semantic_prompt = f"""
Please evaluate the semantic correctness of this SQL query for the given question:

Question: {task.question}
Evidence: {task.evidence}
Database Schema: {db_schema}
SQL Query: {sql}

Please assess:
1. Does the SQL correctly interpret the question?
2. Are the right tables and columns selected?
3. Are the join conditions appropriate?
4. Are the WHERE conditions correctly specified?
5. Are aggregations used appropriately?
6. Will this query provide the expected answer?

Provide your assessment in this format:
Correctness: [CORRECT/INCORRECT/PARTIAL]
Confidence: [HIGH/MEDIUM/LOW]
Issues: [List any issues found]
Explanation: [Brief explanation of the assessment]
"""
        
        response = chat_model.get_ans(semantic_prompt, temperature=0.0)
        
        # Parse LLM response
        semantic_result = parse_semantic_evaluation(response)
        semantic_result["llm_response"] = response
        
        return semantic_result
        
    except Exception as e:
        logger.warning(f"Semantic evaluation failed: {e}")
        return {"error": str(e)}


def parse_semantic_evaluation(response: str) -> Dict[str, Any]:
    """
    Parse LLM semantic evaluation response.
    
    Args:
        response (str): LLM response.
        
    Returns:
        Dict[str, Any]: Parsed evaluation results.
    """
    result = {
        "correctness": "UNKNOWN",
        "confidence": "LOW",
        "issues": [],
        "explanation": ""
    }
    
    lines = response.split('\n')
    
    for line in lines:
        line = line.strip()
        if line.startswith('Correctness:'):
            correctness = line.split(':', 1)[1].strip().upper()
            if correctness in ['CORRECT', 'INCORRECT', 'PARTIAL']:
                result["correctness"] = correctness
        
        elif line.startswith('Confidence:'):
            confidence = line.split(':', 1)[1].strip().upper()
            if confidence in ['HIGH', 'MEDIUM', 'LOW']:
                result["confidence"] = confidence
        
        elif line.startswith('Issues:'):
            issues_text = line.split(':', 1)[1].strip()
            if issues_text and issues_text.lower() != 'none':
                result["issues"] = [issues_text]
        
        elif line.startswith('Explanation:'):
            explanation = line.split(':', 1)[1].strip()
            result["explanation"] = explanation
    
    return result


def calculate_overall_score(results: Dict[str, Any]) -> float:
    """
    Calculate an overall evaluation score.
    
    Args:
        results (Dict[str, Any]): All evaluation results.
        
    Returns:
        float: Overall score between 0 and 1.
    """
    score = 0.0
    max_score = 0.0
    
    # Execution score (most important)
    exec_res = results.get("exec_res", 0)
    score += exec_res * 0.6  # 60% weight
    max_score += 0.6
    
    # Syntax score
    syntax_eval = results.get("syntax_evaluation", {})
    if syntax_eval.get("syntax_correct", False):
        score += 0.2  # 20% weight
    max_score += 0.2
    
    # Semantic score (if available)
    semantic_eval = results.get("semantic_evaluation", {})
    if semantic_eval and "correctness" in semantic_eval:
        correctness = semantic_eval["correctness"]
        if correctness == "CORRECT":
            score += 0.2  # 20% weight
        elif correctness == "PARTIAL":
            score += 0.1  # 10% weight
    max_score += 0.2
    
    # Normalize score
    if max_score > 0:
        return score / max_score
    else:
        return 0.0


def generate_evaluation_summary(results: Dict[str, Any]) -> str:
    """
    Generate a human-readable evaluation summary.
    
    Args:
        results (Dict[str, Any]): Evaluation results.
        
    Returns:
        str: Evaluation summary.
    """
    summary_parts = []
    
    # Execution summary
    exec_res = results.get("exec_res", 0)
    exec_err = results.get("exec_err", "unknown")
    
    if exec_res == 1:
        summary_parts.append("✓ Execution: PASSED")
    else:
        summary_parts.append(f"✗ Execution: FAILED ({exec_err})")
    
    # Syntax summary
    syntax_eval = results.get("syntax_evaluation", {})
    if syntax_eval.get("syntax_correct", False):
        summary_parts.append("✓ Syntax: VALID")
    else:
        issues = syntax_eval.get("issues", [])
        summary_parts.append(f"✗ Syntax: ISSUES ({len(issues)} found)")
    
    # Semantic summary (if available)
    semantic_eval = results.get("semantic_evaluation", {})
    if semantic_eval and "correctness" in semantic_eval:
        correctness = semantic_eval["correctness"]
        confidence = semantic_eval.get("confidence", "UNKNOWN")
        summary_parts.append(f"Semantics: {correctness} (confidence: {confidence})")
    
    # Overall score
    overall_score = results.get("overall_score", 0.0)
    summary_parts.append(f"Overall Score: {overall_score:.2f}")
    
    return " | ".join(summary_parts)