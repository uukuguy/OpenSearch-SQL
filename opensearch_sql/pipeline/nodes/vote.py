"""
Voting node for OpenSearch-SQL pipeline.
"""
from ...utils.loguru_config import get_logger
from typing import Any, Dict, List
from collections import Counter

from ...core import DatabaseManager, PipelineManager, Logger
from ...llm import model_chose
from ..utils import node_decorator, get_last_node_result


logger = get_logger(__name__)

@node_decorator(check_schema_status=False)
def vote(task: Any, execution_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Vote on the best SQL query from multiple candidates or alignment results.
    
    Args:
        task: Task object containing question and database information.
        execution_history: History of pipeline execution.
        
    Returns:
        Dict[str, Any]: Final voted SQL query and voting information.
    """
    try:
        # Get configuration
        config, node_name = PipelineManager().get_model_para()
        db_manager = DatabaseManager()
        
        # Get SQL candidates from previous nodes
        candidates = collect_sql_candidates(execution_history)
        
        if not candidates:
            logger.error("No SQL candidates found for voting")
            return {"status": "error", "error": "No SQL candidates available for voting"}
        
        # Get voting method from config
        voting_method = config.get("voting_method", "execution_based")
        use_llm_voting = config.get("use_llm_voting", False)
        
        # Apply voting strategy
        if voting_method == "execution_based":
            voted_sql, voting_info = execution_based_voting(candidates, db_manager, task)
        elif voting_method == "similarity_based":
            voted_sql, voting_info = similarity_based_voting(candidates, task)
        elif voting_method == "llm_based" or use_llm_voting:
            # Get schema for LLM voting
            schema_result = get_last_node_result(execution_history, "generate_db_schema")
            db_schema = schema_result.get("db_list", "") if schema_result else ""
            
            engine = config.get("engine", "gpt-4o")
            chat_model = model_chose(node_name, engine)
            voted_sql, voting_info = llm_based_voting(candidates, task, db_schema, chat_model)
        else:
            # Default to simple voting
            voted_sql, voting_info = simple_voting(candidates)
        
        response = {
            "SQL": voted_sql,
            "voting_method": voting_method,
            "voting_info": voting_info,
            "candidate_count": len(candidates),
            "candidates": candidates
        }
        
        logger.info(f"Voted SQL for task {task.db_id}_{task.question_id}: method={voting_method}")
        return response
        
    except Exception as e:
        logger.error(f"Error in vote: {e}")
        return {
            "SQL": "",
            "status": "error",
            "error": str(e)
        }


def collect_sql_candidates(execution_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Collect SQL candidates from previous pipeline nodes.
    
    Args:
        execution_history: Pipeline execution history.
        
    Returns:
        List[Dict[str, Any]]: List of SQL candidates with metadata.
    """
    candidates = []
    
    # Get candidates from align_correct node
    align_result = get_last_node_result(execution_history, "align_correct")
    if align_result and align_result.get("SQL"):
        candidates.append({
            "sql": align_result["SQL"],
            "source": "align_correct",
            "original_sql": align_result.get("original_SQL"),
            "corrections": align_result.get("corrections_applied", []),
            "priority": 10  # Highest priority for corrected SQL
        })
    
    # Get candidates from candidate_generate node
    candidate_result = get_last_node_result(execution_history, "candidate_generate")
    if candidate_result:
        sql_candidates = candidate_result.get("SQL", "")
        if isinstance(sql_candidates, str):
            sql_candidates = [sql_candidates]
        
        for i, sql in enumerate(sql_candidates):
            if sql and sql.strip():
                candidates.append({
                    "sql": sql,
                    "source": "candidate_generate",
                    "index": i,
                    "priority": 5  # Medium priority for raw candidates
                })
    
    # Remove duplicates (same SQL)
    unique_candidates = []
    seen_sqls = set()
    
    for candidate in candidates:
        sql_normalized = normalize_sql_for_comparison(candidate["sql"])
        if sql_normalized not in seen_sqls:
            seen_sqls.add(sql_normalized)
            unique_candidates.append(candidate)
    
    return unique_candidates


def normalize_sql_for_comparison(sql: str) -> str:
    """
    Normalize SQL query for comparison purposes.
    
    Args:
        sql (str): SQL query.
        
    Returns:
        str: Normalized SQL.
    """
    if not sql:
        return ""
    
    # Convert to uppercase and remove extra whitespace
    normalized = " ".join(sql.strip().upper().split())
    
    # Remove semicolon if present
    if normalized.endswith(';'):
        normalized = normalized[:-1]
    
    return normalized


def execution_based_voting(candidates: List[Dict[str, Any]], 
                          db_manager: DatabaseManager, task) -> tuple:
    """
    Vote based on SQL execution results.
    
    Args:
        candidates: List of SQL candidates.
        db_manager: Database manager instance.
        task: Task object.
        
    Returns:
        tuple: (voted_sql, voting_info)
    """
    scored_candidates = []
    
    for candidate in candidates:
        sql = candidate["sql"]
        score = 0.0
        execution_info = {}
        
        try:
            # Try to execute the SQL
            result = db_manager.validate_sql_query(sql, max_returned_rows=10)
            
            if result["STATUS"] == "OK":
                score += 5.0  # Base score for successful execution
                execution_info["executable"] = True
                execution_info["result_count"] = len(result.get("RESULT", []))
                
                # Bonus for reasonable result size
                result_count = execution_info["result_count"]
                if 1 <= result_count <= 100:
                    score += 2.0
                elif result_count == 0:
                    score += 1.0  # Empty results might be correct
                
            else:
                execution_info["executable"] = False
                execution_info["error"] = result.get("RESULT", "Unknown error")
                score -= 2.0  # Penalty for non-executable SQL
            
        except Exception as e:
            execution_info["executable"] = False
            execution_info["error"] = str(e)
            score -= 2.0
        
        # Add priority bonus
        score += candidate.get("priority", 0)
        
        scored_candidates.append({
            **candidate,
            "execution_score": score,
            "execution_info": execution_info
        })
    
    # Sort by execution score and select the best
    scored_candidates.sort(key=lambda x: x["execution_score"], reverse=True)
    
    if scored_candidates:
        best_candidate = scored_candidates[0]
        voting_info = {
            "method": "execution_based",
            "winner": best_candidate,
            "all_scores": [(c["sql"][:50] + "...", c["execution_score"]) for c in scored_candidates],
            "executable_count": sum(1 for c in scored_candidates if c["execution_info"].get("executable", False))
        }
        return best_candidate["sql"], voting_info
    
    return "", {"method": "execution_based", "error": "No candidates to vote on"}


def similarity_based_voting(candidates: List[Dict[str, Any]], task) -> tuple:
    """
    Vote based on similarity between candidates.
    
    Args:
        candidates: List of SQL candidates.
        task: Task object.
        
    Returns:
        tuple: (voted_sql, voting_info)
    """
    if len(candidates) == 1:
        return candidates[0]["sql"], {"method": "similarity_based", "winner": "only_candidate"}
    
    # Count similar SQL structures
    sql_patterns = []
    for candidate in candidates:
        sql = candidate["sql"]
        pattern = extract_sql_pattern(sql)
        sql_patterns.append(pattern)
    
    # Find the most common pattern
    pattern_counts = Counter(sql_patterns)
    most_common_pattern, count = pattern_counts.most_common(1)[0]
    
    # Find the best candidate with the most common pattern
    pattern_candidates = [
        candidates[i] for i, pattern in enumerate(sql_patterns)
        if pattern == most_common_pattern
    ]
    
    # Among pattern matches, select by priority
    best_candidate = max(pattern_candidates, key=lambda x: x.get("priority", 0))
    
    voting_info = {
        "method": "similarity_based",
        "most_common_pattern": most_common_pattern,
        "pattern_count": count,
        "total_patterns": len(set(sql_patterns)),
        "winner": best_candidate
    }
    
    return best_candidate["sql"], voting_info


def extract_sql_pattern(sql: str) -> str:
    """
    Extract a simplified pattern from SQL for similarity comparison.
    
    Args:
        sql (str): SQL query.
        
    Returns:
        str: Simplified SQL pattern.
    """
    if not sql:
        return ""
    
    # Extract main SQL keywords and structure
    import re
    
    sql_upper = sql.upper()
    
    # Extract main clauses
    pattern_parts = []
    
    if "SELECT" in sql_upper:
        pattern_parts.append("SELECT")
    if "FROM" in sql_upper:
        pattern_parts.append("FROM")
    if "WHERE" in sql_upper:
        pattern_parts.append("WHERE")
    if "GROUP BY" in sql_upper:
        pattern_parts.append("GROUP_BY")
    if "ORDER BY" in sql_upper:
        pattern_parts.append("ORDER_BY")
    if "HAVING" in sql_upper:
        pattern_parts.append("HAVING")
    if "LIMIT" in sql_upper:
        pattern_parts.append("LIMIT")
    
    # Check for functions
    if re.search(r'\b(COUNT|SUM|AVG|MAX|MIN)\s*\(', sql_upper):
        pattern_parts.append("AGGREGATE")
    if "JOIN" in sql_upper:
        pattern_parts.append("JOIN")
    
    return "_".join(pattern_parts)


def llm_based_voting(candidates: List[Dict[str, Any]], task, db_schema: str, chat_model) -> tuple:
    """
    Vote using LLM to evaluate candidates.
    
    Args:
        candidates: List of SQL candidates.
        task: Task object.
        db_schema: Database schema.
        chat_model: Chat model instance.
        
    Returns:
        tuple: (voted_sql, voting_info)
    """
    try:
        # Format candidates for LLM
        candidate_text = ""
        for i, candidate in enumerate(candidates):
            candidate_text += f"\nCandidate {i+1}:\n{candidate['sql']}\n"
        
        # Create voting prompt
        voting_prompt = f"""
Please evaluate these SQL query candidates and select the best one for answering the question:

Question: {task.question}
Evidence: {task.evidence}
Database Schema: {db_schema}

SQL Candidates:{candidate_text}

Please analyze each candidate for:
1. Correctness in answering the question
2. Proper SQL syntax and structure  
3. Appropriate use of database schema
4. Completeness of the answer
5. Efficiency and best practices

Select the best candidate number (1, 2, 3, etc.) and briefly explain why:
"""
        
        response = chat_model.get_ans(voting_prompt, temperature=0.0)
        
        # Parse LLM response to extract selection
        selected_candidate, explanation = parse_llm_voting_response(response, candidates)
        
        voting_info = {
            "method": "llm_based",
            "llm_response": response,
            "explanation": explanation,
            "winner": selected_candidate
        }
        
        return selected_candidate["sql"], voting_info
        
    except Exception as e:
        logger.warning(f"LLM voting failed: {e}")
        # Fallback to simple voting
        return simple_voting(candidates)


def parse_llm_voting_response(response: str, candidates: List[Dict[str, Any]]) -> tuple:
    """
    Parse LLM voting response to extract the selected candidate.
    
    Args:
        response (str): LLM response.
        candidates: List of candidates.
        
    Returns:
        tuple: (selected_candidate, explanation)
    """
    import re
    
    # Look for candidate number in response
    number_pattern = r'candidate\s*(\d+)'
    matches = re.findall(number_pattern, response, re.IGNORECASE)
    
    if matches:
        try:
            selected_index = int(matches[0]) - 1  # Convert to 0-based index
            if 0 <= selected_index < len(candidates):
                return candidates[selected_index], response
        except (ValueError, IndexError):
            pass
    
    # Fallback: return highest priority candidate
    best_candidate = max(candidates, key=lambda x: x.get("priority", 0))
    return best_candidate, f"Could not parse LLM selection, using highest priority candidate"


def simple_voting(candidates: List[Dict[str, Any]]) -> tuple:
    """
    Simple voting based on candidate priority.
    
    Args:
        candidates: List of SQL candidates.
        
    Returns:
        tuple: (voted_sql, voting_info)
    """
    if not candidates:
        return "", {"method": "simple", "error": "No candidates"}
    
    # Select candidate with highest priority
    best_candidate = max(candidates, key=lambda x: x.get("priority", 0))
    
    voting_info = {
        "method": "simple",
        "winner": best_candidate,
        "selection_reason": "highest_priority"
    }
    
    return best_candidate["sql"], voting_info