"""
Main entry point for the standalone OpenSearch-SQL pipeline.
"""
import argparse
import json
from ..utils.loguru_config import get_logger
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .runner import RunManager


logger = get_logger(__name__)
def load_dataset(data_path: str) -> List[Dict[str, Any]]:
    """
    Loads the dataset from the specified path.

    Args:
        data_path (str): Path to the data file.

    Returns:
        List[Dict[str, Any]]: The loaded dataset.
    """
    try:
        with open(data_path, 'r', encoding='utf-8') as file:
            dataset = json.load(file)
        return dataset
    except Exception as e:
        logger.error(f"Error loading dataset from {data_path}: {e}")
        raise


def validate_args(args) -> bool:
    """
    Validate command line arguments.
    
    Args:
        args: Parsed arguments.
        
    Returns:
        bool: True if valid, False otherwise.
    """
    errors = []
    
    # Check required paths exist
    if not Path(args.db_root_path).exists():
        errors.append(f"Database root path does not exist: {args.db_root_path}")
    
    # Validate pipeline setup JSON
    try:
        pipeline_setup = json.loads(args.pipeline_setup)
        if not isinstance(pipeline_setup, dict):
            errors.append("Pipeline setup must be a JSON object")
    except json.JSONDecodeError as e:
        errors.append(f"Invalid pipeline setup JSON: {e}")
    
    # Validate range parameters
    if args.start < 0:
        errors.append("Start index must be non-negative")
    
    if args.end > 0 and args.end <= args.start:
        errors.append("End index must be greater than start index")
    
    # Validate checkpoint configuration
    if args.use_checkpoint:
        if not args.checkpoint_nodes:
            errors.append("Checkpoint nodes must be specified when using checkpoints")
        if not args.checkpoint_dir:
            errors.append("Checkpoint directory must be specified when using checkpoints")
        elif not Path(args.checkpoint_dir).exists():
            errors.append(f"Checkpoint directory does not exist: {args.checkpoint_dir}")
    
    if errors:
        for error in errors:
            logger.error(error)
        return False
    
    return True


def setup_logging(log_level: str):
    """
    Setup logging configuration using loguru.
    
    Args:
        log_level (str): Logging level.
    """
    from .utils.loguru_config import LoguruConfig
    LoguruConfig.setup(log_level=log_level)


def get_dataset_path(args) -> str:
    """
    Get the dataset path based on arguments.
    
    Args:
        args: Parsed arguments.
        
    Returns:
        str: Dataset file path.
    """
    # Use the same logic as the original implementation
    db_json = f"{args.db_root_path}/dev_20240627/dev.json"
    
    if not Path(db_json).exists():
        # Fallback to other possible paths
        alternative_paths = [
            f"{args.db_root_path}/data_preprocess/{args.data_mode}.json",
            f"{args.db_root_path}/{args.data_mode}/{args.data_mode}.json",
            f"{args.db_root_path}/{args.data_mode}.json"
        ]
        
        for alt_path in alternative_paths:
            if Path(alt_path).exists():
                db_json = alt_path
                break
        else:
            raise FileNotFoundError(f"Dataset file not found. Tried: {db_json}, {alternative_paths}")
    
    return db_json


def print_banner():
    """Print the application banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                        OpenSearch-SQL Pipeline                        ║
    ║                         Standalone Version                            ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def main(args):
    """
    Main function to run the pipeline with the specified configuration.
    
    Args:
        args: Parsed command line arguments.
    """
    print_banner()
    
    # Setup logging
    setup_logging(args.log_level)
    logger.info("Starting OpenSearch-SQL pipeline execution")
    
    # Validate arguments
    if not validate_args(args):
        logger.error("Argument validation failed")
        sys.exit(1)
    
    try:
        # Load dataset
        dataset_path = get_dataset_path(args)
        logger.info(f"Loading dataset from: {dataset_path}")
        dataset = load_dataset(dataset_path)
        logger.info(f"Loaded {len(dataset)} items from dataset")
        
        # Create and run the pipeline
        with RunManager(args) as run_manager:
            logger.info("Initializing tasks...")
            run_manager.initialize_tasks(args.start, args.end, dataset)
            
            logger.info("Running tasks...")
            run_manager.run_tasks()
            
            # Print execution summary
            summary = run_manager.get_execution_summary()
            logger.info("Execution Summary:")
            logger.info(f"  Total tasks: {summary['total_tasks']}")
            logger.info(f"  Processed tasks: {summary['processed_tasks']}")
            logger.info(f"  Completion rate: {summary['completion_rate']:.2%}")
            logger.info(f"  Results saved to: {summary['result_directory']}")
    
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        raise


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.
    
    Returns:
        argparse.ArgumentParser: Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="OpenSearch-SQL Pipeline - Standalone Implementation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with basic configuration
  python -m src_optimized.main --data_mode dev --db_root_path ./Bird --pipeline_nodes "generate_db_schema+extract_col_value+candidate_generate+vote+evaluation" --pipeline_setup '{"candidate_generate": {"engine": "gpt-4o", "temperature": 0.0, "n": 1}}'
  
  # Run with checkpoints
  python -m src_optimized.main --data_mode dev --db_root_path ./Bird --pipeline_nodes "candidate_generate+vote+evaluation" --pipeline_setup '{"candidate_generate": {"engine": "gpt-4o"}}' --use_checkpoint --checkpoint_nodes "generate_db_schema+extract_col_value" --checkpoint_dir ./checkpoints
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--data_mode', 
        type=str, 
        required=True,
        help="Mode of the data to be processed (e.g., 'dev', 'train')"
    )
    
    parser.add_argument(
        '--db_root_path', 
        type=str, 
        required=True,
        help="Path to the database root directory containing the Bird dataset"
    )
    
    parser.add_argument(
        '--pipeline_nodes', 
        type=str, 
        required=True,
        help="Pipeline nodes configuration separated by '+' (e.g., 'generate_db_schema+extract_col_value+candidate_generate+vote+evaluation')"
    )
    
    parser.add_argument(
        '--pipeline_setup', 
        type=str, 
        required=True,
        help="Pipeline setup configuration in JSON format"
    )
    
    # Optional arguments
    parser.add_argument(
        '--use_checkpoint', 
        action='store_true',
        help="Enable checkpoint loading"
    )
    
    parser.add_argument(
        '--checkpoint_nodes', 
        type=str,
        help="Checkpoint nodes configuration separated by '+'"
    )
    
    parser.add_argument(
        '--checkpoint_dir', 
        type=str,
        help="Directory containing checkpoint files"
    )
    
    parser.add_argument(
        '--log_level', 
        type=str, 
        default='info',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        help="Logging level (default: info)"
    )
    
    parser.add_argument(
        '--start', 
        type=int, 
        default=0,
        help="Starting index for processing tasks (default: 0)"
    )
    
    parser.add_argument(
        '--end', 
        type=int, 
        default=-1,
        help="Ending index for processing tasks (default: -1 for all tasks)"
    )
    
    parser.add_argument(
        '--use_multiprocessing',
        action='store_true',
        help="Enable multiprocessing for task execution (experimental)"
    )
    
    return parser


if __name__ == '__main__':
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Set run start time
    args.run_start_time = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    # Handle end index
    if args.end <= 0:
        args.end = float('inf')  # Process all tasks
    
    try:
        main(args)
        print("\n✅ Pipeline execution completed successfully!")
    except KeyboardInterrupt:
        print("\n❌ Pipeline execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Pipeline execution failed: {e}")
        sys.exit(1)