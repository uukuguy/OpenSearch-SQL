"""
Data handling helper utilities for OpenSearch-SQL pipeline.
"""
import json
from ..utils.loguru_config import get_logger
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


logger = get_logger(__name__)
class DataHelper:
    """
    Helper class for managing dataset loading and validation.
    """
    
    @staticmethod
    def load_bird_dataset(data_root: str, data_mode: str = "dev") -> List[Dict[str, Any]]:
        """
        Load the BIRD dataset from the specified path.
        
        Args:
            data_root (str): Root path to the BIRD dataset.
            data_mode (str): Data mode ('dev' or 'train').
            
        Returns:
            List[Dict[str, Any]]: Loaded dataset.
        """
        possible_paths = [
            f"{data_root}/dev_20240627/dev.json",  # Primary path for dev data
            f"{data_root}/data_preprocess/{data_mode}.json",  # Preprocessed data
            f"{data_root}/{data_mode}/{data_mode}.json",  # Standard structure
            f"{data_root}/{data_mode}.json"  # Direct file
        ]
        
        for data_path in possible_paths:
            if Path(data_path).exists():
                try:
                    with open(data_path, 'r', encoding='utf-8') as f:
                        dataset = json.load(f)
                    
                    logger.info(f"Loaded dataset from: {data_path}")
                    logger.info(f"Dataset contains {len(dataset)} items")
                    
                    return dataset
                except Exception as e:
                    logger.warning(f"Error loading from {data_path}: {e}")
                    continue
        
        raise FileNotFoundError(f"Could not find dataset file in any of: {possible_paths}")
    
    @staticmethod
    def validate_dataset_structure(dataset: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Validate the structure of a loaded dataset.
        
        Args:
            dataset (List[Dict[str, Any]]): Dataset to validate.
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_issues)
        """
        issues = []
        
        if not isinstance(dataset, list):
            issues.append("Dataset is not a list")
            return False, issues
        
        if len(dataset) == 0:
            issues.append("Dataset is empty")
            return False, issues
        
        required_fields = ["question_id", "db_id", "question", "evidence"]
        optional_fields = ["SQL", "difficulty"]
        
        for i, item in enumerate(dataset):
            if not isinstance(item, dict):
                issues.append(f"Item {i} is not a dictionary")
                continue
            
            # Check required fields
            for field in required_fields:
                if field not in item:
                    # question_id might be missing and added later
                    if field == "question_id":
                        continue
                    issues.append(f"Item {i} missing required field: {field}")
            
            # Check field types
            if "question_id" in item and not isinstance(item["question_id"], int):
                issues.append(f"Item {i} has non-integer question_id")
            
            if "db_id" in item and not isinstance(item["db_id"], str):
                issues.append(f"Item {i} has non-string db_id")
            
            if "question" in item and not isinstance(item["question"], str):
                issues.append(f"Item {i} has non-string question")
            
            if "evidence" in item and not isinstance(item["evidence"], str):
                issues.append(f"Item {i} has non-string evidence")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    @staticmethod
    def get_dataset_statistics(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get statistics about the dataset.
        
        Args:
            dataset (List[Dict[str, Any]]): Dataset to analyze.
            
        Returns:
            Dict[str, Any]: Dataset statistics.
        """
        if not dataset:
            return {"total_items": 0}
        
        stats = {
            "total_items": len(dataset),
            "unique_databases": len(set(item.get("db_id", "unknown") for item in dataset)),
            "has_sql": sum(1 for item in dataset if item.get("SQL")),
            "has_difficulty": sum(1 for item in dataset if item.get("difficulty")),
            "difficulty_distribution": {},
            "database_distribution": {},
            "question_length_stats": {},
            "evidence_length_stats": {}
        }
        
        # Difficulty distribution
        difficulties = [item.get("difficulty") for item in dataset if item.get("difficulty")]
        if difficulties:
            for diff in set(difficulties):
                stats["difficulty_distribution"][diff] = difficulties.count(diff)
        
        # Database distribution
        db_ids = [item.get("db_id", "unknown") for item in dataset]
        for db_id in set(db_ids):
            stats["database_distribution"][db_id] = db_ids.count(db_id)
        
        # Question length statistics
        question_lengths = [len(item.get("question", "")) for item in dataset]
        if question_lengths:
            stats["question_length_stats"] = {
                "min": min(question_lengths),
                "max": max(question_lengths),
                "avg": sum(question_lengths) / len(question_lengths)
            }
        
        # Evidence length statistics
        evidence_lengths = [len(item.get("evidence", "")) for item in dataset]
        if evidence_lengths:
            stats["evidence_length_stats"] = {
                "min": min(evidence_lengths),
                "max": max(evidence_lengths),
                "avg": sum(evidence_lengths) / len(evidence_lengths)
            }
        
        return stats
    
    @staticmethod
    def filter_dataset(dataset: List[Dict[str, Any]], 
                      db_ids: Optional[List[str]] = None,
                      difficulties: Optional[List[str]] = None,
                      min_question_length: Optional[int] = None,
                      max_question_length: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Filter dataset based on various criteria.
        
        Args:
            dataset (List[Dict[str, Any]]): Dataset to filter.
            db_ids (Optional[List[str]]): Database IDs to include.
            difficulties (Optional[List[str]]): Difficulties to include.
            min_question_length (Optional[int]): Minimum question length.
            max_question_length (Optional[int]): Maximum question length.
            
        Returns:
            List[Dict[str, Any]]: Filtered dataset.
        """
        filtered = dataset
        
        if db_ids:
            filtered = [item for item in filtered if item.get("db_id") in db_ids]
        
        if difficulties:
            filtered = [item for item in filtered if item.get("difficulty") in difficulties]
        
        if min_question_length is not None:
            filtered = [item for item in filtered if len(item.get("question", "")) >= min_question_length]
        
        if max_question_length is not None:
            filtered = [item for item in filtered if len(item.get("question", "")) <= max_question_length]
        
        logger.info(f"Filtered dataset from {len(dataset)} to {len(filtered)} items")
        return filtered
    
    @staticmethod
    def verify_database_files(data_root: str, dataset: List[Dict[str, Any]], 
                             data_mode: str = "dev") -> Dict[str, bool]:
        """
        Verify that database files exist for all database IDs in the dataset.
        
        Args:
            data_root (str): Root path to the BIRD dataset.
            dataset (List[Dict[str, Any]]): Dataset to check.
            data_mode (str): Data mode ('dev' or 'train').
            
        Returns:
            Dict[str, bool]: Database ID to existence mapping.
        """
        db_ids = set(item.get("db_id") for item in dataset)
        db_existence = {}
        
        for db_id in db_ids:
            if not db_id:
                continue
                
            # Check for database files
            db_paths = [
                f"{data_root}/dev_20240627/dev_databases/{db_id}/{db_id}.sqlite",
                f"{data_root}/{data_mode}/{data_mode}_databases/{db_id}/{db_id}.sqlite",
                f"{data_root}/{data_mode}_databases/{db_id}/{db_id}.sqlite"
            ]
            
            exists = any(Path(db_path).exists() for db_path in db_paths)
            db_existence[db_id] = exists
            
            if not exists:
                logger.warning(f"Database file not found for {db_id}")
        
        missing_count = sum(1 for exists in db_existence.values() if not exists)
        if missing_count > 0:
            logger.warning(f"{missing_count} database files are missing")
        else:
            logger.info("All database files found")
        
        return db_existence


def load_bird_dataset(data_root: str, data_mode: str = "dev", 
                     validate: bool = True) -> List[Dict[str, Any]]:
    """
    Load and optionally validate BIRD dataset.
    
    Args:
        data_root (str): Root path to the BIRD dataset.
        data_mode (str): Data mode ('dev' or 'train').
        validate (bool): Whether to validate the dataset structure.
        
    Returns:
        List[Dict[str, Any]]: Loaded dataset.
    """
    dataset = DataHelper.load_bird_dataset(data_root, data_mode)
    
    if validate:
        is_valid, issues = DataHelper.validate_dataset_structure(dataset)
        if not is_valid:
            logger.warning(f"Dataset validation found {len(issues)} issues:")
            for issue in issues[:5]:  # Show first 5 issues
                logger.warning(f"  - {issue}")
            if len(issues) > 5:
                logger.warning(f"  - ... and {len(issues) - 5} more issues")
    
    return dataset


def validate_dataset(dataset: List[Dict[str, Any]], 
                    data_root: Optional[str] = None) -> bool:
    """
    Validate dataset structure and optionally check database files.
    
    Args:
        dataset (List[Dict[str, Any]]): Dataset to validate.
        data_root (Optional[str]): Root path to check database files.
        
    Returns:
        bool: True if valid, False otherwise.
    """
    # Validate structure
    is_valid, issues = DataHelper.validate_dataset_structure(dataset)
    
    if not is_valid:
        logger.error("Dataset structure validation failed:")
        for issue in issues:
            logger.error(f"  - {issue}")
        return False
    
    # Validate database files if data_root provided
    if data_root:
        db_existence = DataHelper.verify_database_files(data_root, dataset)
        missing_dbs = [db_id for db_id, exists in db_existence.items() if not exists]
        
        if missing_dbs:
            logger.error(f"Missing database files for: {missing_dbs}")
            return False
    
    return True


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        data_root = sys.argv[1]
        data_mode = sys.argv[2] if len(sys.argv) > 2 else "dev"
        
        try:
            dataset = load_bird_dataset(data_root, data_mode)
            stats = DataHelper.get_dataset_statistics(dataset)
            
            print(f"Dataset Statistics:")
            print(json.dumps(stats, indent=2))
            
        except Exception as e:
            logger.error(f"Error: {e}")
    else:
        print("Usage: python data_helper.py <data_root> [data_mode]")
        print("Example: python data_helper.py ./Bird dev")