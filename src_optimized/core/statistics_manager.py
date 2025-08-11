"""
Standalone StatisticsManager implementation for OpenSearch-SQL pipeline.
"""
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Union, Tuple


@dataclass
class Statistics:
    """
    Dataclass to hold statistics data for pipeline execution.
    """
    corrects: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)
    incorrects: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)
    errors: Dict[str, List[Union[Tuple[str, str], Tuple[str, str, str]]]] = field(default_factory=dict)
    total: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Dict[str, Union[Dict[str, int], List[Tuple[str, str]]]]]:
        """
        Converts the statistics data to a dictionary format.

        Returns:
            Dict[str, Dict[str, Union[Dict[str, int], List[Tuple[str, str]]]]]: The statistics data as a dictionary.
        """
        return {
            "counts": {
                key: {
                    "correct": len(self.corrects.get(key, [])),
                    "incorrect": len(self.incorrects.get(key, [])),
                    "error": len(self.errors.get(key, [])),
                    "total": self.total.get(key, 0)
                }
                for key in self.total
            },
            "ids": {
                key: {
                    "correct": sorted(self.corrects.get(key, [])),
                    "incorrect": sorted(self.incorrects.get(key, [])),
                    "error": sorted(self.errors.get(key, []))
                }
                for key in self.total
            }
        }

    def get_accuracy(self, evaluation_for: str = None) -> Dict[str, float]:
        """
        Calculates accuracy for all or specific evaluation contexts.
        
        Args:
            evaluation_for (str, optional): Specific evaluation context.
            
        Returns:
            Dict[str, float]: Accuracy statistics.
        """
        accuracies = {}
        
        if evaluation_for:
            keys = [evaluation_for] if evaluation_for in self.total else []
        else:
            keys = list(self.total.keys())
        
        for key in keys:
            total = self.total.get(key, 0)
            correct = len(self.corrects.get(key, []))
            accuracies[key] = correct / total if total > 0 else 0.0
        
        return accuracies

    def get_summary(self) -> Dict[str, Any]:
        """
        Gets a summary of all statistics.
        
        Returns:
            Dict[str, Any]: Summary statistics.
        """
        summary = {
            "total_evaluations": sum(self.total.values()),
            "total_correct": sum(len(corrects) for corrects in self.corrects.values()),
            "total_incorrect": sum(len(incorrects) for incorrects in self.incorrects.values()),
            "total_errors": sum(len(errors) for errors in self.errors.values()),
            "accuracies": self.get_accuracy()
        }
        
        if summary["total_evaluations"] > 0:
            summary["overall_accuracy"] = summary["total_correct"] / summary["total_evaluations"]
        else:
            summary["overall_accuracy"] = 0.0
            
        return summary


class StatisticsManager:
    """
    Manages execution statistics for the pipeline.
    """
    
    def __init__(self, result_directory: str):
        """
        Initializes the StatisticsManager.

        Args:
            result_directory (str): The directory to store results.
        """
        self.result_directory = Path(result_directory)
        self.statistics = Statistics()

        # Ensure the statistics file exists
        self.statistics_file_path = self.result_directory / "-statistics.json"
        if not self.statistics_file_path.exists():
            self.statistics_file_path.touch()
            self.dump_statistics_to_file()

    def update_stats(self, db_id: str, question_id: str, evaluation_for: str, result: Dict[str, Any]):
        """
        Updates the statistics based on the evaluation result.

        Args:
            db_id (str): The database ID.
            question_id (str): The question ID.
            evaluation_for (str): The evaluation context.
            result (Dict[str, Any]): The evaluation result.
        """
        exec_res = result.get("exec_res", 0)
        exec_err = result.get("exec_err", "unknown error")

        self.statistics.total[evaluation_for] = self.statistics.total.get(evaluation_for, 0) + 1

        if exec_res == 1:
            if evaluation_for not in self.statistics.corrects:
                self.statistics.corrects[evaluation_for] = []
            self.statistics.corrects[evaluation_for].append((db_id, question_id))
        else:
            if exec_err == "incorrect answer":
                if evaluation_for not in self.statistics.incorrects:
                    self.statistics.incorrects[evaluation_for] = []
                self.statistics.incorrects[evaluation_for].append((db_id, question_id))
            else:
                if evaluation_for not in self.statistics.errors:
                    self.statistics.errors[evaluation_for] = []
                self.statistics.errors[evaluation_for].append((db_id, question_id, exec_err))

    def dump_statistics_to_file(self):
        """
        Dumps the current statistics to a JSON file.
        """
        stats_data = self.statistics.to_dict()
        # Add summary information
        stats_data["summary"] = self.statistics.get_summary()
        
        with self.statistics_file_path.open('w', encoding='utf-8') as f:
            json.dump(stats_data, f, indent=4, ensure_ascii=False)

    def get_current_stats(self) -> Dict[str, Any]:
        """
        Gets current statistics without writing to file.
        
        Returns:
            Dict[str, Any]: Current statistics.
        """
        return self.statistics.to_dict()

    def reset_stats(self):
        """
        Resets all statistics.
        """
        self.statistics = Statistics()
        self.dump_statistics_to_file()

    def print_summary(self):
        """
        Prints a summary of current statistics.
        """
        summary = self.statistics.get_summary()
        print("\n" + "="*50)
        print("EXECUTION STATISTICS SUMMARY")
        print("="*50)
        print(f"Total Evaluations: {summary['total_evaluations']}")
        print(f"Total Correct: {summary['total_correct']}")
        print(f"Total Incorrect: {summary['total_incorrect']}")
        print(f"Total Errors: {summary['total_errors']}")
        print(f"Overall Accuracy: {summary['overall_accuracy']:.2%}")
        
        if summary['accuracies']:
            print("\nAccuracy by Evaluation Type:")
            for eval_type, accuracy in summary['accuracies'].items():
                print(f"  {eval_type}: {accuracy:.2%}")
        print("="*50)

    def __str__(self) -> str:
        """String representation of the StatisticsManager."""
        summary = self.statistics.get_summary()
        return f"StatisticsManager(total={summary['total_evaluations']}, accuracy={summary['overall_accuracy']:.2%})"

    def __repr__(self) -> str:
        """Detailed representation of the StatisticsManager."""
        return self.__str__()