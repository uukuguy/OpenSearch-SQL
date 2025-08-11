"""
Column retrieval and other information gathering node for OpenSearch-SQL pipeline.
"""
import json
import logging
from typing import Any, Dict, List, Tuple
from pathlib import Path

from ...core import DatabaseManager, PipelineManager, Logger
from ...llm import model_chose
from ..utils import node_decorator, get_last_node_result, safe_get_node_result


@node_decorator(check_schema_status=False)
def column_retrieve_and_other_info(task: Any, execution_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Retrieve relevant columns and gather other information needed for SQL generation.
    
    Args:
        task: Task object containing question and database information.
        execution_history: History of pipeline execution.
        
    Returns:
        Dict[str, Any]: Retrieved columns, foreign keys, values, and other info.
    """
    try:
        # Get configuration
        config, node_name = PipelineManager().get_model_para()
        paths = DatabaseManager()
        
        # Get previous results safely
        schema_result = get_last_node_result(execution_history, "generate_db_schema")
        values_result = get_last_node_result(execution_history, "extract_col_value")
        nouns_result = get_last_node_result(execution_history, "extract_query_noun")
        
        if not schema_result:
            logging.error("No database schema found in execution history")
            return {"status": "error", "error": "Missing database schema"}
        
        db_list = schema_result.get("db_list", "")
        db_col_dic = schema_result.get("db_col_dic", {})
        
        # Retrieve relevant columns
        relevant_columns = retrieve_relevant_columns(
            task.question, task.evidence, db_col_dic, values_result, nouns_result, config
        )
        
        # Get foreign keys
        foreign_keys = extract_foreign_keys(db_col_dic, paths)
        
        # Get column values for WHERE conditions
        l_values = extract_column_values(
            task.question, task.evidence, db_col_dic, values_result, paths
        )
        
        # Generate query order information
        q_order = generate_query_order_info(task.question, task.evidence, relevant_columns)
        
        # Format column information
        column_info = format_column_information(relevant_columns, db_col_dic)
        
        response = {
            "column": column_info,
            "foreign_keys": foreign_keys, 
            "L_values": l_values,
            "q_order": q_order,
            "relevant_columns": relevant_columns,
            "column_count": len(relevant_columns)
        }
        
        logging.info(f"Retrieved {len(relevant_columns)} relevant columns for task {task.db_id}_{task.question_id}")
        return response
        
    except Exception as e:
        logging.error(f"Error in column_retrieve_and_other_info: {e}")
        return {
            "column": "",
            "foreign_keys": "",
            "L_values": [],
            "q_order": "",
            "status": "error",
            "error": str(e)
        }


def retrieve_relevant_columns(question: str, evidence: str, db_col_dic: Dict[str, Any],
                            values_result: Dict[str, Any], nouns_result: Dict[str, Any],
                            config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Retrieve columns relevant to answering the question.
    
    Args:
        question (str): Question text.
        evidence (str): Evidence text.
        db_col_dic (Dict[str, Any]): Database column information.
        values_result (Dict[str, Any]): Extracted values result.
        nouns_result (Dict[str, Any]): Extracted nouns result.
        config (Dict[str, Any]): Node configuration.
        
    Returns:
        List[Dict[str, Any]]: List of relevant columns with metadata.
    """
    relevant_columns = []
    combined_text = f"{question} {evidence}".lower()
    
    # Get extracted entities and values for relevance scoring (safe access)
    extracted_values = []
    if values_result and isinstance(values_result, dict):
        extracted_values = values_result.get("extracted_values", [])
    
    extracted_entities = []
    if nouns_result and isinstance(nouns_result, dict):
        extracted_entities = nouns_result.get("combined_entities", [])
    
    # Extract keywords from question and evidence
    keywords = extract_keywords_from_text(combined_text)
    
    for table_name, table_info in db_col_dic.items():
        # Handle both dict and list formats for table_info
        if isinstance(table_info, dict):
            columns = table_info.get("columns", [])
        elif isinstance(table_info, list):
            # If table_info is a list, assume it's the columns list directly
            columns = table_info
        else:
            logging.warning(f"Unexpected table_info format for {table_name}: {type(table_info)}")
            continue
        
        for column in columns:
            # Handle various column formats
            if isinstance(column, dict):
                col_name = column.get("name", "").lower()
                col_type = column.get("type", "")
            elif hasattr(column, '_asdict'):
                # Handle namedtuple format
                col_name = getattr(column, 'name', '').lower()
                col_type = getattr(column, 'type', '')
            elif isinstance(column, (list, tuple)) and len(column) >= 2:
                # Handle list/tuple format: [name, type, ...]
                col_name = str(column[0]).lower()
                col_type = str(column[1])
            elif isinstance(column, str):
                # Handle simple string format (column name only)
                col_name = column.lower()
                col_type = "unknown"
            else:
                logging.debug(f"Skipping unexpected column format: {type(column)}")
                continue
            
            # Calculate relevance score
            relevance_score = calculate_column_relevance(
                col_name, col_type, table_name, keywords, extracted_values, extracted_entities
            )
            
            if relevance_score > 0.1:  # Minimum relevance threshold
                # Get primary key and not null info safely
                if isinstance(column, dict):
                    primary_key = column.get("primary_key", False)
                    not_null = column.get("not_null", False)
                elif hasattr(column, '_asdict'):
                    primary_key = getattr(column, 'pk', False)
                    not_null = getattr(column, 'notnull', False)
                else:
                    primary_key = False
                    not_null = False
                
                relevant_columns.append({
                    "table": table_name,
                    "column": col_name,
                    "type": col_type,
                    "relevance_score": relevance_score,
                    "primary_key": primary_key,
                    "not_null": not_null
                })
    
    # Sort by relevance score and return top columns
    relevant_columns.sort(key=lambda x: x["relevance_score"], reverse=True)
    return relevant_columns[:20]  # Limit to top 20 most relevant columns


def extract_keywords_from_text(text: str) -> List[str]:
    """
    Extract important keywords from text.
    
    Args:
        text (str): Input text.
        
    Returns:
        List[str]: List of keywords.
    """
    # Simple keyword extraction - remove stop words and short words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 
        'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'shall', 'must'
    }
    
    # Split into words and filter
    words = text.lower().split()
    keywords = [word.strip('.,!?;:"()[]') for word in words 
               if len(word) > 2 and word not in stop_words]
    
    return list(set(keywords))  # Remove duplicates


def calculate_column_relevance(col_name: str, col_type: str, table_name: str,
                              keywords: List[str], extracted_values: List[Dict[str, Any]],
                              extracted_entities: List[Dict[str, Any]]) -> float:
    """
    Calculate relevance score for a column.
    
    Args:
        col_name (str): Column name.
        col_type (str): Column data type.
        table_name (str): Table name.
        keywords (List[str]): Keywords from question.
        extracted_values (List[Dict[str, Any]]): Extracted values.
        extracted_entities (List[Dict[str, Any]]): Extracted entities.
        
    Returns:
        float: Relevance score between 0 and 1.
    """
    score = 0.0
    
    # Direct keyword match
    for keyword in keywords:
        if keyword in col_name:
            score += 0.3
        if keyword in table_name:
            score += 0.2
    
    # Match with extracted values
    for value_info in extracted_values:
        suggested_col = value_info.get("suggested_column", "").lower()
        source_col = value_info.get("source_column", "").lower()
        
        if suggested_col == col_name or source_col == col_name:
            score += 0.4
    
    # Match with extracted entities
    for entity_info in extracted_entities:
        entity_word = entity_info.get("word", "").lower()
        if entity_word in col_name or col_name in entity_word:
            score += 0.2
    
    # Boost score for common important columns
    important_columns = {'id', 'name', 'title', 'date', 'time', 'year', 'amount', 'count', 'total'}
    if any(important in col_name for important in important_columns):
        score += 0.1
    
    # Boost primary keys slightly
    if 'id' in col_name and col_name.endswith('id'):
        score += 0.1
    
    return min(score, 1.0)  # Cap at 1.0


def extract_foreign_keys(db_col_dic: Dict[str, Any], db_manager: DatabaseManager) -> str:
    """
    Extract foreign key relationships from the database.
    
    Args:
        db_col_dic (Dict[str, Any]): Database column information.
        db_manager (DatabaseManager): Database manager instance.
        
    Returns:
        str: Formatted foreign key information.
    """
    foreign_keys = []
    
    try:
        # Get foreign key information from database
        for table_name in db_col_dic.keys():
            try:
                fk_info = db_manager.execute_sql(f"PRAGMA foreign_key_list({table_name})")
                for fk in fk_info:
                    # fk structure: [id, seq, table, from, to, on_update, on_delete, match]
                    if len(fk) >= 5:
                        from_col = fk[3]
                        to_table = fk[2] 
                        to_col = fk[4]
                        foreign_keys.append(f"{table_name}.{from_col} -> {to_table}.{to_col}")
            except Exception as e:
                logging.warning(f"Could not get foreign keys for table {table_name}: {e}")
        
        # If no foreign keys found, infer from column names
        if not foreign_keys:
            foreign_keys = infer_foreign_keys_from_names(db_col_dic)
    
    except Exception as e:
        logging.warning(f"Error extracting foreign keys: {e}")
        return "No foreign key information available."
    
    if foreign_keys:
        return "Foreign Key Relationships:\n" + "\n".join(foreign_keys)
    else:
        return "No foreign key relationships found."


def infer_foreign_keys_from_names(db_col_dic: Dict[str, Any]) -> List[str]:
    """
    Infer possible foreign key relationships from column names.
    
    Args:
        db_col_dic (Dict[str, Any]): Database column information.
        
    Returns:
        List[str]: Inferred foreign key relationships.
    """
    inferred_fks = []
    
    # Collect all tables and their ID columns
    table_ids = {}
    for table_name, table_info in db_col_dic.items():
        columns = table_info.get("columns", [])
        for col in columns:
            col_name = col.get("name", "").lower()
            if col_name == "id" or (col_name.endswith("_id") and col.get("primary_key", False)):
                table_ids[table_name] = col_name
    
    # Look for foreign key patterns
    for table_name, table_info in db_col_dic.items():
        columns = table_info.get("columns", [])
        for col in columns:
            col_name = col.get("name", "").lower()
            if col_name.endswith("_id") and not col.get("primary_key", False):
                # This might be a foreign key
                potential_table = col_name[:-3]  # Remove '_id'
                
                # Look for matching table
                for ref_table, ref_id_col in table_ids.items():
                    if potential_table in ref_table.lower() or ref_table.lower() in potential_table:
                        inferred_fks.append(f"{table_name}.{col_name} -> {ref_table}.{ref_id_col}")
                        break
    
    return inferred_fks


def extract_column_values(question: str, evidence: str, db_col_dic: Dict[str, Any],
                         values_result: Dict[str, Any], db_manager: DatabaseManager) -> List[Tuple[str, str]]:
    """
    Extract specific column values for WHERE conditions.
    
    Args:
        question (str): Question text.
        evidence (str): Evidence text. 
        db_col_dic (Dict[str, Any]): Database column information.
        values_result (Dict[str, Any]): Previously extracted values.
        db_manager (DatabaseManager): Database manager instance.
        
    Returns:
        List[Tuple[str, str]]: List of (column, value) pairs.
    """
    l_values = []
    
    if values_result and "extracted_values" in values_result:
        extracted_values = values_result["extracted_values"]
        
        for value_info in extracted_values:
            value = value_info.get("value", "")
            suggested_col = value_info.get("suggested_column", "")
            source_col = value_info.get("source_column", "")
            
            # Use suggested or source column if available
            if suggested_col:
                l_values.append((suggested_col, value))
            elif source_col:
                l_values.append((source_col, value))
            else:
                # Try to match value to columns based on type and content
                matched_col = match_value_to_column(value, db_col_dic, db_manager)
                if matched_col:
                    l_values.append((matched_col, value))
    
    return l_values[:10]  # Limit to 10 values


def match_value_to_column(value: str, db_col_dic: Dict[str, Any], 
                         db_manager: DatabaseManager) -> str:
    """
    Try to match a value to an appropriate column.
    
    Args:
        value (str): Value to match.
        db_col_dic (Dict[str, Any]): Database column information.
        db_manager (DatabaseManager): Database manager instance.
        
    Returns:
        str: Best matching column name or empty string.
    """
    # For now, return empty string - this would need more sophisticated matching
    # In a full implementation, you would check column types, sample data, etc.
    return ""


def generate_query_order_info(question: str, evidence: str, 
                             relevant_columns: List[Dict[str, Any]]) -> str:
    """
    Generate query ordering information.
    
    Args:
        question (str): Question text.
        evidence (str): Evidence text.
        relevant_columns (List[Dict[str, Any]]): Relevant columns.
        
    Returns:
        str: Query ordering information.
    """
    order_info = ""
    combined_text = f"{question} {evidence}".lower()
    
    # Look for ordering keywords
    if any(keyword in combined_text for keyword in ['highest', 'largest', 'maximum', 'max', 'most']):
        order_info += "Order by DESC (highest first)\n"
    elif any(keyword in combined_text for keyword in ['lowest', 'smallest', 'minimum', 'min', 'least']):
        order_info += "Order by ASC (lowest first)\n"
    elif any(keyword in combined_text for keyword in ['first', 'earliest', 'oldest']):
        order_info += "Order by ASC (chronological order)\n"
    elif any(keyword in combined_text for keyword in ['last', 'latest', 'newest', 'recent']):
        order_info += "Order by DESC (reverse chronological order)\n"
    
    # Look for limiting keywords
    if any(keyword in combined_text for keyword in ['top', 'first', 'limit', 'only']):
        # Try to extract number
        import re
        numbers = re.findall(r'\b(\d+)\b', combined_text)
        if numbers:
            order_info += f"LIMIT {numbers[0]}\n"
        else:
            order_info += "LIMIT clause may be needed\n"
    
    return order_info.strip()


def format_column_information(relevant_columns: List[Dict[str, Any]], 
                             db_col_dic: Dict[str, Any]) -> str:
    """
    Format column information for use in prompts.
    
    Args:
        relevant_columns (List[Dict[str, Any]]): Relevant columns.
        db_col_dic (Dict[str, Any]): Database column information.
        
    Returns:
        str: Formatted column information.
    """
    if not relevant_columns:
        return "No relevant columns identified."
    
    formatted = "Relevant Columns:\n"
    
    # Group by table
    tables = {}
    for col_info in relevant_columns:
        table = col_info["table"]
        if table not in tables:
            tables[table] = []
        tables[table].append(col_info)
    
    for table_name, columns in tables.items():
        formatted += f"\nTable: {table_name}\n"
        for col_info in columns:
            col_name = col_info["column"]
            col_type = col_info["type"]
            relevance = col_info["relevance_score"]
            
            formatted += f"  - {col_name} ({col_type}) [relevance: {relevance:.2f}]"
            if col_info.get("primary_key"):
                formatted += " [PRIMARY KEY]"
            formatted += "\n"
    
    return formatted