"""
Optimized column retrieval pipeline node using embedding service.
Demonstrates how to integrate the new architecture.
"""

from ..utils.loguru_config import get_logger
import json
from typing import Any, Dict, List
from pathlib import Path

# Import from original codebase
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from pipeline.utils import node_decorator, get_last_node_result
from pipeline.pipeline_manager import PipelineManager
from runner.database_manager import DatabaseManager
from llm.model import model_chose
from llm.db_conclusion import find_foreign_keys_MYSQL_like
from llm.prompts import db_check_prompts
from runner.column_retrieve import ColumnRetriever
from runner.column_update import ColumnUpdater
from database_process.make_emb import load_emb

# Import optimized services
from ..services.embedding_service import get_embedding_service
from ..services.model_pool import initialize_model_pool

logger = get_logger(__name__)


class OptimizedDES:
    """Optimized DES using embedding service instead of loading model."""
    
    def __init__(self, embedding_service, DB_emb, col_values):
        self.embedding_service = embedding_service
        self.DB_emb = DB_emb
        self.col_values = col_values
    
    def get_examples(self, target: List[str], topk: int = 3):
        """Get top-k similar examples using embedding service."""
        # Use embedding service instead of model.encode
        target_embeddings = self.embedding_service.encode(target)
        
        # Rest of the logic remains similar
        all_pairs = []
        for key in self.DB_emb:
            embs = self.DB_emb[key]
            
            # Calculate distances
            import numpy as np
            from sklearn.metrics.pairwise import euclidean_distances
            
            distances = np.squeeze(euclidean_distances(target_embeddings, embs)).tolist()
            distances = [distances] if np.isscalar(distances) else distances
            
            pairs = [
                (distance, index, key)
                for distance, index in zip(distances, range(len(distances)))
            ]
            
            pairs_sorted = sorted(pairs, key=lambda x: x[0])
            all_pairs.extend(pairs_sorted[:topk])
            all_pairs.sort(key=lambda x: x[0])
        
        return all_pairs[:topk]
    
    def get_key_col_des(self, cols, values, shold=0.65, debug=False, topk=7):
        """Get key column descriptions with optimized embedding lookups."""
        des = []
        value_cols = []
        
        # Batch encode all values at once for efficiency
        all_values = [v.strip(" '\"") for v in values if v.strip(" '\"")]
        if not all_values:
            return cols, des
        
        # Use embedding service for batch encoding
        value_embeddings = self.embedding_service.encode(all_values)
        
        # Process each value
        for value, value_emb in zip(all_values, value_embeddings):
            if len(value) < 3:
                continue
                
            # Find similar columns
            col_matches = self._find_similar_columns(value_emb, value, topk, shold)
            
            for match in col_matches:
                tab, col = match['table_col'].split('.')
                col_formatted = f"{tab}.`{col}`" if ' ' in col else f"{tab}.{col}"
                val_ans = match['value'].replace("'", "''")
                des.append((col_formatted, val_ans))
                value_cols.append(col_formatted)
        
        cols = cols.union(set(value_cols))
        return cols, des
    
    def _find_similar_columns(self, value_emb, value_text, topk, threshold):
        """Find similar columns based on embedding similarity."""
        matches = []
        
        for table_col, col_embs in self.DB_emb.items():
            if 'sqlite_sequence' in table_col:
                continue
                
            # Calculate similarities
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity
            
            similarities = cosine_similarity(value_emb.reshape(1, -1), col_embs)[0]
            
            # Get top matches
            top_indices = np.argsort(similarities)[-topk:][::-1]
            
            for idx in top_indices:
                if similarities[idx] > threshold:
                    matches.append({
                        'table_col': table_col,
                        'value': self.col_values[table_col][idx],
                        'similarity': similarities[idx]
                    })
        
        # Sort by similarity
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        return matches[:topk]


@node_decorator(check_schema_status=False)
def column_retrieve_optimized(task: Any, execution_history: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optimized version of column_retrieve_and_other_info using embedding service.
    """
    config, node_name = PipelineManager().get_model_para()
    paths = DatabaseManager()
    emb_dir = paths.emb_dir
    tables_info_dir = paths.db_tables
    
    # Get embedding service instead of loading model
    embedding_service = get_embedding_service(
        model_name=config["bert_model"],
        cache_enabled=True,
        batch_size=32
    )
    
    # Get chat model for LLM operations
    chat_model = model_chose(node_name, config["engine"])
    
    # Get data from previous nodes
    all_db_col = get_last_node_result(execution_history, "generate_db_schema")["db_col_dic"]
    origin_col = get_last_node_result(execution_history, "extract_query_noun")["col"]
    values = get_last_node_result(execution_history, "extract_query_noun")["values"]
    
    db = task.db_id
    
    # Load embeddings (could be cached in service in production)
    logger.info(f"Loading embeddings for database: {db}")
    DB_emb, col_values = load_emb(db, emb_dir)
    
    db_col = {x: all_db_col[x][0] for x in all_db_col}
    db_keys_col = all_db_col.keys()
    
    # Use embedding service for column retrieval
    logger.info("Performing column retrieval with embedding service")
    col_retriever = OptimizedColumnRetriever(embedding_service, tables_info_dir)
    col_retrieve = col_retriever.get_col_retrieve(task.question, db, db_keys_col)
    
    # Get foreign keys
    foreign_keys, foreign_set = find_foreign_keys_MYSQL_like(tables_info_dir, db)
    
    # Update columns
    cols = ColumnUpdater(db_col).col_pre_update(origin_col, col_retrieve, foreign_set)
    
    # Use optimized DES with embedding service
    des = OptimizedDES(embedding_service, DB_emb, col_values)
    cols_select, L_values = des.get_key_col_des(
        cols,
        values,
        debug=False,
        topk=config.get('top_k', 7),
        shold=0.65
    )
    
    column = ColumnUpdater(db_col).col_suffix(cols_select)
    
    # Get query order
    count = 0
    q_order = ""
    while count < 3:
        try:
            q_order = query_order(
                task.raw_question,
                chat_model,
                db_check_prompts().select_prompt,
                temperature=config.get('temperature', 0.7)
            )
            break
        except:
            count += 1
    
    # Log statistics
    stats = embedding_service.get_stats()
    logger.info(f"Embedding service stats: {stats}")
    
    response = {
        "L_values": L_values,
        "column": column,
        "foreign_keys": foreign_keys,
        "foreign_set": foreign_set,
        "q_order": q_order,
        "embedding_stats": stats  # Include stats for monitoring
    }
    
    return response


class OptimizedColumnRetriever:
    """Optimized column retriever using embedding service."""
    
    def __init__(self, embedding_service, tables_info_dir):
        self.embedding_service = embedding_service
        self.tables_info_dir = Path(tables_info_dir)
    
    def get_col_retrieve(self, question: str, db: str, db_cols: List[str]) -> List[str]:
        """Retrieve relevant columns using embedding similarity."""
        # Encode question
        question_emb = self.embedding_service.encode(question)
        
        # Encode all columns (with caching)
        col_embeddings = self.embedding_service.encode(list(db_cols))
        
        # Calculate similarities
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        
        similarities = cosine_similarity(
            question_emb.reshape(1, -1),
            col_embeddings
        )[0]
        
        # Get top columns
        top_k = min(20, len(db_cols))
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        relevant_cols = [list(db_cols)[i] for i in top_indices if similarities[i] > 0.3]
        
        return relevant_cols


def query_order(question, chat_model, select_prompt, temperature):
    """Extract query order from question."""
    import re
    
    prompt = select_prompt.format(question=question)
    ans = chat_model.get_ans(prompt, temperature=temperature)
    ans = re.sub("```json|```", "", ans)
    
    try:
        select_json = json.loads(ans)
        res, judge = json_ext(select_json)
        return res
    except:
        return []


def json_ext(jsonf):
    """Extract information from JSON response."""
    ans = []
    judge = False
    
    for x in jsonf:
        if x["Type"] == "QIC":
            Q = x["Extract"]["Q"].lower()
            if Q in ["how many", "how much", "which", "how often"]:
                for item in x["Extract"]["I"]:
                    ans.append(x["Extract"]["Q"] + " " + item)
            elif Q in ["when", "who", "where"]:
                ans.append(x["Extract"]["Q"])
            else:
                ans.extend(x["Extract"]["I"])
        elif x["Type"] == "JC":
            ans.append(x["Extract"]["J"])
            judge = True
    
    return ans, judge