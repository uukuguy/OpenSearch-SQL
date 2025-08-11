"""
Column value extraction node for OpenSearch-SQL pipeline.
"""
import json
import logging
import re
from typing import Any, Dict, List, Tuple

from ...core import DatabaseManager, PipelineManager, Logger
from ...llm import model_chose
from ..utils import node_decorator, get_last_node_result


@node_decorator(check_schema_status=False)
def extract_col_value(task: Any, execution_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract column values mentioned in the question.
    
    Args:
        task: Task object containing question and database information.
        execution_history: History of pipeline execution.
        
    Returns:
        Dict[str, Any]: Extracted column values and related information.
    """
    try:
        # Get configuration and initialize components
        config, node_name = PipelineManager().get_model_para()
        paths = DatabaseManager()
        
        # Get database schema from previous node
        schema_result = get_last_node_result(execution_history, "generate_db_schema")
        if not schema_result:
            logging.error("No database schema found in execution history")
            return {"extracted_values": [], "status": "error", "error": "Missing database schema"}
        
        db_schema = schema_result.get("db_list", "")
        db_col_dic = schema_result.get("db_col_dic", {})
        
        # Initialize chat model if needed
        use_llm = config.get("use_llm", True)
        if use_llm:
            engine = config.get("engine", "gpt-4o")
            chat_model = model_chose(node_name, engine)
        else:
            chat_model = None
        
        # Extract values using multiple methods
        extracted_values = []
        
        # Method 1: Direct pattern matching
        pattern_values = extract_values_by_pattern(task.question, task.evidence)
        extracted_values.extend(pattern_values)
        
        # Method 2: Database sample matching
        db_values = extract_values_from_database_samples(task.question, task.evidence, db_col_dic, paths)
        extracted_values.extend(db_values)
        
        # Method 3: LLM-based extraction (if enabled)
        if chat_model:
            llm_values = extract_values_with_llm(task.question, task.evidence, db_schema, chat_model)
            extracted_values.extend(llm_values)
        
        # Remove duplicates and clean up
        cleaned_values = clean_and_deduplicate_values(extracted_values)
        
        response = {
            "extracted_values": cleaned_values,
            "total_values": len(cleaned_values),
            "extraction_methods": {
                "pattern_matching": len(pattern_values),
                "database_samples": len(db_values),
                "llm_extraction": len(llm_values) if chat_model else 0
            }
        }
        
        logging.info(f"Extracted {len(cleaned_values)} values for task {task.db_id}_{task.question_id}")
        return response
        
    except Exception as e:
        logging.error(f"Error in extract_col_value: {e}")
        return {
            "extracted_values": [],
            "status": "error",
            "error": str(e)
        }


def extract_values_by_pattern(question: str, evidence: str) -> List[Dict[str, Any]]:
    """
    Extract values using pattern matching.
    
    Args:
        question (str): Question text.
        evidence (str): Evidence text.
        
    Returns:
        List[Dict[str, Any]]: List of extracted values with metadata.
    """
    extracted_values = []
    combined_text = f"{question} {evidence}".lower()
    
    # Pattern 1: Quoted strings
    quoted_pattern = r"['\"]([^'\"]+)['\"]"
    quoted_matches = re.findall(quoted_pattern, combined_text)
    for match in quoted_matches:
        if len(match) > 1:  # Skip single characters
            extracted_values.append({
                "value": match,
                "type": "string",
                "method": "quoted_pattern",
                "confidence": 0.9
            })
    
    # Pattern 2: Numbers
    number_pattern = r'\b(\d+(?:\.\d+)?)\b'
    number_matches = re.findall(number_pattern, combined_text)
    for match in number_matches:
        extracted_values.append({
            "value": match,
            "type": "number",
            "method": "number_pattern", 
            "confidence": 0.8
        })
    
    # Pattern 3: Years (4-digit numbers between 1900-2030)
    year_pattern = r'\b(19\d{2}|20[0-3]\d)\b'
    year_matches = re.findall(year_pattern, combined_text)
    for match in year_matches:
        extracted_values.append({
            "value": match,
            "type": "year",
            "method": "year_pattern",
            "confidence": 0.95
        })
    
    # Pattern 4: Common named entities (basic)
    capitalized_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
    capitalized_matches = re.findall(capitalized_pattern, question + " " + evidence)
    for match in capitalized_matches:
        if len(match.split()) <= 3:  # Limit to reasonable entity length
            extracted_values.append({
                "value": match,
                "type": "entity",
                "method": "capitalized_pattern",
                "confidence": 0.6
            })
    
    return extracted_values


def extract_values_from_database_samples(question: str, evidence: str, 
                                        db_col_dic: Dict[str, Any], 
                                        db_manager: DatabaseManager) -> List[Dict[str, Any]]:
    """
    Extract values by matching against database sample data.
    
    Args:
        question (str): Question text.
        evidence (str): Evidence text.
        db_col_dic (Dict[str, Any]): Database column information.
        db_manager (DatabaseManager): Database manager instance.
        
    Returns:
        List[Dict[str, Any]]: List of extracted values with metadata.
    """
    extracted_values = []
    combined_text = (question + " " + evidence).lower()
    
    try:
        for table_name, table_info in db_col_dic.items():
            # Handle both dict and list formats for table_info
            if isinstance(table_info, dict):
                sample_values = table_info.get("sample_values", {})
            elif isinstance(table_info, list):
                # If it's a list, skip sample value extraction for now
                logging.debug(f"Skipping sample values for table {table_name} (list format)")
                continue
            else:
                logging.warning(f"Unexpected table_info format for {table_name}: {type(table_info)}")
                continue
            
            for column_name, values in sample_values.items():
                if isinstance(values, (list, tuple)):
                    for value in values:
                        if value is not None:
                            value_str = str(value).lower()
                            # Check if this value appears in the question/evidence
                            if value_str in combined_text and len(value_str) > 2:
                                extracted_values.append({
                                    "value": str(value),
                                    "type": "database_value",
                                    "method": "database_sample",
                                    "confidence": 0.85,
                                    "source_table": table_name,
                                    "source_column": column_name
                                })
    
    except Exception as e:
        logging.warning(f"Error extracting values from database samples: {e}")
    
    return extracted_values


def extract_values_with_llm(question: str, evidence: str, db_schema: str, 
                           chat_model) -> List[Dict[str, Any]]:
    """
    Extract values using LLM analysis.
    
    Args:
        question (str): Question text.
        evidence (str): Evidence text.
        db_schema (str): Database schema description.
        chat_model: Chat model instance.
        
    Returns:
        List[Dict[str, Any]]: List of extracted values with metadata.
    """
    try:
        from ...llm.prompts import PromptManager
        prompt_manager = PromptManager()
        
        prompt = prompt_manager.format_prompt(
            "extract_col_value",
            question=question,
            db_schema=db_schema
        )
        
        response = chat_model.get_ans(prompt, temperature=0.0)
        
        # Parse LLM response
        extracted_values = parse_llm_value_response(response)
        
        return extracted_values
        
    except Exception as e:
        logging.warning(f"Error extracting values with LLM: {e}")
        return []


def parse_llm_value_response(response: str) -> List[Dict[str, Any]]:
    """
    Parse LLM response to extract structured value information.
    
    Args:
        response (str): LLM response text.
        
    Returns:
        List[Dict[str, Any]]: Parsed values with metadata.
    """
    extracted_values = []
    
    try:
        # Look for patterns like "Column: type = value"
        pattern = r'(\w+):\s*(\w+)\s*=\s*["\']?([^"\'\\n]+)["\']?'
        matches = re.findall(pattern, response, re.IGNORECASE)
        
        for column, value_type, value in matches:
            extracted_values.append({
                "value": value.strip(),
                "type": value_type.lower(),
                "method": "llm_extraction",
                "confidence": 0.7,
                "suggested_column": column
            })
    
    except Exception as e:
        logging.warning(f"Error parsing LLM value response: {e}")
    
    return extracted_values


def clean_and_deduplicate_values(values: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean and deduplicate extracted values.
    
    Args:
        values (List[Dict[str, Any]]): Raw extracted values.
        
    Returns:
        List[Dict[str, Any]]: Cleaned and deduplicated values.
    """
    # Remove duplicates based on value
    seen_values = set()
    cleaned_values = []
    
    # Sort by confidence descending
    sorted_values = sorted(values, key=lambda x: x.get('confidence', 0), reverse=True)
    
    for value_info in sorted_values:
        value = value_info['value'].strip()
        
        # Skip empty or very short values
        if len(value) < 2:
            continue
            
        # Skip common stop words and articles
        if value.lower() in {'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}:
            continue
        
        # Add if not seen before
        if value.lower() not in seen_values:
            seen_values.add(value.lower())
            cleaned_values.append(value_info)
    
    # Limit to reasonable number of values
    return cleaned_values[:20]