#!/usr/bin/env python3
"""
Results collector for OpenSearch-SQL pipeline.
Collects and persists question-SQL pairs while maintaining dataset order.
"""

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from .loguru_config import get_logger

logger = get_logger(__name__)


class ResultsCollector:
    """
    Thread-safe results collector that maintains dataset order.
    Collects question-SQL pairs and other metadata for persistence.
    """

    def __init__(self, result_directory: str, dataset_size: int = 0):
        """
        Initialize the results collector.
        
        Args:
            result_directory (str): Directory to save results
            dataset_size (int): Total size of dataset for order preservation
        """
        self.result_directory = Path(result_directory)
        self.dataset_size = dataset_size
        
        self._lock = threading.Lock()
        
        # Initialize ordered results array
        self.results = [None] * dataset_size if dataset_size > 0 else []
        self.metadata = {
            "collection_start_time": datetime.now().isoformat(),
            "dataset_size": dataset_size,
            "completed_count": 0,
            "failed_count": 0
        }
        
        # Ensure result directory exists
        self.result_directory.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"ResultsCollector initialized for {dataset_size} items in {result_directory}")

    def add_result(self, 
                   original_index: int, 
                   question: str, 
                   evidence: str,
                   db_id: str,
                   question_id: str,
                   generated_sql: str = "",
                   ground_truth_sql: str = "",
                   execution_status: str = "unknown",
                   evaluation_results: Optional[Dict[str, Any]] = None,
                   processing_time: float = 0.0,
                   error_message: str = ""):
        """
        Add a result to the collector at the specified index.
        
        Args:
            original_index (int): Original index in dataset
            question (str): Natural language question
            evidence (str): Evidence/hint text
            db_id (str): Database ID
            question_id (str): Question ID
            generated_sql (str): Generated SQL query
            ground_truth_sql (str): Ground truth SQL (if available)
            execution_status (str): Status of SQL execution
            evaluation_results (dict): Evaluation metrics
            processing_time (float): Time taken to process this item
            error_message (str): Error message if processing failed
        """
        with self._lock:
            try:
                result_entry = {
                    "original_index": original_index,
                    "db_id": db_id,
                    "question_id": question_id,
                    "question": question,
                    "evidence": evidence,
                    "generated_sql": generated_sql,
                    "ground_truth_sql": ground_truth_sql,
                    "execution_status": execution_status,
                    "processing_time": processing_time,
                    "timestamp": datetime.now().isoformat(),
                    "error_message": error_message
                }
                
                # Add evaluation results if provided
                if evaluation_results:
                    result_entry["evaluation"] = evaluation_results
                
                # Store at correct index to maintain order
                if 0 <= original_index < self.dataset_size:
                    self.results[original_index] = result_entry
                else:
                    # If dataset_size is 0 or index out of bounds, append
                    self.results.append(result_entry)
                
                # Update metadata
                if error_message:
                    self.metadata["failed_count"] += 1
                else:
                    self.metadata["completed_count"] += 1
                
                logger.debug(f"Added result for index {original_index}: {db_id}_{question_id}")
                
            except Exception as e:
                logger.error(f"Error adding result for index {original_index}: {e}")

    def get_completion_status(self) -> Dict[str, Any]:
        """
        Get current completion status.
        
        Returns:
            Dict with completion statistics
        """
        with self._lock:
            completed = sum(1 for r in self.results if r is not None)
            return {
                "total": self.dataset_size,
                "completed": completed,
                "remaining": self.dataset_size - completed if self.dataset_size > 0 else 0,
                "completion_rate": completed / self.dataset_size if self.dataset_size > 0 else 0,
                "failed": self.metadata["failed_count"],
                "success": self.metadata["completed_count"]
            }

    def save_results(self, filename: str = "detailed_results.json") -> str:
        """
        Save collected results to JSON file.
        
        Args:
            filename (str): Output filename
            
        Returns:
            str: Path to saved file
        """
        with self._lock:
            try:
                # Update metadata
                self.metadata["collection_end_time"] = datetime.now().isoformat()
                status = self.get_completion_status()
                self.metadata.update(status)
                
                # Prepare output data
                output_data = {
                    "metadata": self.metadata,
                    "results": [r for r in self.results if r is not None]  # Remove None entries
                }
                
                # Save to file
                output_path = self.result_directory / filename
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Results saved to {output_path} ({len(output_data['results'])} entries)")
                return str(output_path)
                
            except Exception as e:
                logger.error(f"Error saving results: {e}")
                raise

    def save_simple_format(self, filename: str = "results.json") -> str:
        """
        Save results in a simple format with just question and SQL pairs.
        
        Args:
            filename (str): Output filename
            
        Returns:
            str: Path to saved file
        """
        with self._lock:
            try:
                simple_results = []
                
                for result in self.results:
                    if result is not None:
                        simple_entry = {
                            "index": result["original_index"],
                            "db_id": result["db_id"],
                            "question": result["question"],
                            "evidence": result["evidence"],
                            "generated_sql": result["generated_sql"]
                        }
                        
                        # Add ground truth if available
                        if result.get("ground_truth_sql"):
                            simple_entry["ground_truth_sql"] = result["ground_truth_sql"]
                        
                        # Add execution status
                        simple_entry["executable"] = result.get("execution_status") == "success"
                        
                        simple_results.append(simple_entry)
                
                # Sort by original index to maintain order
                simple_results.sort(key=lambda x: x["index"])
                
                # Save to file
                output_path = self.result_directory / filename
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(simple_results, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Simple results saved to {output_path} ({len(simple_results)} entries)")
                return str(output_path)
                
            except Exception as e:
                logger.error(f"Error saving simple results: {e}")
                raise

    def save_csv_format(self, filename: str = "results.csv") -> str:
        """
        Save results in CSV format for easy analysis.
        
        Args:
            filename (str): Output filename
            
        Returns:
            str: Path to saved file
        """
        try:
            import csv
            
            with self._lock:
                output_path = self.result_directory / filename
                
                with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = [
                        'index', 'db_id', 'question_id', 'question', 'evidence', 
                        'generated_sql', 'ground_truth_sql', 'executable', 
                        'processing_time', 'error_message'
                    ]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    # Sort results by index
                    valid_results = [r for r in self.results if r is not None]
                    valid_results.sort(key=lambda x: x["original_index"])
                    
                    for result in valid_results:
                        row = {
                            'index': result["original_index"],
                            'db_id': result["db_id"],
                            'question_id': result["question_id"],
                            'question': result["question"],
                            'evidence': result["evidence"],
                            'generated_sql': result["generated_sql"],
                            'ground_truth_sql': result.get("ground_truth_sql", ""),
                            'executable': result.get("execution_status") == "success",
                            'processing_time': result.get("processing_time", 0),
                            'error_message': result.get("error_message", "")
                        }
                        writer.writerow(row)
                
                logger.info(f"CSV results saved to {output_path}")
                return str(output_path)
                
        except ImportError:
            logger.warning("CSV module not available, skipping CSV export")
            return ""
        except Exception as e:
            logger.error(f"Error saving CSV results: {e}")
            raise

    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics of collected results.
        
        Returns:
            Dict with summary statistics
        """
        with self._lock:
            valid_results = [r for r in self.results if r is not None]
            
            if not valid_results:
                return {"total": 0, "message": "No results collected yet"}
            
            # Calculate statistics
            total_time = sum(r.get("processing_time", 0) for r in valid_results)
            executable_count = sum(1 for r in valid_results if r.get("execution_status") == "success")
            error_count = sum(1 for r in valid_results if r.get("error_message"))
            
            db_counts = {}
            for result in valid_results:
                db_id = result.get("db_id", "unknown")
                db_counts[db_id] = db_counts.get(db_id, 0) + 1
            
            return {
                "total_processed": len(valid_results),
                "executable_queries": executable_count,
                "execution_rate": executable_count / len(valid_results) if valid_results else 0,
                "error_count": error_count,
                "average_processing_time": total_time / len(valid_results) if valid_results else 0,
                "total_processing_time": total_time,
                "databases_processed": db_counts,
                "unique_databases": len(db_counts)
            }

    def __str__(self) -> str:
        """String representation of collector status."""
        status = self.get_completion_status()
        return f"ResultsCollector({status['completed']}/{status['total']} completed, {status['failed']} failed)"

    def __repr__(self) -> str:
        """Detailed representation of collector."""
        return self.__str__()