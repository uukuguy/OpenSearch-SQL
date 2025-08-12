"""
Standalone RunManager implementation for OpenSearch-SQL pipeline.
"""
import os
import json
from opensearch_sql.utils.loguru_config import get_logger
from pathlib import Path
from multiprocessing import Pool
from typing import List, Dict, Any, Tuple
from datetime import datetime

from opensearch_sql.core import Task, Logger, DatabaseManager, StatisticsManager, PipelineManager
from opensearch_sql.pipeline import build_pipeline, validate_pipeline_nodes
from opensearch_sql.utils.results_collector import ResultsCollector
from opensearch_sql.utils.progress_tracker import ProgressTracker, SQLFormatter, ErrorFilter
from opensearch_sql.utils.task_result_formatter import TaskResultLogger


# Default values - will be overridden by args
DEFAULT_NUM_WORKERS = 3


logger = get_logger(__name__)

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
        
        # Initialize results collector
        self.results_collector = None
        
        # Get verbose mode from args (default to False)
        self.verbose = getattr(args, 'verbose', False)
        
        # Initialize progress tracker and formatters
        self.progress_tracker = None
        self.sql_formatter = SQLFormatter()
        self.error_filter = ErrorFilter()
        self.result_logger = TaskResultLogger()  # 任务结果始终详细显示
        
        # Setup logging
        self._setup_logging()
        
        logger.info(f"RunManager initialized with result directory: {self.result_directory}")

    def _setup_logging(self):
        """Setup logging configuration."""
        # Logging is now configured via loguru in main_standalone.py
        pass

    def get_result_directory(self) -> str:
        """
        Creates and returns a simplified result directory path.
        
        Returns:
            str: The path to the result directory.
        """
        # Simplified directory structure: results/dataset/YYYY-MM-DD_HH-MM-SS/
        dataset_name = Path(self.args.db_root_path).stem
        
        # Format timestamp as YYYY-MM-DD_HH-MM-SS for better readability
        timestamp_str = str(self.args.run_start_time)
        if len(timestamp_str) == 19 and '-' in timestamp_str[:10]:
            # Handle existing YYYY-MM-DD-HH-MM-SS format
            timestamp = timestamp_str.replace('-', '_', 1)  # Only replace first dash to get YYYY_MM-DD-HH-MM-SS
            timestamp = timestamp.replace('-', '_', 1)  # Replace second dash to get YYYY_MM_DD-HH-MM-SS
        else:
            # Fallback: use current timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Simple structure: results/Bird/2025-08-12_00-01-53/
        run_folder_path = Path(self.RESULT_ROOT_PATH) / dataset_name / timestamp
        
        run_folder_path.mkdir(parents=True, exist_ok=True)
        
        # Save configuration to a clearly named file
        config_file_path = run_folder_path / "run_config.json"
        with config_file_path.open('w') as file:
            json.dump(vars(self.args), file, indent=2)
        
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
                # Add original index to maintain order
                task.original_index = i
                self.tasks.append(task)
            except Exception as e:
                logger.error(f"Error creating task {i}: {e}")
                continue
        
        self.total_number_of_tasks = len(self.tasks)
        
        # Initialize results collector with the total number of tasks
        self.results_collector = ResultsCollector(
            result_directory=self.result_directory,
            dataset_size=self.total_number_of_tasks
        )
        
        # Initialize progress tracker with enhanced features
        # Check if ground truth is available by looking for SQL field in tasks
        has_ground_truth = any(hasattr(task, 'SQL') and task.SQL for task in self.tasks)
        self.progress_tracker = ProgressTracker(
            total_tasks=self.total_number_of_tasks,
            has_ground_truth=has_ground_truth
        )
        
        logger.info(f"Total number of tasks: {self.total_number_of_tasks}")

    def run_tasks(self):
        """Runs the tasks using a pool of workers or sequentially."""
        # Get concurrency settings from args
        enable_multiprocessing = getattr(self.args, 'enable_multiprocessing', False)
        num_workers = getattr(self.args, 'num_workers', DEFAULT_NUM_WORKERS)
        
        logger.info(f"Concurrency settings: multiprocessing={enable_multiprocessing}, workers={num_workers}")
        
        if enable_multiprocessing and num_workers > 1:
            logger.info(f"Running {self.total_number_of_tasks} tasks in parallel with {num_workers} workers")
            self._run_tasks_parallel(num_workers)
        else:
            logger.info(f"Running {self.total_number_of_tasks} tasks sequentially")
            self._run_tasks_sequential()

    def _run_tasks_parallel(self, num_workers):
        """Run tasks in parallel using multiprocessing."""
        try:
            import concurrent.futures
            with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
                # Submit all tasks with their indices using task dictionaries instead of Task objects
                futures = []
                for i, task in enumerate(self.tasks):
                    # Convert Task object to dictionary to avoid pickling issues
                    task_dict = task.to_dict()
                    task_dict['original_index'] = getattr(task, 'original_index', task.question_id)
                    
                    # Convert args to dictionary to avoid pickling issues with complex objects
                    args_dict = vars(self.args).copy()
                    
                    future = executor.submit(self._worker_process, task_dict, args_dict, self.result_directory)
                    futures.append((future, task, i))
                
                # Process results as they complete
                for future, task, task_index in futures:
                    try:
                        result = future.result()
                        self.task_done(result, task)
                    except Exception as e:
                        logger.error(f"Error processing parallel task: {e}")
                        original_index = getattr(task, 'original_index', task.question_id)
                        self.task_done((None, task.db_id, task.question_id, original_index, 0.0), task)
                        
        except Exception as e:
            logger.error(f"Error in parallel execution: {e}")
            # Fallback to sequential execution
            self._run_tasks_sequential()

    def _run_tasks_sequential(self):
        """Run tasks sequentially."""
        for task in self.tasks:
            try:
                result = self.worker(task)
                self.task_done(result, task)
            except Exception as e:
                logger.error(f"Error processing task {task.question_id}: {e}")
                original_index = getattr(task, 'original_index', task.question_id)
                self.task_done((None, task.db_id, task.question_id, original_index, 0.0), task)

    @staticmethod
    def _worker_process(task_dict: Dict[str, Any], args_dict: Dict[str, Any], result_directory: str) -> Tuple[Any, str, int, int, float]:
        """
        Static worker function that can be pickled for multiprocessing.
        
        Args:
            task_dict (Dict): Task data as dictionary
            args_dict (Dict): Arguments as dictionary
            result_directory (str): Result directory path
        
        Returns:
            tuple: The state of the task processing, task identifiers, original index, and processing time.
        """
        # Import here to avoid issues with multiprocessing
        import json
        from datetime import datetime
        from opensearch_sql.core import Task, Logger, DatabaseManager, PipelineManager
        from opensearch_sql.pipeline import build_pipeline, validate_pipeline_nodes
        from opensearch_sql.utils.loguru_config import get_logger
        
        worker_logger = get_logger(__name__)
        
        # Recreate Task object from dictionary
        original_index = task_dict.pop('original_index', task_dict.get('question_id', 0))
        task = Task(task_dict)
        task.original_index = original_index
        
        start_time = datetime.now()
        
        try:
            # Initialize components for this task
            database_manager = DatabaseManager(
                db_mode=args_dict['data_mode'], 
                db_root_path=args_dict['db_root_path'], 
                db_id=task.db_id
            )
            
            logger = Logger(
                db_id=task.db_id, 
                question_id=task.question_id, 
                result_directory=result_directory
            )
            logger._set_log_level(args_dict.get('log_level', 'INFO'))
            logger.log(f"Processing task: {task.db_id} {task.question_id}", "info")
            
            # Initialize pipeline manager
            pipeline_setup = json.loads(args_dict['pipeline_setup'])
            pipeline_manager = PipelineManager(pipeline_setup)
            
            # No checkpoint loading in multiprocessing to keep it simple
            execution_history = []
            
            # Build and run pipeline
            initial_state = {
                "keys": {
                    "task": task, 
                    "execution_history": execution_history
                }
            }
            
            worker_logger.info("Building pipeline...")
            
            # Validate pipeline nodes first
            if not validate_pipeline_nodes(args_dict['pipeline_nodes']):
                raise ValueError(f"Invalid pipeline nodes: {args_dict['pipeline_nodes']}")
            
            app = build_pipeline(args_dict['pipeline_nodes'])
            worker_logger.info("Pipeline built successfully.")

            # Determine the final node
            if hasattr(app, 'nodes') and app.nodes:
                last_node_key = list(app.nodes.keys())[-1]
                worker_logger.debug(f'Final node: {last_node_key}')
            else:
                last_node_key = '__end__'  # Default fallback

            # Execute pipeline
            final_state = None
            for state in app.stream(initial_state):
                final_state = state
                continue

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            if final_state and last_node_key in final_state:
                return final_state[last_node_key], task.db_id, task.question_id, original_index, processing_time
            else:
                worker_logger.warning(f"No final state found for task {task.question_id}")
                return final_state, task.db_id, task.question_id, original_index, processing_time
                
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            worker_logger.error(f"Worker error for task {task.question_id}: {e}")
            return None, task.db_id, task.question_id, original_index, processing_time

    def worker(self, task: Task) -> Tuple[Any, str, int, int, float]:
        """
        Worker function to process a single task.
        
        Args:
            task (Task): The task to be processed.
        
        Returns:
            tuple: The state of the task processing, task identifiers, original index, and processing time.
        """
        start_time = datetime.now()
        original_index = getattr(task, 'original_index', task.question_id)
        
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
            
            logger.info("Building pipeline...")
            
            # Validate pipeline nodes first
            if not validate_pipeline_nodes(self.args.pipeline_nodes):
                raise ValueError(f"Invalid pipeline nodes: {self.args.pipeline_nodes}")
            
            app = build_pipeline(self.args.pipeline_nodes)
            logger.info("Pipeline built successfully.")

            # Determine the final node
            if hasattr(app, 'nodes') and app.nodes:
                last_node_key = list(app.nodes.keys())[-1]
                logger.debug(f'Final node: {last_node_key}')
            else:
                last_node_key = '__end__'  # Default fallback

            # Execute pipeline
            final_state = None
            for state in app.stream(initial_state):
                final_state = state
                continue

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            if final_state and last_node_key in final_state:
                return final_state[last_node_key], task.db_id, task.question_id, original_index, processing_time
            else:
                logger.warning(f"No final state found for task {task.question_id}")
                return final_state, task.db_id, task.question_id, original_index, processing_time
                
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.log(f"Error processing task: {task.db_id} {task.question_id}\n{e}", "error")
            logger.error(f"Worker error for task {task.question_id}: {e}")
            return None, task.db_id, task.question_id, original_index, processing_time

    def task_done(self, log: Tuple[Any, str, int, int, float], task: Task):
        """
        Callback function when a task is done.
        
        Args:
            log (tuple): The log information of the task processing.
            task (Task): The original task object.
        """
        state, db_id, question_id, original_index, processing_time = log
        
        # Extract task results for detailed display
        generated_sql = ""
        execution_status = "unknown"
        evaluation_results = None
        error_message = ""
        
        if state is not None and "keys" in state and "execution_history" in state["keys"]:
            execution_history = state["keys"]["execution_history"]
            
            # Extract SQL
            for step in reversed(execution_history):
                if not isinstance(step, dict):
                    continue
                if step.get("node_type") == "vote" and "SQL" in step:
                    generated_sql = step["SQL"]
                    break
                elif step.get("node_type") == "align_correct" and "SQL" in step:
                    generated_sql = step["SQL"]
                    break
                elif step.get("node_type") == "candidate_generate" and "SQL" in step:
                    sql_candidates = step["SQL"]
                    if isinstance(sql_candidates, list) and sql_candidates:
                        generated_sql = sql_candidates[0]
                    elif isinstance(sql_candidates, str):
                        generated_sql = sql_candidates
                    break
                    
            # Extract evaluation results
            for step in reversed(execution_history):
                if not isinstance(step, dict):
                    continue
                if step.get("node_type") == "evaluation":
                    evaluation_results = {k: v for k, v in step.items() if k not in ["node_type", "status"]}
                    if step.get("exec_res") == 1:
                        execution_status = "success"
                    else:
                        execution_status = "failed"
                        error_message = step.get("error", "")
                    break
        
        # Display detailed task result
        task_id = f"{db_id}#{question_id}"
        ground_truth_sql = getattr(task, 'SQL', "")
        question_text = getattr(task, 'question', f"Question {question_id}")
        
        self.result_logger.log_task_result(
            task_id=task_id,
            question=question_text,
            generated_sql=generated_sql,
            ground_truth_sql=ground_truth_sql,
            execution_status=execution_status,
            evaluation_results=evaluation_results,
            processing_time=processing_time,
            error_message=error_message
        )
        
        # Collect result data
        self._collect_task_result(state, task, original_index, processing_time)
        
        if state is None:
            self.processed_tasks += 1
            return

        # Update statistics if we have valid state and execution history
        if state is not None and "keys" in state and "execution_history" in state["keys"]:
            try:
                execution_history = state["keys"]['execution_history']
                
                # Update statistics from evaluation result
                if execution_history:
                    evaluation_result = execution_history[-1]
                    # Check if evaluation_result is a dictionary before calling .get()
                    if isinstance(evaluation_result, dict) and evaluation_result.get("node_type") == "evaluation":
                        for evaluation_for, result in evaluation_result.items():
                            if evaluation_for in ['node_type', 'status']:
                                continue
                            self.statistics_manager.update_stats(db_id, question_id, evaluation_for, result)
                        self.statistics_manager.dump_statistics_to_file()
            
            except Exception as e:
                # Only log unexpected errors
                if not self.error_filter.is_expected_error(str(e)):
                    logger.error(f"Error processing task result for {question_id}: {e}")
        
        self.processed_tasks += 1
        
        # Update enhanced progress tracker
        if self.progress_tracker:
            # Extract more detailed information for progress tracking
            is_exact_match = False
            if evaluation_results and "exec_res" in evaluation_results:
                is_exact_match = (evaluation_results["exec_res"] == 1)
            elif evaluation_results and "execution_match" in evaluation_results:
                is_exact_match = evaluation_results["execution_match"]
                
            self.progress_tracker.update(
                task_id=task_id,
                generated_sql=generated_sql,
                execution_status=execution_status,
                is_exact_match=is_exact_match,
                error_message=error_message
            )
        
        # Save results periodically
        if self.processed_tasks % 10 == 0 or self.processed_tasks == self.total_number_of_tasks:
            self._save_intermediate_results()

    def _collect_task_result(self, state: Any, task: Task, original_index: int, processing_time: float):
        """
        Collect result data from a completed task.
        
        Args:
            state: Final state from pipeline execution
            task: Task object
            original_index: Original index in dataset
            processing_time: Time taken to process this task
        """
        if self.results_collector is None:
            return
            
        try:
            generated_sql = ""
            ground_truth_sql = getattr(task, 'SQL', "")
            execution_status = "unknown"
            evaluation_results = None
            error_message = ""
            
            if state is None:
                execution_status = "failed"
                error_message = "Pipeline execution failed"
            else:
                # Extract generated SQL from execution history
                if "keys" in state and "execution_history" in state["keys"]:
                    execution_history = state["keys"]["execution_history"]
                    
                    # Look for the final SQL in voting node result
                    for step in reversed(execution_history):
                        if not isinstance(step, dict):
                            continue
                        if step.get("node_type") == "vote" and "SQL" in step:
                            generated_sql = step["SQL"]
                            break
                        elif step.get("node_type") == "align_correct" and "SQL" in step:
                            generated_sql = step["SQL"]
                            break
                        elif step.get("node_type") == "candidate_generate" and "SQL" in step:
                            sql_candidates = step["SQL"]
                            if isinstance(sql_candidates, list) and sql_candidates:
                                generated_sql = sql_candidates[0]
                            elif isinstance(sql_candidates, str):
                                generated_sql = sql_candidates
                            break
                    
                    # Extract evaluation results
                    for step in reversed(execution_history):
                        if not isinstance(step, dict):
                            continue
                        if step.get("node_type") == "evaluation":
                            evaluation_results = {k: v for k, v in step.items() if k != "node_type"}
                            if step.get("exec_res") == 1:
                                execution_status = "success"
                            else:
                                execution_status = "failed"
                            break
            
            # Add to results collector
            self.results_collector.add_result(
                original_index=original_index,
                question=task.question,
                evidence=getattr(task, 'evidence', ""),
                db_id=task.db_id,
                question_id=str(task.question_id),
                generated_sql=generated_sql,
                ground_truth_sql=ground_truth_sql,
                execution_status=execution_status,
                evaluation_results=evaluation_results,
                processing_time=processing_time,
                error_message=error_message
            )
            
        except Exception as e:
            logger.error(f"Error collecting task result: {e}")

    def _save_intermediate_results(self):
        """Save intermediate results to prevent data loss."""
        if self.results_collector is None:
            return
            
        try:
            self.results_collector.save_simple_format("results_temp.json")
            logger.debug(f"Saved intermediate results ({self.processed_tasks}/{self.total_number_of_tasks})")
        except Exception as e:
            logger.warning(f"Could not save intermediate results: {e}")

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
            logger.warning("Checkpoint enabled but no checkpoint directory provided")
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
                    logger.info(f"Loaded checkpoint for {question_id}_{db_id}: {len(execution_history)} steps")
                    logger.debug(f"Checkpoint ends at: {execution_history[-1]['node_type']}")
                    
            except Exception as e:
                logger.warning(f"Error loading checkpoint {checkpoint_file}: {e}")
        else:
            logger.debug(f"Checkpoint file not found: {checkpoint_file}")
            
        return execution_history

    def save_final_results(self):
        """
        Save final results in multiple formats.
        
        Returns:
            Dict[str, str]: Paths to saved files
        """
        if self.results_collector is None:
            logger.warning("No results collector available")
            return {}
            
        saved_files = {}
        
        try:
            # Save main results (simple format is the primary output)
            main_path = self.results_collector.save_simple_format("results.json")
            saved_files["results"] = main_path
            
            # Save detailed results
            detailed_path = self.results_collector.save_results("results_detailed.json")
            saved_files["detailed"] = detailed_path
            
            # Save CSV format
            csv_path = self.results_collector.save_csv_format("results.csv")
            if csv_path:
                saved_files["csv"] = csv_path
            
            # Log summary statistics
            stats = self.results_collector.get_summary_stats()
            logger.info(f"Final results summary: {stats}")
            
            return saved_files
            
        except Exception as e:
            logger.error(f"Error saving final results: {e}")
            return {}

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
                    logger.warning(f"Error processing result file {file_path}: {e}")
                    continue
            
            # Write SQL files for each node type
            for node_type, sql_dict in sqls.items():
                output_file = Path(self.result_directory) / f"-{node_type}.json"
                with output_file.open('w') as f:
                    json.dump(sql_dict, f, indent=4, ensure_ascii=False)
                    
                logger.info(f"Generated SQL file: {output_file} ({len(sql_dict)} queries)")
                
        except Exception as e:
            logger.error(f"Error generating SQL files: {e}")

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
            # Display final progress summary
            if self.progress_tracker:
                self.progress_tracker.finish()
            
            # Print final statistics
            self.statistics_manager.print_summary()
            
            # Generate final SQL files
            self.generate_sql_files()
            
            logger.info("RunManager cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()