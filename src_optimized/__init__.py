"""
OpenSearch-SQL Pipeline - Standalone Implementation

A complete, standalone implementation of the OpenSearch-SQL Text-to-SQL pipeline.
"""

__version__ = "1.0.0"
__author__ = "OpenSearch-SQL Team"
__description__ = "Standalone OpenSearch-SQL Text-to-SQL Pipeline"

# Core imports
from .core import (
    Task,
    DatabaseManager,
    Logger,
    PipelineManager,
    StatisticsManager
)

# Pipeline imports
from .pipeline import WorkflowBuilder, build_pipeline

# Runner imports
from .runner import RunManager

# Utility imports
from .utils import (
    ConfigHelper,
    DataHelper,
    PerformanceHelper,
    load_config,
    load_bird_dataset
)

__all__ = [
    # Core components
    "Task",
    "DatabaseManager", 
    "Logger",
    "PipelineManager",
    "StatisticsManager",
    
    # Pipeline components
    "WorkflowBuilder",
    "build_pipeline",
    
    # Runner components
    "RunManager",
    
    # Utilities
    "ConfigHelper",
    "DataHelper",
    "PerformanceHelper",
    "load_config",
    "load_bird_dataset"
]