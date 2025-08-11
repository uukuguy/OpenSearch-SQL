"""
Optimized Run Manager with concurrent processing support.
Implements multiple execution strategies: multiprocessing, threading, and async.
"""

import os
import json
import time
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from multiprocessing import Pool, Queue, Manager
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from threading import Lock
import queue

# Import from standalone implementation
from ..core import Logger, Task, DatabaseManager, StatisticsManager, PipelineManager
from ..pipeline import build_pipeline

# Import optimized services
from ..services.model_pool import initialize_model_pool, model_pool_manager
from ..services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


@dataclass
class RunConfig:
    """Configuration for run manager."""
    execution_mode: str = 'multiprocess'  # 'multiprocess', 'thread', 'async', 'sequential'
    num_workers: int = 3
    batch_size: int = 10
    enable_progress_bar: bool = True
    checkpoint_enabled: bool = True
    model_pool_size: int = 3
    cache_enabled: bool = True


class ConcurrentRunManager:
    """Optimized run manager with multiple execution strategies."""
    
    RESULT_ROOT_PATH = "results"
    
    def __init__(self, args: Any, config: Optional[RunConfig] = None):
        self.args = args
        self.config = config or RunConfig()
        self.result_directory = self.get_result_directory()
        self.statistics_manager = StatisticsManager(self.result_directory)
        self.tasks: List[Task] = []
        self.total_number_of_tasks = 0
        self.processed_tasks = 0
        self._lock = Lock()
        self._start_time = None
        
        # Initialize model pool if needed
        self._initialize_model_pool()
        
        # Initialize embedding service
        self._initialize_embedding_service()
    
    def _initialize_model_pool(self):
        """Initialize the model pool based on configuration."""
        if hasattr(self.args, 'pipeline_setup'):
            pipeline_setup = json.loads(self.args.pipeline_setup)
            
            # Find bert_model in pipeline setup
            bert_model = None
            for node_config in pipeline_setup.values():
                if isinstance(node_config, dict) and 'bert_model' in node_config:
                    bert_model = node_config['bert_model']
                    break
            
            if bert_model:
                logger.info(f"Initializing model pool with {bert_model}")
                initialize_model_pool(
                    model_name=bert_model,
                    pool_size=self.config.model_pool_size
                )
    
    def _initialize_embedding_service(self):
        """Initialize embedding service for the run."""
        if hasattr(self.args, 'pipeline_setup'):
            pipeline_setup = json.loads(self.args.pipeline_setup)
            
            for node_config in pipeline_setup.values():
                if isinstance(node_config, dict) and 'bert_model' in node_config:
                    bert_model = node_config['bert_model']
                    self.embedding_service = get_embedding_service(
                        model_name=bert_model,
                        cache_enabled=self.config.cache_enabled
                    )
                    logger.info(f"Initialized embedding service for {bert_model}")
                    break
    
    def get_result_directory(self) -> str:
        """Creates and returns the result directory path."""
        data_mode = self.args.data_mode
        pipeline_nodes = self.args.pipeline_nodes
        dataset_name = Path(self.args.db_root_path).stem
        run_folder_name = str(self.args.run_start_time)
        run_folder_path = Path(self.RESULT_ROOT_PATH) / data_mode / pipeline_nodes / dataset_name / run_folder_name
        
        run_folder_path.mkdir(parents=True, exist_ok=True)
        
        # Save arguments and configuration
        arg_file_path = run_folder_path / "-args.json"
        with arg_file_path.open('w') as file:
            args_dict = vars(self.args)
            args_dict['run_config'] = {
                'execution_mode': self.config.execution_mode,
                'num_workers': self.config.num_workers,
                'batch_size': self.config.batch_size
            }
            json.dump(args_dict, file, indent=4)
        
        log_folder_path = run_folder_path / "logs"
        log_folder_path.mkdir(exist_ok=True)
        
        return str(run_folder_path)
    
    def initialize_tasks(self, start: int, end: int, dataset: List[Dict[str, Any]]):
        """Initialize tasks from the dataset."""
        for i, data in enumerate(dataset):
            if i < start:
                continue
            if end > 0 and i >= end:
                break
            if "question_id" not in data:
                data = {"question_id": i, **data}
            task = Task(data)
            self.tasks.append(task)
        
        self.total_number_of_tasks = len(self.tasks)
        logger.info(f"Initialized {self.total_number_of_tasks} tasks")
    
    def run_tasks(self):
        """Run tasks using the configured execution mode."""
        self._start_time = time.time()
        
        logger.info(f"Starting task execution with mode: {self.config.execution_mode}")
        
        if self.config.execution_mode == 'multiprocess':
            self._run_multiprocess()
        elif self.config.execution_mode == 'thread':
            self._run_threaded()
        elif self.config.execution_mode == 'async':
            asyncio.run(self._run_async())
        else:  # sequential
            self._run_sequential()
        
        elapsed_time = time.time() - self._start_time
        logger.info(f"All tasks completed in {elapsed_time:.2f} seconds")
        
        # Print final statistics
        self._print_final_stats(elapsed_time)
    
    def _run_multiprocess(self):
        """Run tasks using multiprocessing."""
        with ProcessPoolExecutor(max_workers=self.config.num_workers) as executor:
            # Submit tasks in batches
            futures = []
            for i in range(0, len(self.tasks), self.config.batch_size):
                batch = self.tasks[i:i + self.config.batch_size]
                for task in batch:
                    future = executor.submit(self._worker_process_safe, task)
                    futures.append(future)
            
            # Process completed tasks
            for future in as_completed(futures):
                try:
                    result = future.result()
                    self.task_done(result)
                except Exception as e:
                    logger.error(f"Task failed: {e}")
    
    def _run_threaded(self):
        """Run tasks using threading."""
        with ThreadPoolExecutor(max_workers=self.config.num_workers) as executor:
            futures = []
            for task in self.tasks:
                future = executor.submit(self.worker, task)
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    self.task_done(result)
                except Exception as e:
                    logger.error(f"Task failed: {e}")
    
    async def _run_async(self):
        """Run tasks using asyncio."""
        # Create task queue
        task_queue = asyncio.Queue()
        for task in self.tasks:
            await task_queue.put(task)
        
        # Create workers
        workers = [
            asyncio.create_task(self._async_worker(task_queue, i))
            for i in range(self.config.num_workers)
        ]
        
        # Wait for all tasks to complete
        await task_queue.join()
        
        # Cancel workers
        for worker in workers:
            worker.cancel()
        
        await asyncio.gather(*workers, return_exceptions=True)
    
    async def _async_worker(self, task_queue: asyncio.Queue, worker_id: int):
        """Async worker to process tasks."""
        while True:
            try:
                task = await task_queue.get()
                
                # Run the synchronous worker in executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self.worker, task)
                
                self.task_done(result)
                task_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                task_queue.task_done()
    
    def _run_sequential(self):
        """Run tasks sequentially (fallback mode)."""
        for task in self.tasks:
            try:
                result = self.worker(task)
                self.task_done(result)
            except Exception as e:
                logger.error(f"Task failed: {e}")
    
    def _worker_process_safe(self, task: Task) -> Tuple[Any, str, int]:
        """Process-safe worker that reinitializes services."""
        # In multiprocess mode, we need to reinitialize services
        # as they can't be shared across processes
        try:
            # Reinitialize embedding service for this process
            if hasattr(self.args, 'pipeline_setup'):
                pipeline_setup = json.loads(self.args.pipeline_setup)
                for node_config in pipeline_setup.values():
                    if isinstance(node_config, dict) and 'bert_model' in node_config:
                        bert_model = node_config['bert_model']
                        # Each process gets its own embedding service
                        get_embedding_service(
                            model_name=bert_model,
                            cache_enabled=self.config.cache_enabled
                        )
                        break
            
            return self.worker(task)
        except Exception as e:
            logger.error(f"Process worker error: {e}")
            return None, task.db_id, task.question_id
    
    def worker(self, task: Task) -> Tuple[Any, str, int]:
        """Worker function to process a single task."""
        try:
            # Initialize managers
            database_manager = DatabaseManager(
                db_mode=self.args.data_mode,
                db_root_path=self.args.db_root_path,
                db_id=task.db_id
            )
            
            logger_instance = Logger(
                db_id=task.db_id,
                question_id=task.question_id,
                result_directory=self.result_directory
            )
            logger_instance._set_log_level(self.args.log_level)
            logger_instance.log(f"Processing task: {task.db_id} {task.question_id}", "info")
            
            # Initialize pipeline
            pipeline_manager = PipelineManager(json.loads(self.args.pipeline_setup))
            execution_history = self.load_checkpoint(task.db_id, task.question_id)
            
            initial_state = {"keys": {"task": task, "execution_history": execution_history}}
            
            # Build and run pipeline
            app = build_pipeline(self.args.pipeline_nodes)
            
            # Get the last node key
            last_node_key = None
            if hasattr(app, 'nodes') and app.nodes:
                last_node_key = list(app.nodes.keys())[-1]
            
            # Execute pipeline
            for state in app.stream(initial_state):
                continue
            
            return state[last_node_key], task.db_id, task.question_id
            
        except Exception as e:
            logger.error(f"Error processing task {task.db_id} {task.question_id}: {e}")
            return None, task.db_id, task.question_id
    
    def task_done(self, log: Tuple[Any, str, int]):
        """Callback when a task is completed."""
        state, db_id, question_id = log
        
        if state is None:
            return
        
        # Process evaluation results
        evaluation_result = state["keys"]['execution_history'][-1]
        if evaluation_result.get("node_type") == "evaluation":
            for evaluation_for, result in evaluation_result.items():
                if evaluation_for in ['node_type', 'status']:
                    continue
                self.statistics_manager.update_stats(db_id, question_id, evaluation_for, result)
            self.statistics_manager.dump_statistics_to_file()
        
        # Update progress
        with self._lock:
            self.processed_tasks += 1
            self.plot_progress()
    
    def plot_progress(self, bar_length: int = 100):
        """Display progress bar."""
        if not self.config.enable_progress_bar:
            return
        
        processed_ratio = self.processed_tasks / self.total_number_of_tasks
        progress_length = int(processed_ratio * bar_length)
        
        # Calculate ETA
        if self._start_time and self.processed_tasks > 0:
            elapsed = time.time() - self._start_time
            rate = self.processed_tasks / elapsed
            remaining = (self.total_number_of_tasks - self.processed_tasks) / rate if rate > 0 else 0
            eta_str = f" ETA: {remaining:.1f}s"
        else:
            eta_str = ""
        
        # Clear previous line and print progress
        print('\x1b[1A' + '\x1b[2K' + '\x1b[1A')
        print(f"[{'=' * progress_length}>{' ' * (bar_length - progress_length)}] "
              f"{self.processed_tasks}/{self.total_number_of_tasks}{eta_str}")
    
    def load_checkpoint(self, db_id: str, question_id: int) -> List[Dict[str, Any]]:
        """Load checkpoint if available."""
        execution_history = []
        
        if self.config.checkpoint_enabled and hasattr(self.args, 'use_checkpoint') and self.args.use_checkpoint:
            checkpoint_file = Path(self.args.checkpoint_dir) / f"{question_id}_{db_id}.json"
            
            if checkpoint_file.exists():
                with checkpoint_file.open('r') as file:
                    checkpoint = json.load(file)
                    for step in checkpoint:
                        node_type = step["node_type"]
                        if node_type in self.args.checkpoint_nodes:
                            execution_history.append(step)
                
                logger.info(f"Loaded checkpoint for {db_id}_{question_id}")
        
        return execution_history
    
    def _print_final_stats(self, elapsed_time: float):
        """Print final execution statistics."""
        print("\n" + "=" * 50)
        print("Execution Summary")
        print("=" * 50)
        print(f"Mode: {self.config.execution_mode}")
        print(f"Workers: {self.config.num_workers}")
        print(f"Total tasks: {self.total_number_of_tasks}")
        print(f"Completed: {self.processed_tasks}")
        print(f"Total time: {elapsed_time:.2f}s")
        print(f"Avg time/task: {elapsed_time/self.processed_tasks:.2f}s")
        
        # Print embedding service stats if available
        if hasattr(self, 'embedding_service'):
            stats = self.embedding_service.get_stats()
            print(f"\nEmbedding Service Stats:")
            print(f"  Cache hits: {stats.get('cache_hits', 0)}")
            print(f"  Cache misses: {stats.get('cache_misses', 0)}")
            
            if 'cache_stats' in stats:
                cache_stats = stats['cache_stats']['l1_cache']
                print(f"  Cache hit rate: {cache_stats.get('hit_rate', 0):.2%}")
        
        # Print model pool stats
        pool_stats = model_pool_manager.get_all_stats()
        if pool_stats:
            print(f"\nModel Pool Stats:")
            for model_name, stats in pool_stats.items():
                print(f"  {model_name}:")
                print(f"    Pool size: {stats['pool_size']}")
                print(f"    Available: {stats['available']}")
                print(f"    In use: {stats['in_use']}")
    
    def generate_sql_files(self):
        """Generates SQL files from the execution history."""
        logger.info("Generating SQL files from execution history")
        sqls = {}
        
        # Scan result directory for execution history files
        for file in os.listdir(self.result_directory):
            if file.endswith(".json") and "_" in file:
                _index = file.find("_")
                question_id = int(file[:_index])
                db_id = file[_index + 1:-5]
                
                filepath = os.path.join(self.result_directory, file)
                with open(filepath, 'r') as f:
                    exec_history = json.load(f)
                    
                    # Extract SQL from each step
                    for step in exec_history:
                        if "SQL" in step:
                            node_type = step["node_type"]
                            if node_type not in sqls:
                                sqls[node_type] = {}
                            sqls[node_type][question_id] = step["SQL"]
        
        # Write SQL files for each node type
        for key, value in sqls.items():
            output_file = os.path.join(self.result_directory, f"-{key}.json")
            with open(output_file, 'w') as f:
                json.dump(value, f, indent=4, ensure_ascii=False)
            logger.info(f"Generated SQL file: {output_file}")
        
        logger.info(f"SQL file generation complete. Generated {len(sqls)} files")
    
    def shutdown(self):
        """Cleanup resources."""
        logger.info("Shutting down run manager")
        
        # Shutdown services
        if hasattr(self, 'embedding_service'):
            self.embedding_service.shutdown()
        
        model_pool_manager.shutdown()
        
        logger.info("Shutdown complete")