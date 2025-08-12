#!/usr/bin/env python3
"""
Fully standalone main entry point for OpenSearch-SQL pipeline.
Uses only the standalone implementation without any external dependencies.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Import standalone components only
from .core import Task, DatabaseManager, Logger, PipelineManager, StatisticsManager
from .pipeline import build_pipeline
from .llm import ModelFactory
from .utils import ConfigHelper, DataHelper
from .utils.loguru_config import setup_logging, get_logger
from .runner import RunManager

# Initialize logger
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
        logger.info(f"Loaded {len(dataset)} samples from {data_path}")
        return dataset
    except FileNotFoundError:
        logger.error(f"Dataset file not found: {data_path}")
        # Return mock data for testing
        return [
            {
                "question_id": 1,
                "question": "Show all users",
                "db_id": "test_db",
                "evidence": "Users are stored in the user table",
                "SQL": "SELECT * FROM users;"
            }
        ]
    except Exception as e:
        logger.error(f"Error loading dataset: {e}")
        return []


def main(args):
    """
    Main function to run the standalone pipeline.
    
    Args:
        args: Command line arguments
    """
    # Setup logging first
    setup_logging(
        log_level=getattr(args, 'log_level', 'INFO'),
        verbose=getattr(args, 'verbose', False)
    )
    logger = get_logger("main")
    
    logger.info("=" * 60)
    logger.info("OpenSearch-SQL Standalone Pipeline")
    logger.info("=" * 60)
    
    # Parse optimization settings from string arguments
    args.enable_multiprocessing = args.enable_multiprocessing.lower() == 'true'
    args.enable_threading = args.enable_threading.lower() == 'true'
    args.enable_async = args.enable_async.lower() == 'true'
    args.enable_cache = args.enable_cache.lower() == 'true'
    args.enable_redis = args.enable_redis.lower() == 'true'
    args.preload_models = args.preload_models.lower() == 'true'
    
    # Display optimization configuration
    logger.info("Performance Optimization Settings:")
    logger.info(f"  Workers: {args.num_workers} (concurrent processing)")
    logger.info(f"  Model pool: {args.pool_size} (avoid reloading)")
    logger.info(f"  Multiprocessing: {args.enable_multiprocessing}")
    logger.info(f"  Threading: {args.enable_threading}")
    logger.info(f"  Caching: {args.enable_cache} (L1 size: {args.cache_l1_size})")
    logger.info(f"  Redis cache: {args.enable_redis}")
    if args.enable_redis:
        logger.info(f"  Redis: {args.redis_host}:{args.redis_port} (DB: {args.redis_db})")
    logger.info("")
    
    # Determine dataset path
    dataset_paths = [
        f"{args.db_root_path}/data_preprocess/{args.data_mode}.json",
        f"{args.db_root_path}/dev_20240627/dev.json",
        f"{args.db_root_path}/{args.data_mode}/{args.data_mode}.json"
    ]
    
    db_json = None
    for path in dataset_paths:
        if os.path.exists(path):
            db_json = path
            break
    
    if db_json is None:
        logger.warning("No dataset file found, using mock data")
        db_json = "mock_dataset"
    
    logger.info(f"Using dataset: {db_json}")
    
    # Load dataset
    dataset = load_dataset(db_json) if db_json != "mock_dataset" else load_dataset("")
    
    # Initialize optimization services
    if args.preload_models:
        try:
            # Get BERT model path from pipeline setup
            pipeline_setup = json.loads(args.pipeline_setup)
            bert_path = None
            
            # Find BERT model path from any node that uses it
            for node_config in pipeline_setup.values():
                if isinstance(node_config, dict) and "bert_model" in node_config:
                    bert_path = node_config["bert_model"]
                    break
            
            if bert_path:
                from .services.model_pool import initialize_model_pool
                logger.info(f"Initializing model pool with {bert_path}, pool size: {args.pool_size}")
                initialize_model_pool(bert_path, device="cpu", pool_size=args.pool_size)
                logger.info("Model pool initialized successfully")
            
        except Exception as e:
            logger.warning(f"Failed to initialize model pool: {e}")
    
    # Create run manager with standalone components
    run_manager = RunManager(args)
    
    # Initialize tasks
    start = getattr(args, 'start', 0)
    end = getattr(args, 'end', -1)
    if end == -1:
        end = len(dataset)
    
    end = min(end, len(dataset))  # Don't exceed dataset size
    
    logger.info(f"Processing tasks from index {start} to {end}")
    run_manager.initialize_tasks(start, end, dataset)
    
    # Run tasks
    start_time = datetime.now()
    run_manager.run_tasks()
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # Generate SQL files
    run_manager.generate_sql_files()
    
    # Save final results in persistent format
    saved_files = run_manager.save_final_results()
    if saved_files:
        logger.info("Results saved to:")
        for format_name, file_path in saved_files.items():
            logger.info(f"  {format_name}: {file_path}")
    
    # Print final statistics
    logger.info("=" * 60)
    logger.info("Pipeline Execution Complete")
    logger.info("=" * 60)
    logger.info(f"Total execution time: {elapsed:.2f} seconds")
    logger.info(f"Tasks processed: {run_manager.processed_tasks}")
    if run_manager.processed_tasks > 0:
        logger.info(f"Average time per task: {elapsed/run_manager.processed_tasks:.2f} seconds")
    
    logger.info("Standalone execution completed successfully!")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="OpenSearch-SQL Standalone Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with basic settings
  python -m src_optimized.main_standalone --data_mode dev --db_root_path Bird
  
  # Run with custom pipeline
  python -m src_optimized.main_standalone --data_mode dev --db_root_path Bird \\
    --pipeline_nodes "candidate_generate+vote+evaluation" \\
    --pipeline_setup '{"candidate_generate": {"engine": "mock", "n": 1}}'
    
  # High-performance mode
  python -m src_optimized.main_standalone --data_mode dev --db_root_path Bird \\
    --num_workers 6 --pool_size 4 --enable_redis true
        """
    )
    
    # Required arguments
    parser.add_argument('--data_mode', type=str, required=True, 
                       choices=['dev', 'train'],
                       help="Mode of the data to be processed")
    parser.add_argument('--db_root_path', type=str, required=True,
                       help="Root directory path for the database")
    
    # Optional arguments
    parser.add_argument('--pipeline_nodes', type=str, 
                       default="candidate_generate+vote+evaluation",
                       help="Pipeline nodes configuration (e.g., 'node1+node2+node3')")
    parser.add_argument('--pipeline_setup', type=str, 
                       default='{"candidate_generate": {"engine": "mock", "n": 1}, "vote": {"method": "simple"}}',
                       help="Pipeline setup in JSON format")
    
    # Data processing arguments
    parser.add_argument('--start', type=int, default=0,
                       help="Start index for processing (inclusive)")
    parser.add_argument('--end', type=int, default=5,
                       help="End index for processing (exclusive, -1 for all)")
    
    # Checkpoint arguments
    parser.add_argument('--use_checkpoint', action='store_true',
                       help="Enable checkpoint loading")
    parser.add_argument('--checkpoint_nodes', type=str,
                       help="Comma-separated list of checkpoint nodes")
    parser.add_argument('--checkpoint_dir', type=str,
                       help="Directory containing checkpoints")
    
    # Logging arguments
    parser.add_argument('--log_level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help="Logging level")
    
    # 🚀 Performance optimization arguments
    # Concurrency settings
    parser.add_argument('--num_workers', type=int, default=3,
                       help="Number of concurrent workers")
    parser.add_argument('--pool_size', type=int, default=2,
                       help="Model pool size to avoid reloading")
    parser.add_argument('--enable_multiprocessing', type=str, default='true',
                       choices=['true', 'false'],
                       help="Enable multiprocessing")
    parser.add_argument('--enable_threading', type=str, default='true',
                       choices=['true', 'false'],
                       help="Enable threading")
    parser.add_argument('--enable_async', type=str, default='false',
                       choices=['true', 'false'],
                       help="Enable async processing")
    
    # Cache settings
    parser.add_argument('--enable_cache', type=str, default='true',
                       choices=['true', 'false'],
                       help="Enable multi-level caching")
    parser.add_argument('--cache_l1_size', type=int, default=1000,
                       help="L1 memory cache size")
    parser.add_argument('--enable_redis', type=str, default='false',
                       choices=['true', 'false'],
                       help="Enable Redis L2 cache")
    parser.add_argument('--redis_host', type=str, default='localhost',
                       help="Redis host")
    parser.add_argument('--redis_port', type=int, default=6379,
                       help="Redis port")
    parser.add_argument('--redis_db', type=int, default=0,
                       help="Redis database number")
    
    # Model management
    parser.add_argument('--preload_models', type=str, default='true',
                       choices=['true', 'false'],
                       help="Preload models to avoid reloading")
    parser.add_argument('--model_pool_timeout', type=int, default=30,
                       help="Model pool timeout in seconds")
    
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_arguments()
    
    # Set timestamp
    args.run_start_time = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    # Validate checkpoint arguments
    if args.use_checkpoint:
        if not args.checkpoint_nodes:
            logger.warning('Checkpoint nodes not specified')
        if not args.checkpoint_dir:
            logger.warning('Checkpoint directory not specified')
        elif not os.path.exists(args.checkpoint_dir):
            logger.warning(f'Checkpoint directory does not exist: {args.checkpoint_dir}')
    
    # Set logging level (loguru is already configured via setup_logging)
    
    try:
        main(args)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)