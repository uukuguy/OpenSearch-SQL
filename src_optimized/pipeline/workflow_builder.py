"""
Standalone WorkflowBuilder implementation for OpenSearch-SQL pipeline.
"""
import logging
from typing import Dict, TypedDict, Callable
from langgraph.graph import END, StateGraph

# Import pipeline nodes
from .nodes.generate_db_schema import generate_db_schema
from .nodes.extract_col_value import extract_col_value
from .nodes.extract_query_noun import extract_query_noun
from .nodes.column_retrieve_and_other_info import column_retrieve_and_other_info
from .nodes.candidate_generate import candidate_generate
from .nodes.align_correct import align_correct
from .nodes.vote import vote
from .nodes.evaluation import evaluation


### Graph State ###
class GraphState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        keys: A dictionary where each key is a string.
    """
    keys: Dict[str, any]


class WorkflowBuilder:
    """
    Builds and manages the LangGraph workflow for the OpenSearch-SQL pipeline.
    """
    
    def __init__(self):
        """Initialize the WorkflowBuilder."""
        self.workflow = StateGraph(GraphState)
        logging.info("Initialized WorkflowBuilder")

    def build(self, pipeline_nodes: str) -> None:
        """
        Builds the workflow based on the provided pipeline nodes.

        Args:
            pipeline_nodes (str): A string of pipeline node names separated by '+'.
        """
        nodes = pipeline_nodes.split("+")
        logging.info(f"Building workflow with nodes: {nodes}")
        self._add_nodes(nodes)
        self.workflow.set_entry_point(nodes[0])
        self._add_edges([(nodes[i], nodes[i+1]) for i in range(len(nodes) - 1)])
        self._add_edges([(nodes[-1], END)])
        logging.info("Workflow built successfully")

    def _add_nodes(self, nodes: list) -> None:
        """
        Adds nodes to the workflow.

        Args:
            nodes (list): A list of node names.
        """
        # Mapping of node names to their corresponding functions
        node_functions = {
            "generate_db_schema": generate_db_schema,
            "extract_col_value": extract_col_value,
            "extract_query_noun": extract_query_noun,
            "column_retrieve_and_other_info": column_retrieve_and_other_info,
            "candidate_generate": candidate_generate,
            "align_correct": align_correct,
            "vote": vote,
            "evaluation": evaluation
        }
        
        for node_name in nodes:
            if node_name in node_functions:
                self.workflow.add_node(node_name, node_functions[node_name])
                logging.info(f"Added node: {node_name}")
            else:
                logging.error(f"Node function '{node_name}' not found in node_functions mapping")
                available_nodes = list(node_functions.keys())
                logging.error(f"Available nodes: {available_nodes}")
                raise ValueError(f"Unknown node: {node_name}. Available nodes: {available_nodes}")

    def _add_edges(self, edges: list) -> None:
        """
        Adds edges between nodes in the workflow.

        Args:
            edges (list): A list of tuples representing the edges.
        """
        for src, dst in edges:
            self.workflow.add_edge(src, dst)
            logging.info(f"Added edge from {src} to {dst}")

    def compile(self) -> Callable:
        """
        Compiles the workflow into an executable application.
        
        Returns:
            Callable: The compiled workflow application.
        """
        try:
            app = self.workflow.compile()
            logging.info("Workflow compiled successfully")
            return app
        except Exception as e:
            logging.error(f"Error compiling workflow: {e}")
            raise

    def get_graph_visualization(self) -> str:
        """
        Gets a text representation of the workflow graph.
        
        Returns:
            str: Text representation of the graph.
        """
        try:
            # Simple text representation of the graph structure
            nodes = list(self.workflow.nodes.keys()) if hasattr(self.workflow, 'nodes') else []
            edges = []
            
            # Try to extract edges information
            if hasattr(self.workflow, 'edges'):
                edges = [(src, dst) for src, dst in self.workflow.edges.items()]
            
            visualization = "Workflow Graph:\n"
            visualization += f"Nodes: {nodes}\n"
            visualization += f"Edges: {edges}\n"
            
            return visualization
        except Exception as e:
            logging.error(f"Error generating graph visualization: {e}")
            return f"Error generating visualization: {e}"


def build_pipeline(pipeline_nodes: str) -> Callable:
    """
    Builds and compiles the pipeline based on the provided nodes.

    Args:
        pipeline_nodes (str): A string of pipeline node names separated by '+'.

    Returns:
        Callable: The compiled workflow application.
    """
    try:
        builder = WorkflowBuilder()
        builder.build(pipeline_nodes)
        app = builder.compile()
        logging.info("Pipeline built and compiled successfully")
        return app
    except Exception as e:
        logging.error(f"Error building pipeline: {e}")
        raise

def validate_pipeline_nodes(pipeline_nodes: str) -> bool:
    """
    Validates that all specified pipeline nodes are available.
    
    Args:
        pipeline_nodes (str): A string of pipeline node names separated by '+'.
        
    Returns:
        bool: True if all nodes are valid, False otherwise.
    """
    available_nodes = {
        "generate_db_schema",
        "extract_col_value", 
        "extract_query_noun",
        "column_retrieve_and_other_info",
        "candidate_generate",
        "align_correct",
        "vote",
        "evaluation"
    }
    
    nodes = pipeline_nodes.split("+")
    invalid_nodes = [node for node in nodes if node not in available_nodes]
    
    if invalid_nodes:
        logging.error(f"Invalid pipeline nodes: {invalid_nodes}")
        logging.error(f"Available nodes: {sorted(available_nodes)}")
        return False
    
    return True