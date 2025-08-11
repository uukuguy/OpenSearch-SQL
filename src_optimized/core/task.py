"""
Standalone Task implementation for OpenSearch-SQL pipeline.
"""
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List


@dataclass
class Task:
    """
    Represents a task with question and database details.

    Attributes:
        question_id (int): The unique identifier for the question.
        db_id (str): The database identifier.
        question (str): The question text.
        evidence (str): Supporting evidence for the question.
        SQL (Optional[str]): The SQL query associated with the task, if any.
        difficulty (Optional[str]): The difficulty level of the task, if specified.
        raw_question (str): The original question text.
        question_toks (List[str]): Tokenized question.
        query (str): Query string.
    """
    question_id: int = field(init=False)
    db_id: str = field(init=False)
    question: str = field(init=False)
    evidence: str = field(init=False)
    SQL: Optional[str] = field(init=False, default=None)
    difficulty: Optional[str] = field(init=False, default=None)
    raw_question: str = field(init=False)
    question_toks: List[str] = field(default_factory=list)
    query: str = field(init=False)

    def __init__(self, task_data: Dict[str, Any]):
        """
        Initializes a Task instance using data from a dictionary.

        Args:
            task_data (Dict[str, Any]): A dictionary containing task data.
        """
        self.question_id = task_data["question_id"]
        self.db_id = task_data["db_id"]
        
        self.SQL = task_data.get("SQL")
        self.difficulty = task_data.get("difficulty")
        
        self.raw_question = task_data["question"]
        self.evidence = task_data.get("evidence", "")
        
        # Combine question and evidence
        self.question = (self.raw_question + " " + self.evidence).strip()
        
        # Handle empty evidence
        if self.evidence == "":
            self.evidence = "None"
            
        self.question_toks = task_data.get("question_toks", [])
        self.query = task_data.get("query", "")

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary representation."""
        return {
            "question_id": self.question_id,
            "db_id": self.db_id,
            "question": self.question,
            "evidence": self.evidence,
            "SQL": self.SQL,
            "difficulty": self.difficulty,
            "raw_question": self.raw_question,
            "question_toks": self.question_toks,
            "query": self.query
        }

    def __str__(self) -> str:
        """String representation of the task."""
        return f"Task({self.question_id}, {self.db_id}, '{self.question[:50]}...')"

    def __repr__(self) -> str:
        """Detailed representation of the task."""
        return self.__str__()