"""
Standalone RunManager implementation for OpenSearch-SQL pipeline.
"""
import os
import json
import logging
from pathlib import Path
from multiprocessing import Pool
from typing import List, Dict, Any, Tuple
from datetime import datetime

from ..core import Task, Logger, DatabaseManager, StatisticsManager, PipelineManager
from ..pipeline import build_pipeline, validate_pipeline_nodes


# Default values - will be overridden by args
DEFAULT_NUM_WORKERS = 3


class RunManager:
    """
    Manages the execution of OpenSearch-SQL pipeline tasks.
    """
    
    RESULT_ROOT_PATH = "results"

    def __init__(self, args: Any):
        """
        Initialize the RunManager.
        
        Args:
            args: Arguments object containing configuration.
        """
        self.args = args
        self.result_directory = self.get_result_directory()
        self.statistics_manager = StatisticsManager(self.result_directory)
        self.tasks: List[Task] = []
        self.total_number_of_tasks = 0
        self.processed_tasks = 0
        
        # Setup logging
        self._setup_logging()
        
        logging.info(f"RunManager initialized with result directory: {self.result_directory}")

    def _setup_logging(self):
        """Setup logging configuration."""
        log_level = getattr(self.args, 'log_level', 'info').upper()
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def get_result_directory(self) -> str:
        """
        Creates and returns the result directory path based on the input arguments.
        
        Returns:
            str: The path to the result directory.
        """
        data_mode = self.args.data_mode
        pipeline_nodes = self.args.pipeline_nodes
        dataset_name = Path(self.args.db_root_path).stem
        run_folder_name = str(self.args.run_start_time)
        run_folder_path = Path(self.RESULT_ROOT_PATH) / data_mode / pipeline_nodes / dataset_name / run_folder_name
        
        run_folder_path.mkdir(parents=True, exist_ok=True)
        
        # Save arguments to file
        arg_file_path = run_folder_path / "-args.json"
        with arg_file_path.open('w') as file:
            json.dump(vars(self.args), file, indent=4)
        
        # Create logs directory
        log_folder_path = run_folder_path / "logs"
        log_folder_path.mkdir(exist_ok=True)
        
        return str(run_folder_path)

    def initialize_tasks(self, start: int, end: int, dataset: List[Dict[str, Any]]):
        """
        Initializes tasks from the provided dataset.
        
        Args:
            start (int): Starting index.
            end (int): Ending index.
            dataset (List[Dict[str, Any]]): The dataset containing task information.
        """
        for i, data in enumerate(dataset):
            if i < start:  # Skip before start
                continue
            if end > 0 and i >= end:  # Stop at end
                break
                
            if "question_id" not in data:
                data = {"question_id": i, **data}
                
            try:
                task = Task(data)
                self.tasks.append(task)
            except Exception as e:
                logging.error(f"Error creating task {i}: {e}")
                continue
        
        self.total_number_of_tasks = len(self.tasks)
        logging.info(f"Total number of tasks: {self.total_number_of_tasks}")

    def run_tasks(self):
        """Runs the tasks using a pool of workers or sequentially."""
        # Get concurrency settings from args
        enable_multiprocessing = getattr(self.args, 'enable_multiprocessing', False)
        num_workers = getattr(self.args, 'num_workers', DEFAULT_NUM_WORKERS)
        
        logging.info(f"Concurrency settings: multiprocessing={enable_multiprocessing}, workers={num_workers}")
        
        if enable_multiprocessing and num_workers > 1:
            logging.info(f"Running {self.total_number_of_tasks} tasks in parallel with {num_workers} workers")
            self._run_tasks_parallel(num_workers)
        else:
            logging.info(f"Running {self.total_number_of_tasks} tasks sequentially")
            self._run_tasks_sequential()

    def _run_tasks_parallel(self, num_workers):
        """Run tasks in parallel using multiprocessing."""
        try:
            import concurrent.futures
            with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
                # Submit all tasks
                futures = []
                for task in self.tasks:
                    future = executor.submit(self.worker, task)
                    futures.append(future)
                
                # Process results as they complete
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        self.task_done(result)
                    except Exception as e:
                        logging.error(f"Error processing parallel task: {e}")
                        
        except Exception as e:
            logging.error(f"Error in parallel execution: {e}")
            # Fallback to sequential execution
            self._run_tasks_sequential()

    def _run_tasks_sequential(self):
        """Run tasks sequentially."""
        for task in self.tasks:
            try:
                result = self.worker(task)
                self.task_done(result)
            except Exception as e:
                logging.error(f"Error processing task {task.question_id}: {e}")
                self.task_done((None, task.db_id, task.question_id))

    def worker(self, task: Task) -> Tuple[Any, str, int]:
        """
        Worker function to process a single task.
        
        Args:
            task (Task): The task to be processed.
        
        Returns:
            tuple: The state of the task processing and task identifiers.
        """
        try:
            # Initialize components for this task
            database_manager = DatabaseManager(
                db_mode=self.args.data_mode, 
                db_root_path=self.args.db_root_path, 
                db_id=task.db_id
            )
            
            logger = Logger(
                db_id=task.db_id, 
                question_id=task.question_id, 
                result_directory=self.result_directory
            )
            logger._set_log_level(self.args.log_level)
            logger.log(f"Processing task: {task.db_id} {task.question_id}", "info")
            
            # Initialize pipeline manager
            pipeline_setup = json.loads(self.args.pipeline_setup)
            pipeline_manager = PipelineManager(pipeline_setup)
            
            # Load checkpoint if available
            execution_history = self.load_checkpoint(task.db_id, task.question_id)
            
            # Build and run pipeline
            initial_state = {
                "keys": {
                    "task": task, 
                    "execution_history": execution_history
                }
            }
            
            logging.info("Building pipeline...")
            
            # Validate pipeline nodes first
            if not validate_pipeline_nodes(self.args.pipeline_nodes):
                raise ValueError(f"Invalid pipeline nodes: {self.args.pipeline_nodes}")
            
            app = build_pipeline(self.args.pipeline_nodes)
            logging.info("Pipeline built successfully.")

            # Determine the final node
            if hasattr(app, 'nodes') and app.nodes:
                last_node_key = list(app.nodes.keys())[-1]
                logging.debug(f'Final node: {last_node_key}')
            else:
                last_node_key = '__end__'  # Default fallback

            # Execute pipeline
            final_state = None
            for state in app.stream(initial_state):
                final_state = state
                continue

            if final_state and last_node_key in final_state:
                return final_state[last_node_key], task.db_id, task.question_id
            else:
                logging.warning(f"No final state found for task {task.question_id}")
                return final_state, task.db_id, task.question_id
                
        except Exception as e:
            logger.log(f"Error processing task: {task.db_id} {task.question_id}\n{e}", "error")
            logging.error(f"Worker error for task {task.question_id}: {e}")
            return None, task.db_id, task.question_id

    def task_done(self, log: Tuple[Any, str, int]):
        """
        Callback function when a task is done.
        
        Args:
            log (tuple): The log information of the task processing.
        """
        state, db_id, question_id = log
        
        if state is None:
            logging.warning(f"Task {question_id} completed with no result")
            self.processed_tasks += 1
            self.plot_progress()
            return

        try:
            execution_history = state["keys"]['execution_history']
            
            # Update statistics from evaluation result
            if execution_history:
                evaluation_result = execution_history[-1]
                if evaluation_result.get("node_type") == "evaluation":
                    for evaluation_for, result in evaluation_result.items():
                        if evaluation_for in ['node_type', 'status']:
                            continue
                        self.statistics_manager.update_stats(db_id, question_id, evaluation_for, result)
                    self.statistics_manager.dump_statistics_to_file()
        
        except Exception as e:
            logging.error(f"Error processing task result for {question_id}: {e}")
        
        self.processed_tasks += 1
        self.plot_progress()

    def plot_progress(self, bar_length: int = 50):
        """
        Plots the progress of task processing.
        
        Args:
            bar_length (int, optional): The length of the progress bar. Defaults to 50.
        """
        if self.total_number_of_tasks == 0:
            return
            
        processed_ratio = self.processed_tasks / self.total_number_of_tasks
        progress_length = int(processed_ratio * bar_length)
        
        progress_bar = '=' * progress_length + '>' + ' ' * (bar_length - progress_length - 1)
        percentage = processed_ratio * 100
        
        print(f'\r[{progress_bar}] {self.processed_tasks}/{self.total_number_of_tasks} ({percentage:.1f}%)', end='', flush=True)
        
        if self.processed_tasks == self.total_number_of_tasks:
            print()  # New line when complete

    def load_checkpoint(self, db_id: str, question_id: int) -> List[Dict[str, Any]]:
        """
        Load checkpoint data if available.
        
        Args:
            db_id (str): Database ID.
            question_id (int): Question ID.
            
        Returns:
            List[Dict[str, Any]]: Execution history from checkpoint.
        """
        execution_history = []
        
        if not getattr(self.args, 'use_checkpoint', False):
            return execution_history
            
        if not hasattr(self.args, 'checkpoint_dir') or not self.args.checkpoint_dir:
            logging.warning("Checkpoint enabled but no checkpoint directory provided")
            return execution_history
            
        checkpoint_file = Path(self.args.checkpoint_dir) / f"{question_id}_{db_id}.json"
        
        if checkpoint_file.exists():
            try:
                with checkpoint_file.open('r') as file:
                    checkpoint = json.load(file)
                    
                    checkpoint_nodes = getattr(self.args, 'checkpoint_nodes', '').split('+')
                    
                    for step in checkpoint:
                        node_type = step.get("node_type", "")
                        if not checkpoint_nodes or node_type in checkpoint_nodes:
                            execution_history.append(step)
                            
                if execution_history:
                    logging.info(f"Loaded checkpoint for {question_id}_{db_id}: {len(execution_history)} steps")
                    logging.debug(f"Checkpoint ends at: {execution_history[-1]['node_type']}")
                    
            except Exception as e:
                logging.warning(f"Error loading checkpoint {checkpoint_file}: {e}")
        else:
            logging.debug(f"Checkpoint file not found: {checkpoint_file}")
            
        return execution_history

    def generate_sql_files(self):
        """Generates SQL files from the execution history."""
        try:
            sqls = {}
            
            # Collect SQLs from result files
            for file_path in Path(self.result_directory).glob("*.json"):
                if file_path.name.startswith("-"):
                    continue  # Skip system files
                    
                try:
                    # Parse filename to get question_id and db_id
                    filename = file_path.stem  # Remove .json extension
                    if "_" in filename:
                        parts = filename.split("_", 1)
                        question_id = int(parts[0])
                        db_id = parts[1]
                        
                        with file_path.open('r') as f:
                            exec_history = json.load(f)
                            
                        # Extract SQLs from execution history
                        for step in exec_history:
                            if "SQL" in step:
                                node_type = step["node_type"]
                                if node_type not in sqls:
                                    sqls[node_type] = {}
                                sqls[node_type][question_id] = step["SQL"]
                                
                except Exception as e:
                    logging.warning(f"Error processing result file {file_path}: {e}")
                    continue
            
            # Write SQL files for each node type
            for node_type, sql_dict in sqls.items():
                output_file = Path(self.result_directory) / f"-{node_type}.json"
                with output_file.open('w') as f:
                    json.dump(sql_dict, f, indent=4, ensure_ascii=False)
                    
                logging.info(f"Generated SQL file: {output_file} ({len(sql_dict)} queries)")
                
        except Exception as e:
            logging.error(f"Error generating SQL files: {e}")

    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the execution.
        
        Returns:
            Dict[str, Any]: Execution summary.
        """
        return {
            "total_tasks": self.total_number_of_tasks,
            "processed_tasks": self.processed_tasks,
            "completion_rate": self.processed_tasks / self.total_number_of_tasks if self.total_number_of_tasks > 0 else 0,
            "result_directory": self.result_directory,
            "statistics": self.statistics_manager.get_current_stats()
        }

    def cleanup(self):
        """Cleanup resources."""
        try:
            # Print final statistics
            self.statistics_manager.print_summary()
            
            # Generate final SQL files
            self.generate_sql_files()
            
            logging.info("RunManager cleanup completed")
            
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()