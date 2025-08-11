"""
Prompt management for OpenSearch-SQL pipeline.
"""
from typing import Dict, Any, List


class PromptManager:
    """
    Manages prompts for different pipeline nodes and operations.
    """
    
    def __init__(self):
        """Initialize the PromptManager with predefined prompts."""
        self.prompts = self._initialize_prompts()
    
    def _initialize_prompts(self) -> Dict[str, str]:
        """
        Initialize all prompts used in the pipeline.
        
        Returns:
            Dict[str, str]: Dictionary of prompt templates.
        """
        prompts = {}
        
        # Few-shot parsing prompt
        prompts["parse_fewshot"] = """
Please analyze the following question and SQL query to extract the key components:

Question: {question}
SQL: {sql}

Please provide the analysis in this format:
#Tables: [list the main tables used]
#SELECT: [describe what is being selected]
#values: [list any specific values or conditions]
#SQL: {sql}
"""

        # Database schema generation prompt
        prompts["db_schema"] = """
You are a database expert. Given the database schema information, please provide a clear and comprehensive description of the database structure, including:

1. All tables and their relationships
2. Column descriptions and data types
3. Foreign key relationships
4. Any important constraints or indexes

Database Information:
{db_info}

Please format your response as a structured description that would help someone understand how to query this database effectively.
"""

        # Column value extraction prompt
        prompts["extract_col_value"] = """
Given the following question about a database, identify and extract specific column values that are mentioned or referenced:

Question: {question}
Database Schema: {db_schema}

Please identify:
1. Specific values mentioned in the question
2. Column names these values likely correspond to
3. Data types of these values

Format your response as:
Column: value_type = "specific_value"
"""

        # Query noun extraction prompt
        prompts["extract_query_noun"] = """
Analyze the following question and extract the key noun phrases and entities that are important for SQL query generation:

Question: {question}
Evidence: {evidence}

Please identify:
1. Main entities (tables/subjects)
2. Attributes (columns/properties) 
3. Relationships mentioned
4. Conditions or constraints
5. Aggregation requirements

Format as a structured list of important elements for SQL generation.
"""

        # Column retrieval prompt
        prompts["column_retrieve"] = """
Given a question and database schema, identify the most relevant columns needed to answer the question:

Question: {question}
Database Schema: {db_schema}
Available Columns: {available_columns}

Please select and rank the most relevant columns for answering this question. Consider:
1. Columns mentioned directly in the question
2. Columns needed for joins
3. Columns for filtering/conditions
4. Columns for the final output

Return as a ranked list with explanations.
"""

        # SQL candidate generation prompt  
        prompts["candidate_generate"] = """
{fewshot}

Given the database schema and question, generate a SQL query to answer the question.

Database Information:
{db_info}

{key_col_des}

Question: {question}
Evidence: {hint}

{q_order}

Please provide a SQL query that accurately answers the question based on the given database schema and evidence.

SQL Query:
"""

        # Alignment correction prompt
        prompts["align_correct"] = """
Please review and correct the following SQL query to ensure it properly answers the question:

Original Question: {question}
Database Schema: {db_schema}
Original SQL: {sql}

Please check for:
1. Syntax correctness
2. Logical correctness 
3. Proper table joins
4. Appropriate filtering conditions
5. Correct aggregations

Provide the corrected SQL query:
"""

        # Voting prompt
        prompts["vote"] = """
Given multiple SQL query candidates for the same question, please select the best one:

Question: {question}
Database Schema: {db_schema}

SQL Candidates:
{candidates}

Please analyze each candidate and select the best one based on:
1. Correctness
2. Efficiency
3. Clarity
4. Completeness

Selected SQL:
"""

        # Evaluation prompt
        prompts["evaluation"] = """
Please evaluate the correctness of the following SQL query for the given question:

Question: {question}
Database Schema: {db_schema}
SQL Query: {sql}
Expected Result: {expected}
Actual Result: {actual}

Please provide an assessment of:
1. Correctness (1 if correct, 0 if incorrect)
2. Error type (if any)
3. Explanation

Format:
Correctness: [1/0]
Error: [error description or "none"]
Explanation: [detailed explanation]
"""

        return prompts
    
    def get_prompt(self, prompt_name: str) -> str:
        """
        Get a prompt template by name.
        
        Args:
            prompt_name (str): Name of the prompt.
            
        Returns:
            str: Prompt template.
            
        Raises:
            KeyError: If prompt name not found.
        """
        if prompt_name not in self.prompts:
            available_prompts = list(self.prompts.keys())
            raise KeyError(f"Prompt '{prompt_name}' not found. Available prompts: {available_prompts}")
        
        return self.prompts[prompt_name]
    
    def add_prompt(self, prompt_name: str, prompt_template: str):
        """
        Add a new prompt template.
        
        Args:
            prompt_name (str): Name for the new prompt.
            prompt_template (str): The prompt template string.
        """
        self.prompts[prompt_name] = prompt_template
    
    def update_prompt(self, prompt_name: str, prompt_template: str):
        """
        Update an existing prompt template.
        
        Args:
            prompt_name (str): Name of the prompt to update.
            prompt_template (str): The new prompt template string.
        """
        if prompt_name not in self.prompts:
            raise KeyError(f"Prompt '{prompt_name}' not found")
        
        self.prompts[prompt_name] = prompt_template
    
    def list_prompts(self) -> List[str]:
        """
        List all available prompt names.
        
        Returns:
            List[str]: List of prompt names.
        """
        return list(self.prompts.keys())
    
    def format_prompt(self, prompt_name: str, **kwargs) -> str:
        """
        Format a prompt template with provided arguments.
        
        Args:
            prompt_name (str): Name of the prompt.
            **kwargs: Arguments to format the prompt.
            
        Returns:
            str: Formatted prompt.
        """
        template = self.get_prompt(prompt_name)
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise KeyError(f"Missing required argument for prompt '{prompt_name}': {e}")


# Legacy prompt classes for compatibility
class DBCheckPrompts:
    """Legacy prompt class for db_check functionality."""
    
    def __init__(self):
        self.prompt_manager = PromptManager()
    
    @property
    def new_prompt(self):
        return self.prompt_manager.get_prompt("candidate_generate")
    
    @property
    def extract_prompt(self):
        return self.prompt_manager.get_prompt("extract_col_value")
    
    @property
    def noun_prompt(self):
        return self.prompt_manager.get_prompt("extract_query_noun")
    
    @property
    def correct_prompt(self):
        return self.prompt_manager.get_prompt("align_correct")
    
    @property
    def vote_prompt(self):
        return self.prompt_manager.get_prompt("vote")


def db_check_prompts():
    """Factory function for DBCheckPrompts."""
    return DBCheckPrompts()


# Additional specialized prompts that might be needed
SPECIALIZED_PROMPTS = {
    "schema_linking": """
Given the question and database schema, identify which tables and columns are most relevant:

Question: {question}
Schema: {schema}

Provide a ranked list of relevant tables and columns with confidence scores.
""",

    "value_linking": """
Identify specific values mentioned in the question and link them to appropriate database columns:

Question: {question}
Schema: {schema}
Sample Data: {sample_data}

List all specific values and their likely column mappings.
""",

    "join_reasoning": """
Determine what tables need to be joined to answer the question:

Question: {question}
Schema: {schema}
Required Tables: {tables}

Explain the join logic and provide the appropriate JOIN clauses.
""",

    "aggregation_detection": """
Identify if the question requires any aggregation functions:

Question: {question}

Specify:
1. Type of aggregation needed (COUNT, SUM, AVG, MAX, MIN, etc.)
2. Columns to aggregate
3. Grouping requirements
4. Having conditions if any
""",

    "condition_extraction": """
Extract all filtering conditions from the question:

Question: {question}
Evidence: {evidence}

List all WHERE conditions, comparison operators, and logical connectors needed.
"""
}


def get_specialized_prompt(prompt_name: str) -> str:
    """
    Get a specialized prompt template.
    
    Args:
        prompt_name (str): Name of the specialized prompt.
        
    Returns:
        str: Prompt template.
    """
    if prompt_name not in SPECIALIZED_PROMPTS:
        available = list(SPECIALIZED_PROMPTS.keys())
        raise KeyError(f"Specialized prompt '{prompt_name}' not found. Available: {available}")
    
    return SPECIALIZED_PROMPTS[prompt_name]