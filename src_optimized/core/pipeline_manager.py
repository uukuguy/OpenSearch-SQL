"""
Standalone PipelineManager implementation for OpenSearch-SQL pipeline.
"""
import inspect
from threading import Lock
from typing import Any, Dict, Tuple, List


class PipelineManager:
    """
    Singleton class to manage pipeline configuration and node parameters.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls, pipeline_setup: Dict[str, Any] = None):
        """
        Ensures a singleton instance of PipelineManager.

        Args:
            pipeline_setup (Dict[str, Any], optional): The setup dictionary for the pipeline. Required for initialization.

        Returns:
            PipelineManager: The singleton instance of the class.

        Raises:
            ValueError: If the pipeline_setup is not provided during the first initialization.
        """
        if pipeline_setup is not None:
            with cls._lock:
                cls._instance = super(PipelineManager, cls).__new__(cls)
                cls._instance.pipeline_setup = pipeline_setup
                cls._instance._init(pipeline_setup)
        elif cls._instance is None:
            raise ValueError("pipeline_setup dictionary must be provided for initialization")
        return cls._instance

    def _init(self, pipeline_setup: Dict[str, Any]):
        """
        Custom initialization logic using the pipeline_setup dictionary.

        Args:
            pipeline_setup (Dict[str, Any]): The setup dictionary for the pipeline.
        """
        self.generate_db_schema = pipeline_setup.get("generate_db_schema", {})
        self.extract_col_value = pipeline_setup.get("extract_col_value", {})
        self.extract_query_noun = pipeline_setup.get("extract_query_noun", {})
        self.column_retrieve_and_other_info = pipeline_setup.get("column_retrieve_and_other_info", {})
        self.candidate_generate = pipeline_setup.get("candidate_generate", {})
        self.align_correct = pipeline_setup.get("align_correct", {})
        self.vote = pipeline_setup.get("vote", {})
        self.evaluation = pipeline_setup.get("evaluation", {})

    def get_model_para(self, **kwargs: Any) -> Tuple[Dict[str, Any], str]:
        """
        Retrieves the model parameters for the current node based on the pipeline setup.

        Args:
            **kwargs: Additional keyword arguments for the prompt (currently unused).

        Returns:
            Tuple[Dict[str, Any], str]: The node configuration and node name.

        Raises:
            ValueError: If the engine is not specified for the node.
        """
        frame = inspect.currentframe()
        caller_frame = frame.f_back
        node_name = caller_frame.f_code.co_name
        
        node_setup = self.pipeline_setup.get(node_name, {})
        
        # Apply any kwargs updates to node_setup if needed
        if kwargs:
            node_setup = {**node_setup, **kwargs}
                
        return node_setup, node_name

    def get_node_config(self, node_name: str) -> Dict[str, Any]:
        """
        Gets configuration for a specific node.
        
        Args:
            node_name (str): Name of the node.
            
        Returns:
            Dict[str, Any]: Configuration dictionary for the node.
        """
        return self.pipeline_setup.get(node_name, {})

    def set_node_config(self, node_name: str, config: Dict[str, Any]):
        """
        Sets configuration for a specific node.
        
        Args:
            node_name (str): Name of the node.
            config (Dict[str, Any]): Configuration dictionary for the node.
        """
        self.pipeline_setup[node_name] = config

    def update_node_config(self, node_name: str, updates: Dict[str, Any]):
        """
        Updates configuration for a specific node.
        
        Args:
            node_name (str): Name of the node.
            updates (Dict[str, Any]): Updates to apply to the node configuration.
        """
        if node_name not in self.pipeline_setup:
            self.pipeline_setup[node_name] = {}
        self.pipeline_setup[node_name].update(updates)

    def get_all_nodes(self) -> List[str]:
        """
        Gets all configured node names.
        
        Returns:
            List[str]: List of all node names.
        """
        return list(self.pipeline_setup.keys())

    def reset(self):
        """
        Resets the singleton instance.
        """
        with self._lock:
            PipelineManager._instance = None

    def __str__(self) -> str:
        """String representation of the PipelineManager."""
        return f"PipelineManager(nodes={len(self.pipeline_setup)})"

    def __repr__(self) -> str:
        """Detailed representation of the PipelineManager."""
        return f"PipelineManager(pipeline_setup={self.pipeline_setup})"