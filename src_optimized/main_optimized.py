#!/usr/bin/env python3
"""
Optimized main entry point for OpenSearch-SQL pipeline.
Provides complete functionality with performance improvements.
"""

import argparse
import json
import os
import sys
from ..utils.loguru_config import get_logger
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Import optimized components
from src_optimized.runner_optimized.concurrent_run_manager import ConcurrentRunManager, RunConfig
from src_optimized.services.model_pool import initialize_model_pool
from src_optimized.services.embedding_service import embedding_service_pool

# Configure logging
logger = get_logger(__name__)


def load_dataset(data_path: str) -> List[Dict[str, Any]]:
    """
    Loads the dataset from the specified path.
    
    Args:
        data_path (str): Path to the data file.
    
    Returns:
        List[Dict[str, Any]]: The loaded dataset.
    """
    with open(data_path, 'r') as file:
        dataset = json.load(file)
    logger.info(f"Loaded {len(dataset)} samples from {data_path}")
    return dataset


def setup_optimizations(args) -> RunConfig:
    """
    Setup optimization configurations based on arguments.
    
    Args:
        args: Command line arguments
        
    Returns:
        RunConfig: Configuration for optimized execution
    """
    # Determine execution mode based on environment and arguments
    execution_mode = args.execution_mode if hasattr(args, 'execution_mode') else 'multiprocess'
    num_workers = args.num_workers if hasattr(args, 'num_workers') else 3
    
    # Parse pipeline setup to extract model configurations
    pipeline_setup = json.loads(args.pipeline_setup)
    bert_model = None
    device = 'cpu'
    
    for node_config in pipeline_setup.values():
        if isinstance(node_config, dict):
            if 'bert_model' in node_config:
                bert_model = node_config['bert_model']
            if 'device' in node_config:
                device = node_config['device']
    
    # Initialize model pool if bert model is specified
    if bert_model:
        logger.info(f"Initializing model pool for {bert_model} on {device}")
        initialize_model_pool(
            model_name=bert_model,
            device=device,
            pool_size=num_workers  # One model per worker
        )
    
    # Create run configuration
    config = RunConfig(
        execution_mode=execution_mode,
        num_workers=num_workers,
        batch_size=getattr(args, 'batch_size', 10),
        enable_progress_bar=getattr(args, 'enable_progress_bar', True),
        checkpoint_enabled=args.use_checkpoint if hasattr(args, 'use_checkpoint') else False,
        model_pool_size=num_workers,
        cache_enabled=getattr(args, 'cache_enabled', True)
    )
    
    logger.info(f"Optimization config: mode={config.execution_mode}, workers={config.num_workers}")
    
    return config


def main(args):
    """
    Main function to run the optimized pipeline.
    
    Args:
        args: Command line arguments
    """
    logger.info("=" * 60)
    logger.info("OpenSearch-SQL Optimized Pipeline")
    logger.info("=" * 60)
    
    # Determine dataset path
    if hasattr(args, 'dev_json_path') and args.dev_json_path:
        db_json = args.dev_json_path
    else:
        # Use default path structure
        if os.path.exists(f"{args.db_root_path}/data_preprocess/{args.data_mode}.json"):
            db_json = f"{args.db_root_path}/data_preprocess/{args.data_mode}.json"
        elif os.path.exists(f"{args.db_root_path}/dev_20240627/dev.json"):
            db_json = f"{args.db_root_path}/dev_20240627/dev.json"
        else:
            # Fallback to original structure
            db_json = f"{args.db_root_path}/{args.data_mode}/{args.data_mode}.json"
    
    logger.info(f"Loading dataset from: {db_json}")
    
    # Load dataset
    dataset = load_dataset(db_json)
    
    # Setup optimizations
    config = setup_optimizations(args)
    
    # Create optimized run manager
    run_manager = ConcurrentRunManager(args, config)
    
    # Initialize tasks
    start = args.start if hasattr(args, 'start') else 0
    end = args.end if hasattr(args, 'end') else -1
    if end == -1:
        end = len(dataset)
    
    logger.info(f"Processing tasks from index {start} to {end}")
    run_manager.initialize_tasks(start, end, dataset)
    
    # Run tasks with optimizations
    start_time = datetime.now()
    run_manager.run_tasks()
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # Generate SQL files
    run_manager.generate_sql_files()
    
    # Print final statistics
    logger.info("=" * 60)
    logger.info("Pipeline Execution Complete")
    logger.info("=" * 60)
    logger.info(f"Total execution time: {elapsed:.2f} seconds")
    logger.info(f"Average time per task: {elapsed/run_manager.processed_tasks:.2f} seconds")
    
    # Cleanup resources
    run_manager.shutdown()
    embedding_service_pool.shutdown_all()
    
    logger.info("All resources cleaned up. Exiting.")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="OpenSearch-SQL Optimized Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings
  python main_optimized.py --data_mode dev --db_root_path Bird \\
    --pipeline_nodes "generate_db_schema+extract_col_value+..." \\
    --pipeline_setup '{"generate_db_schema": {...}}'
  
  # Run with multiprocess optimization
  python main_optimized.py --data_mode dev --db_root_path Bird \\
    --pipeline_nodes "..." --pipeline_setup '...' \\
    --execution_mode multiprocess --num_workers 4
  
  # Run with checkpoint support
  python main_optimized.py --data_mode dev --db_root_path Bird \\
    --pipeline_nodes "..." --pipeline_setup '...' \\
    --use_checkpoint --checkpoint_dir ./checkpoints
        """
    )
    
    # Required arguments
    parser.add_argument('--data_mode', type=str, required=True, 
                       choices=['dev', 'train'],
                       help="Mode of the data to be processed")
    parser.add_argument('--db_root_path', type=str, required=True,
                       help="Root directory path for the database")
    parser.add_argument('--pipeline_nodes', type=str, required=True,
                       help="Pipeline nodes configuration (e.g., 'node1+node2+node3')")
    parser.add_argument('--pipeline_setup', type=str, required=True,
                       help="Pipeline setup in JSON format")
    
    # Optional arguments for data processing
    parser.add_argument('--start', type=int, default=0,
                       help="Start index for processing (inclusive)")
    parser.add_argument('--end', type=int, default=-1,
                       help="End index for processing (exclusive, -1 for all)")
    parser.add_argument('--dev_json_path', type=str, default=None,
                       help="Custom path to dev.json file")
    
    # Checkpoint arguments
    parser.add_argument('--use_checkpoint', action='store_true',
                       help="Enable checkpoint loading")
    parser.add_argument('--checkpoint_nodes', type=str,
                       help="Comma-separated list of checkpoint nodes")
    parser.add_argument('--checkpoint_dir', type=str,
                       help="Directory containing checkpoints")
    
    # Optimization arguments
    parser.add_argument('--execution_mode', type=str, 
                       choices=['sequential', 'thread', 'multiprocess', 'async'],
                       default='multiprocess',
                       help="Execution mode for task processing")
    parser.add_argument('--num_workers', type=int, default=3,
                       help="Number of worker processes/threads")
    parser.add_argument('--batch_size', type=int, default=10,
                       help="Batch size for task processing")
    parser.add_argument('--cache_enabled', action='store_true', default=True,
                       help="Enable embedding cache")
    parser.add_argument('--no_cache', dest='cache_enabled', action='store_false',
                       help="Disable embedding cache")
    parser.add_argument('--enable_progress_bar', action='store_true', default=True,
                       help="Show progress bar during execution")
    parser.add_argument('--no_progress', dest='enable_progress_bar', action='store_false',
                       help="Disable progress bar")
    
    # Logging arguments
    parser.add_argument('--log_level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help="Logging level")
    
    # Performance monitoring
    parser.add_argument('--enable_profiling', action='store_true',
                       help="Enable performance profiling")
    parser.add_argument('--save_stats', action='store_true',
                       help="Save execution statistics to file")
    
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_arguments()
    
    # Set timestamp
    args.run_start_time = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    # Validate checkpoint arguments
    if args.use_checkpoint:
        if not args.checkpoint_nodes:
            raise ValueError('Please provide --checkpoint_nodes when using checkpoints')
        if not args.checkpoint_dir:
            raise ValueError('Please provide --checkpoint_dir when using checkpoints')
        if not os.path.exists(args.checkpoint_dir):
            raise ValueError(f'Checkpoint directory does not exist: {args.checkpoint_dir}')
        logger.info(f'Using checkpoints from: {args.checkpoint_dir}')
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Enable profiling if requested
    if args.enable_profiling:
        import cProfile
        import pstats
        
        profiler = cProfile.Profile()
        profiler.enable()
        
        try:
            main(args)
        finally:
            profiler.disable()
            stats = pstats.Stats(profiler)
            stats.sort_stats('cumulative')
            stats.print_stats(30)
            
            if args.save_stats:
                stats_file = f"profile_{args.run_start_time}.stats"
                stats.dump_stats(stats_file)
                logger.info(f"Profiling stats saved to: {stats_file}")
    else:
        main(args)