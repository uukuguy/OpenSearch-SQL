"""
Example usage of the standalone OpenSearch-SQL pipeline.
"""
import json
import os
import logging
from datetime import datetime

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_mock_args():
    """Create mock arguments for testing."""
    class MockArgs:
        def __init__(self):
            self.data_mode = "dev"
            self.db_root_path = "./Bird"
            self.pipeline_nodes = "candidate_generate+vote+evaluation"
            self.pipeline_setup = json.dumps({
                "candidate_generate": {
                    "engine": "mock",
                    "temperature": 0.0,
                    "n": 1,
                    "single": "true"
                },
                "vote": {
                    "voting_method": "execution_based"
                },
                "evaluation": {
                    "engine": "mock"
                }
            })
            self.start = 0
            self.end = 2
            self.log_level = "info"
            self.use_checkpoint = False
            self.checkpoint_nodes = None
            self.checkpoint_dir = None
            self.use_multiprocessing = False
            self.run_start_time = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    return MockArgs()


def example_basic_usage():
    """Example of basic pipeline usage."""
    print("="*60)
    print("EXAMPLE 1: Basic Pipeline Usage")
    print("="*60)
    
    from .runner import RunManager
    from .utils import load_bird_dataset, validate_dataset
    
    try:
        # Create mock dataset for testing
        mock_dataset = [
            {
                "question_id": 0,
                "db_id": "california_schools",
                "question": "How many schools are there?",
                "evidence": "Count the total number of schools in the database."
            },
            {
                "question_id": 1,
                "db_id": "california_schools", 
                "question": "What is the name of the school with the highest SAT score?",
                "evidence": "Find the school with the maximum SAT score."
            }
        ]
        
        print(f"Using mock dataset with {len(mock_dataset)} items")
        
        # Create arguments
        args = create_mock_args()
        
        # Run the pipeline
        with RunManager(args) as manager:
            print("Initializing tasks...")
            manager.initialize_tasks(args.start, args.end, mock_dataset)
            
            print("Running tasks...")
            manager.run_tasks()
            
            # Get execution summary
            summary = manager.get_execution_summary()
            
            print("\nExecution Summary:")
            print(f"  Total tasks: {summary['total_tasks']}")
            print(f"  Processed tasks: {summary['processed_tasks']}")
            print(f"  Completion rate: {summary['completion_rate']:.2%}")
            print(f"  Results saved to: {summary['result_directory']}")
            
    except Exception as e:
        print(f"Error in basic usage example: {e}")
        logging.error(f"Basic usage error: {e}", exc_info=True)


def example_configuration_management():
    """Example of configuration management."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Configuration Management")
    print("="*60)
    
    from .utils import ConfigHelper
    
    try:
        # Create a default configuration
        config = ConfigHelper.create_default_config()
        print("Default configuration created:")
        print(json.dumps(config, indent=2))
        
        # Modify configuration
        config["candidate_generate"]["engine"] = "gpt-4o"
        config["candidate_generate"]["n"] = 5
        
        # Save configuration
        config_file = "example_config.json"
        ConfigHelper.save_config(config, config_file)
        print(f"\nConfiguration saved to: {config_file}")
        
        # Load and validate configuration
        loaded_config = ConfigHelper.load_config(config_file)
        print("Configuration loaded successfully")
        
        # Validate each node
        for node_name, node_config in loaded_config.items():
            if not node_name.startswith("_"):  # Skip metadata keys
                is_valid = ConfigHelper.validate_node_config(node_name, node_config)
                print(f"Node {node_name}: {'✓ Valid' if is_valid else '✗ Invalid'}")
        
        # Clean up
        if os.path.exists(config_file):
            os.remove(config_file)
            
    except Exception as e:
        print(f"Error in configuration example: {e}")
        logging.error(f"Configuration error: {e}", exc_info=True)


def example_data_processing():
    """Example of data processing utilities."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Data Processing Utilities")
    print("="*60)
    
    from .utils import DataHelper
    
    try:
        # Create sample dataset
        sample_dataset = [
            {
                "question_id": 0,
                "db_id": "test_db",
                "question": "Sample question 1?",
                "evidence": "Sample evidence 1",
                "SQL": "SELECT * FROM table1;",
                "difficulty": "easy"
            },
            {
                "question_id": 1,
                "db_id": "test_db",
                "question": "Sample question 2?",
                "evidence": "Sample evidence 2",
                "difficulty": "hard"
            }
        ]
        
        # Validate dataset structure
        is_valid, issues = DataHelper.validate_dataset_structure(sample_dataset)
        print(f"Dataset validation: {'✓ Valid' if is_valid else '✗ Invalid'}")
        if issues:
            print("Issues found:")
            for issue in issues:
                print(f"  - {issue}")
        
        # Get dataset statistics
        stats = DataHelper.get_dataset_statistics(sample_dataset)
        print("\nDataset Statistics:")
        print(json.dumps(stats, indent=2))
        
        # Filter dataset
        filtered = DataHelper.filter_dataset(
            sample_dataset, 
            difficulties=["easy"],
            min_question_length=10
        )
        print(f"\nFiltered dataset: {len(filtered)} items")
        
    except Exception as e:
        print(f"Error in data processing example: {e}")
        logging.error(f"Data processing error: {e}", exc_info=True)


def example_performance_monitoring():
    """Example of performance monitoring."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Performance Monitoring")
    print("="*60)
    
    from .utils import PerformanceHelper, profile_function
    import time
    
    try:
        # Example function with profiling
        @profile_function(track_memory=True, track_cpu=True)
        def example_computation(n: int = 100000):
            """Example computation function."""
            return sum(i * i for i in range(n))
        
        # Test performance monitoring
        with PerformanceHelper.performance_context("Example Computation"):
            result = example_computation()
            print(f"Computation result: {result}")
        
        # Test multiple operations
        print("\nTesting multiple operations...")
        for i in range(3):
            with PerformanceHelper.performance_context(f"Operation {i+1}"):
                time.sleep(0.1)  # Simulate work
                result = example_computation(50000)
        
    except Exception as e:
        print(f"Error in performance monitoring example: {e}")
        logging.error(f"Performance monitoring error: {e}", exc_info=True)


def run_all_examples():
    """Run all examples."""
    print("OpenSearch-SQL Standalone Implementation Examples")
    print("=" * 60)
    
    # Check if BIRD dataset is available
    bird_path = "./Bird"
    if not os.path.exists(bird_path):
        print(f"⚠️  BIRD dataset not found at {bird_path}")
        print("   Using mock data for examples")
    
    try:
        example_basic_usage()
        example_configuration_management()
        example_data_processing()
        example_performance_monitoring()
        
        print("\n" + "="*60)
        print("✅ All examples completed successfully!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Examples failed: {e}")
        logging.error(f"Examples failed: {e}", exc_info=True)


if __name__ == "__main__":
    run_all_examples()