"""
Database schema generation node for OpenSearch-SQL pipeline.
"""
import json
import os
import logging
from pathlib import Path
from typing import Any, Dict
from sentence_transformers import SentenceTransformer

from ...core import DatabaseManager, PipelineManager, Logger
from ...llm import model_chose
from ..utils import node_decorator


@node_decorator(check_schema_status=False)
def generate_db_schema(task: Any, execution_history: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate database schema information for the given task.
    
    Args:
        task: Task object containing question and database information.
        execution_history: History of pipeline execution.
        
    Returns:
        Dict[str, Any]: Database schema information including table descriptions and columns.
    """
    try:
        # Get configuration and initialize components
        config, node_name = PipelineManager().get_model_para()
        paths = DatabaseManager()
        
        # Use model pool for BERT embeddings to avoid reloading
        bert_model_path = config.get("bert_model", "BAAI/bge-m3")
        device = config.get("device", "cpu")
        
        # Initialize model pool if not already done
        from ...services.model_pool import initialize_model_pool
        
        try:
            # Initialize or get model pool manager
            pool_manager = initialize_model_pool(bert_model_path, device=device, pool_size=2)
            bert_model_context = pool_manager.get_model(bert_model_path)
            
            logging.info(f"Using BERT model from pool: {bert_model_path}")
        except Exception as e:
            logging.warning(f"Failed to initialize model pool {bert_model_path}: {e}")
            # Fallback: create model directly (not optimal but works)
            try:
                bert_model_context = None
                bert_model = SentenceTransformer(bert_model_path, device=device)
                logging.info(f"Using direct BERT model: {bert_model_path}")
            except Exception as e2:
                logging.warning(f"Failed to load BERT model directly: {e2}")
                bert_model = None
                bert_model_context = None
        
        # Get database paths
        db_json_dir = paths.db_json
        tables_info_dir = paths.db_tables
        sqlite_dir = paths.db_path
        db_dir = paths.db_directory_path
        
        # Initialize chat model
        engine = config.get("engine", "gpt-4o")
        chat_model = model_chose(node_name, engine)
        
        # Check for cached schema
        ext_file = Path(paths.db_root_path) / "db_schema.json"
        
        if ext_file.exists():
            with open(ext_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}
        
        # Check if database schema is already processed
        db = task.db_id
        existing_entry = data.get(db)
        
        if existing_entry:
            all_info, db_col = existing_entry
            logging.info(f"Using cached schema for database {db}")
        else:
            logging.info(f"Generating schema for database {db}")
            
            # Use model pool context manager if available
            if bert_model_context is not None:
                with bert_model_context as bert_model:
                    all_info, db_col = generate_database_info(
                        db, db_json_dir, tables_info_dir, sqlite_dir, db_dir, 
                        chat_model, bert_model
                    )
            else:
                all_info, db_col = generate_database_info(
                    db, db_json_dir, tables_info_dir, sqlite_dir, db_dir, 
                    chat_model, bert_model
                )
            
            # Cache the generated schema
            data[db] = [all_info, db_col]
            with open(ext_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logging.info(f"Cached schema for database {db}")
        
        response = {
            "db_list": all_info,
            "db_col_dic": db_col
        }
        
        return response
        
    except Exception as e:
        logging.error(f"Error in generate_db_schema: {e}")
        # Return minimal schema information as fallback
        return {
            "db_list": f"Database: {task.db_id}",
            "db_col_dic": {}
        }


def generate_database_info(db_id: str, db_json_dir: Path, tables_info_dir: Path,
                          sqlite_dir: Path, db_dir: Path, chat_model, bert_model) -> tuple:
    """
    Generate comprehensive database information.
    
    Args:
        db_id (str): Database identifier.
        db_json_dir (Path): Path to database JSON file.
        tables_info_dir (Path): Path to tables information file.
        sqlite_dir (Path): Path to SQLite database file.
        db_dir (Path): Path to database directory.
        chat_model: Chat model instance for generating descriptions.
        bert_model: BERT model for embeddings (can be None).
        
    Returns:
        tuple: (all_info, db_col) containing database description and column information.
    """
    try:
        # Get database manager for executing queries
        db_manager = DatabaseManager()
        
        # Get database schema
        schema = db_manager.get_database_schema()
        
        # Generate database description
        all_info = generate_database_description(db_id, schema, chat_model)
        
        # Generate column information
        db_col = generate_column_information(db_id, schema, db_manager, bert_model)
        
        return all_info, db_col
        
    except Exception as e:
        logging.error(f"Error generating database info for {db_id}: {e}")
        # Return fallback information
        fallback_info = f"Database Management System: SQLite\nDatabase name: {db_id}\nSchema information unavailable."
        fallback_col = {}
        return fallback_info, fallback_col


def generate_database_description(db_id: str, schema: Dict[str, Any], chat_model) -> str:
    """
    Generate a comprehensive database description using the chat model.
    
    Args:
        db_id (str): Database identifier.
        schema (Dict[str, Any]): Database schema information.
        chat_model: Chat model instance.
        
    Returns:
        str: Database description.
    """
    try:
        # Format schema information for the model
        schema_text = format_schema_for_description(db_id, schema)
        
        # Generate description using chat model
        from ...llm.prompts import PromptManager
        prompt_manager = PromptManager()
        prompt = prompt_manager.format_prompt("db_schema", db_info=schema_text)
        
        description = chat_model.get_ans(prompt, temperature=0.0)
        
        # Format the final description
        final_description = f"Database Management System: SQLite\n"
        final_description += f"Database name: {db_id}\n\n"
        final_description += description
        
        return final_description
        
    except Exception as e:
        logging.error(f"Error generating database description: {e}")
        # Return basic schema information as fallback
        return format_schema_for_description(db_id, schema)


def format_schema_for_description(db_id: str, schema: Dict[str, Any]) -> str:
    """
    Format schema information into a readable description.
    
    Args:
        db_id (str): Database identifier.
        schema (Dict[str, Any]): Database schema.
        
    Returns:
        str: Formatted schema description.
    """
    description = f"Database Management System: SQLite\n"
    description += f"Database name: {db_id}\n\n"
    
    for table_name, columns in schema.items():
        description += f"Table: {table_name}\n"
        description += "Columns:\n"
        
        for col_info in columns:
            col_name = col_info.get('name', 'unknown')
            col_type = col_info.get('type', 'unknown')
            is_pk = col_info.get('pk', 0)
            not_null = col_info.get('notnull', 0)
            
            description += f"  - {col_name} ({col_type})"
            if is_pk:
                description += " [PRIMARY KEY]"
            if not_null:
                description += " [NOT NULL]"
            description += "\n"
        
        description += "\n"
    
    return description


def generate_column_information(db_id: str, schema: Dict[str, Any], 
                               db_manager: DatabaseManager, bert_model) -> Dict[str, Any]:
    """
    Generate detailed column information including value samples.
    
    Args:
        db_id (str): Database identifier.
        schema (Dict[str, Any]): Database schema.
        db_manager (DatabaseManager): Database manager instance.
        bert_model: BERT model for embeddings.
        
    Returns:
        Dict[str, Any]: Column information dictionary.
    """
    try:
        db_col = {}
        
        for table_name, columns in schema.items():
            table_info = {
                "columns": [],
                "sample_values": {}
            }
            
            # Get column information
            for col_info in columns:
                col_name = col_info.get('name', 'unknown')
                col_type = col_info.get('type', 'unknown')
                
                table_info["columns"].append({
                    "name": col_name,
                    "type": col_type,
                    "primary_key": bool(col_info.get('pk', 0)),
                    "not_null": bool(col_info.get('notnull', 0))
                })
                
                # Get sample values for this column
                try:
                    sample_data = db_manager.get_sample_data(table_name, limit=5)
                    if sample_data:
                        # Find column index
                        col_names = [c['name'] for c in columns]
                        if col_name in col_names:
                            col_index = col_names.index(col_name)
                            sample_values = [row[col_index] for row in sample_data if row[col_index] is not None]
                            table_info["sample_values"][col_name] = sample_values[:3]  # Keep top 3 samples
                except Exception as e:
                    logging.warning(f"Could not get sample values for {table_name}.{col_name}: {e}")
            
            db_col[table_name] = table_info
        
        return db_col
        
    except Exception as e:
        logging.error(f"Error generating column information: {e}")
        return {}