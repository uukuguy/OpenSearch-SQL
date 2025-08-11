"""
Standalone DatabaseManager implementation for OpenSearch-SQL pipeline.
"""
import os
import sqlite3
import pickle
import random
import logging
from threading import Lock
from pathlib import Path
from typing import Callable, Dict, List, Any, Union
from func_timeout import func_timeout, FunctionTimedOut


class DatabaseManager:
    """
    A singleton class to manage database operations including schema generation, 
    querying databases, and managing column profiles.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls, db_mode=None, db_root_path=None, db_id=None):
        if (db_mode is not None) and (db_root_path is not None) and (db_id is not None):
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
                    cls._instance._init(db_mode, db_root_path, db_id)
                elif cls._instance.db_id != db_id:
                    cls._instance._init(db_mode, db_root_path, db_id)
                return cls._instance
        else:
            if cls._instance is None:
                raise ValueError("DatabaseManager instance has not been initialized yet.")
            return cls._instance

    def _init(self, db_mode: str, db_root_path: str, db_id: str):
        """
        Initializes the DatabaseManager instance.

        Args:
            db_mode (str): The mode of the database (e.g., 'dev', 'train').
            db_root_path (str): Root path to the database directory.
            db_id (str): The database identifier.
        """
        self.db_mode = db_mode
        self.db_root_path = db_root_path
        self.db_id = db_id
        self._set_paths()

    def _set_paths(self):
        """Sets the paths for the database files and directories."""
        # Update path structure to match the actual Bird dataset structure
        if self.db_mode == "dev":
            self.db_path = Path(self.db_root_path) / "dev_20240627" / "dev_databases" / self.db_id / f"{self.db_id}.sqlite"
            self.db_directory_path = Path(self.db_root_path) / "dev_20240627" / "dev_databases" / self.db_id
        else:
            self.db_path = Path(self.db_root_path) / f"{self.db_mode}" / f"{self.db_mode}_databases" / self.db_id / f"{self.db_id}.sqlite"
            self.db_directory_path = Path(self.db_root_path) / f"{self.db_mode}" / f"{self.db_mode}_databases" / self.db_id
        
        self.db_json = Path(self.db_root_path) / "data_preprocess" / f"{self.db_mode}.json"
        self.db_tables = Path(self.db_root_path) / "data_preprocess" / "tables.json"
        self.db_fewshot_path = Path(self.db_root_path) / "fewshot" / "questions.json"
        self.db_fewshot2_path = Path(self.db_root_path) / "correct_fewshot2.json"
        self.emb_dir = Path(self.db_root_path) / "emb"

    def get_db_schema(self, db_path: str = None) -> str:
        """
        Extracts the database schema.
        
        Args:
            db_path (str): Optional database path. Uses instance db_path if not provided.
            
        Returns:
            str: The database schema as a formatted string.
        """
        if db_path is None:
            db_path = str(self.db_path)
        
        schema_info = []
        
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Get all table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                for table in tables:
                    table_name = table[0]
                    if table_name == 'sqlite_sequence':
                        continue
                        
                    schema_info.append(f"Table: {table_name}")
                    
                    # Get column information
                    cursor.execute(f"PRAGMA table_info({table_name});")
                    columns = cursor.fetchall()
                    
                    for col in columns:
                        col_name = col[1]
                        col_type = col[2]
                        is_primary = "PRIMARY KEY" if col[5] else ""
                        not_null = "NOT NULL" if col[3] else ""
                        default = f"DEFAULT {col[4]}" if col[4] is not None else ""
                        
                        col_desc = f"  - {col_name} {col_type} {is_primary} {not_null} {default}".strip()
                        schema_info.append(col_desc)
                    
                    # Get foreign key information
                    cursor.execute(f"PRAGMA foreign_key_list({table_name});")
                    foreign_keys = cursor.fetchall()
                    
                    if foreign_keys:
                        schema_info.append("  Foreign Keys:")
                        for fk in foreign_keys:
                            schema_info.append(f"    - {fk[3]} -> {fk[2]}.{fk[4]}")
                    
                    schema_info.append("")  # Empty line between tables
                
                return "\n".join(schema_info)
                
        except Exception as e:
            logging.error(f"Error extracting schema: {e}")
            return f"Error: Could not extract schema from {db_path}"
    
    def _clean_sql(self, sql: str) -> str:
        """
        Cleans the SQL query by removing unwanted characters and whitespace.
        
        Args:
            sql (str): The SQL query string.
            
        Returns:
            str: The cleaned SQL query string.
        """
        return sql.replace('\n', ' ').replace('"', "'").strip("`.")

    def execute_sql(self, sql: str, fetch: Union[str, int] = "all") -> Any:
        """
        Executes an SQL query on the database and fetches results.
        
        Args:
            sql (str): The SQL query to execute.
            fetch (Union[str, int]): How to fetch the results. Options are "all", "one", "random", or an integer.
            
        Returns:
            Any: The fetched results based on the fetch argument.
        
        Raises:
            Exception: If an error occurs during SQL execution.
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                if fetch == "all":
                    return cursor.fetchall()
                elif fetch == "one":
                    return cursor.fetchone()
                elif fetch == "random":
                    samples = cursor.fetchmany(10)
                    return random.choice(samples) if samples else []
                elif isinstance(fetch, int):
                    return cursor.fetchmany(fetch)
                else:
                    raise ValueError("Invalid fetch argument. Must be 'all', 'one', 'random', or an integer.")
        except Exception as e:
            logging.error(f"Error in execute_sql: {e}\nSQL: {sql}")
            raise e

    def _compare_sqls_outcomes(self, predicted_sql: str, ground_truth_sql: str) -> int:
        """
        Compares the outcomes of two SQL queries to check for equivalence.
        
        Args:
            predicted_sql (str): The predicted SQL query.
            ground_truth_sql (str): The ground truth SQL query.
            
        Returns:
            int: 1 if the outcomes are equivalent, 0 otherwise.
        
        Raises:
            Exception: If an error occurs during SQL execution.
        """
        try:
            predicted_res = self.execute_sql(predicted_sql)
            ground_truth_res = self.execute_sql(ground_truth_sql)
            return int(set(predicted_res) == set(ground_truth_res))
        except Exception as e:
            logging.critical(f"Error comparing SQL outcomes: {e}")
            raise e

    def compare_sqls(self, predicted_sql: str, ground_truth_sql: str, meta_time_out: int = 30) -> Dict[str, Union[int, str]]:
        """
        Compares predicted SQL with ground truth SQL within a timeout.
        
        Args:
            predicted_sql (str): The predicted SQL query.
            ground_truth_sql (str): The ground truth SQL query.
            meta_time_out (int): The timeout for the comparison.
            
        Returns:
            dict: A dictionary with the comparison result and any error message.
        """
        try:
            res = func_timeout(meta_time_out, self._compare_sqls_outcomes, args=(predicted_sql, ground_truth_sql))
            error = "incorrect answer" if res == 0 else "--"
        except FunctionTimedOut:
            logging.warning("Comparison timed out.")
            error = "timeout"
            res = 0
        except Exception as e:
            logging.error(f"Error in compare_sqls: {e}")
            error = str(e)
            res = 0
        return {'exec_res': res, 'exec_err': error}

    def validate_sql_query(self, sql: str, max_returned_rows: int = 30) -> Dict[str, Union[str, Any]]:
        """
        Validates an SQL query by executing it and returning the result.
        
        Args:
            sql (str): The SQL query to validate.
            max_returned_rows (int): The maximum number of rows to return.
            
        Returns:
            dict: A dictionary with the SQL query, result, and status.
        """
        try:
            result = self.execute_sql(sql, fetch=max_returned_rows)
            return {"SQL": sql, "RESULT": result, "STATUS": "OK"}
        except Exception as e:
            logging.error(f"Error in validate_sql_query: {e}")
            return {"SQL": sql, "RESULT": str(e), "STATUS": "ERROR"}

    def aggregate_sqls(self, sqls: List[str]) -> str:
        """
        Aggregates multiple SQL queries by validating them and clustering based on result sets.
        
        Args:
            sqls (List[str]): A list of SQL queries to aggregate.
            
        Returns:
            str: The shortest SQL query from the largest cluster of equivalent queries.
        """
        results = [self.validate_sql_query(sql) for sql in sqls]
        clusters = {}

        # Group queries by unique result sets
        for result in results:
            if result['STATUS'] == 'OK':
                # Using a frozenset as the key to handle unhashable types like lists
                key = frozenset(tuple(row) for row in result['RESULT'])
                if key in clusters:
                    clusters[key].append(result['SQL'])
                else:
                    clusters[key] = [result['SQL']]
        
        if clusters:
            # Find the largest cluster
            largest_cluster = max(clusters.values(), key=len, default=[])
            # Select the shortest SQL query from the largest cluster
            if largest_cluster:
                return min(largest_cluster, key=len)
        
        logging.warning("No valid SQL clusters found. Returning the first SQL query.")
        return sqls[0] if sqls else ""

    def get_table_names(self) -> List[str]:
        """
        Gets all table names from the database.
        
        Returns:
            List[str]: List of table names.
        """
        try:
            result = self.execute_sql("SELECT name FROM sqlite_master WHERE type='table';")
            return [row[0] for row in result]
        except Exception as e:
            logging.error(f"Error getting table names: {e}")
            return []

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Gets the schema of a specific table.
        
        Args:
            table_name (str): Name of the table.
            
        Returns:
            List[Dict[str, Any]]: Schema information for the table.
        """
        try:
            result = self.execute_sql(f"PRAGMA table_info({table_name});")
            return [
                {
                    "cid": row[0],
                    "name": row[1],
                    "type": row[2],
                    "notnull": row[3],
                    "dflt_value": row[4],
                    "pk": row[5]
                }
                for row in result
            ]
        except Exception as e:
            logging.error(f"Error getting table schema for {table_name}: {e}")
            return []

    def get_database_schema(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Gets the complete database schema.
        
        Returns:
            Dict[str, List[Dict[str, Any]]]: Complete database schema.
        """
        schema = {}
        table_names = self.get_table_names()
        for table_name in table_names:
            schema[table_name] = self.get_table_schema(table_name)
        return schema

    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Any]:
        """
        Gets sample data from a table.
        
        Args:
            table_name (str): Name of the table.
            limit (int): Number of rows to sample.
            
        Returns:
            List[Any]: Sample data from the table.
        """
        try:
            return self.execute_sql(f"SELECT * FROM {table_name} LIMIT {limit};")
        except Exception as e:
            logging.error(f"Error getting sample data from {table_name}: {e}")
            return []

    @staticmethod
    def with_db_path(func: Callable):
        """
        Decorator to inject db_path as the first argument to the function.
        """
        def wrapper(self, *args, **kwargs):
            return func(str(self.db_path), *args, **kwargs)
        return wrapper

    @classmethod
    def add_methods_to_class(cls, funcs: List[Callable]):
        """
        Adds methods to the class with db_path automatically provided.

        Args:
            funcs (List[Callable]): List of functions to be added as methods.
        """
        for func in funcs:
            method = cls.with_db_path(func)
            setattr(cls, func.__name__, method)

    def __str__(self) -> str:
        """String representation of the DatabaseManager."""
        return f"DatabaseManager(db_id={self.db_id}, db_mode={self.db_mode})"

    def __repr__(self) -> str:
        """Detailed representation of the DatabaseManager."""
        return self.__str__()