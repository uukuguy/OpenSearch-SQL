"""
Configuration helper utilities for OpenSearch-SQL pipeline.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigHelper:
    """
    Helper class for managing configuration files and settings.
    """
    
    @staticmethod
    def create_default_config() -> Dict[str, Any]:
        """
        Create a default configuration template.
        
        Returns:
            Dict[str, Any]: Default configuration.
        """
        return {
            "generate_db_schema": {
                "engine": "gpt-4o",
                "temperature": 0.0,
                "bert_model": "BAAI/bge-m3",
                "device": "cpu"
            },
            "extract_col_value": {
                "engine": "gpt-4o",
                "temperature": 0.0,
                "use_llm": True
            },
            "extract_query_noun": {
                "engine": "gpt-4o", 
                "temperature": 0.0,
                "use_llm": True
            },
            "column_retrieve_and_other_info": {
                "engine": "gpt-4o",
                "temperature": 0.0,
                "max_columns": 20
            },
            "candidate_generate": {
                "engine": "gpt-4o",
                "temperature": 0.0,
                "n": 1,
                "single": "true",
                "return_question": "false"
            },
            "align_correct": {
                "engine": "gpt-4o",
                "temperature": 0.0,
                "alignment_methods": ["style_align", "function_align"]
            },
            "vote": {
                "engine": "gpt-4o",
                "temperature": 0.0,
                "voting_method": "execution_based",
                "use_llm_voting": False
            },
            "evaluation": {
                "engine": "gpt-4o",
                "temperature": 0.0,
                "use_llm_evaluation": False
            }
        }
    
    @staticmethod
    def save_config(config: Dict[str, Any], config_path: str):
        """
        Save configuration to file.
        
        Args:
            config (Dict[str, Any]): Configuration to save.
            config_path (str): Path to save the configuration.
        """
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            logging.info(f"Configuration saved to: {config_path}")
        except Exception as e:
            logging.error(f"Error saving configuration: {e}")
            raise
    
    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Args:
            config_path (str): Path to the configuration file.
            
        Returns:
            Dict[str, Any]: Loaded configuration.
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logging.info(f"Configuration loaded from: {config_path}")
            return config
        except Exception as e:
            logging.error(f"Error loading configuration: {e}")
            raise
    
    @staticmethod
    def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two configurations, with override_config taking precedence.
        
        Args:
            base_config (Dict[str, Any]): Base configuration.
            override_config (Dict[str, Any]): Override configuration.
            
        Returns:
            Dict[str, Any]: Merged configuration.
        """
        merged = base_config.copy()
        
        for key, value in override_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = ConfigHelper.merge_configs(merged[key], value)
            else:
                merged[key] = value
        
        return merged
    
    @staticmethod
    def validate_node_config(node_name: str, config: Dict[str, Any]) -> bool:
        """
        Validate configuration for a specific node.
        
        Args:
            node_name (str): Name of the node.
            config (Dict[str, Any]): Node configuration.
            
        Returns:
            bool: True if valid, False otherwise.
        """
        required_fields = {
            "generate_db_schema": ["engine"],
            "extract_col_value": ["engine"],
            "extract_query_noun": ["engine"],
            "column_retrieve_and_other_info": ["engine"],
            "candidate_generate": ["engine", "n"],
            "align_correct": ["engine"],
            "vote": ["engine", "voting_method"],
            "evaluation": ["engine"]
        }
        
        if node_name not in required_fields:
            logging.warning(f"Unknown node: {node_name}")
            return True  # Allow unknown nodes
        
        for field in required_fields[node_name]:
            if field not in config:
                logging.error(f"Missing required field '{field}' for node '{node_name}'")
                return False
        
        return True


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from file or return default.
    
    Args:
        config_path (Optional[str]): Path to configuration file.
        
    Returns:
        Dict[str, Any]: Configuration dictionary.
    """
    if config_path and Path(config_path).exists():
        return ConfigHelper.load_config(config_path)
    else:
        logging.info("Using default configuration")
        return ConfigHelper.create_default_config()


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate the complete pipeline configuration.
    
    Args:
        config (Dict[str, Any]): Configuration to validate.
        
    Returns:
        bool: True if valid, False otherwise.
    """
    for node_name, node_config in config.items():
        if not ConfigHelper.validate_node_config(node_name, node_config):
            return False
    
    return True


def create_sample_config_file(output_path: str):
    """
    Create a sample configuration file for reference.
    
    Args:
        output_path (str): Path to save the sample configuration.
    """
    config = ConfigHelper.create_default_config()
    
    # Add comments in the form of special keys
    config["_info"] = {
        "description": "OpenSearch-SQL Pipeline Configuration",
        "version": "1.0",
        "instructions": {
            "engines": "Supported engines: gpt-4o, claude-3-opus, mock",
            "temperature": "Temperature for LLM sampling (0.0 = deterministic, 1.0 = random)",
            "n": "Number of candidates to generate",
            "bert_model": "BERT model for embeddings (default: BAAI/bge-m3)",
            "voting_method": "Options: execution_based, similarity_based, llm_based"
        }
    }
    
    ConfigHelper.save_config(config, output_path)
    logging.info(f"Sample configuration created at: {output_path}")


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "create_sample":
        output_file = sys.argv[2] if len(sys.argv) > 2 else "sample_config.json"
        create_sample_config_file(output_file)
    else:
        # Test configuration loading
        config = load_config()
        print("Default configuration:")
        print(json.dumps(config, indent=2))