import logging
from typing import Any, Dict
from pathlib import Path
from sentence_transformers import SentenceTransformer
from pipeline.utils import node_decorator
from pipeline.pipeline_manager import PipelineManager
from runner.database_manager import DatabaseManager
from llm.model import model_chose
from llm.db_conclusion import *
import json
from loguru import logger

@node_decorator(check_schema_status=False)
def generate_db_schema(task: Any, execution_history: Dict[str, Any]) -> Dict[str, Any]:
    config,node_name=PipelineManager().get_model_para()
    paths=DatabaseManager()
    # 初始化模型
    logger.debug(f"Initializing model with config: {config}")
    bert_model = SentenceTransformer(config["bert_model"], device=config["device"])

    # 读取参数
    db_json_dir = paths.db_json
    tables_info_dir = paths.db_tables
    sqllite_dir=paths.db_path
    db_dir=paths.db_directory_path
    chat_model = model_chose(node_name,config["engine"])  # deepseek qwen-max gpt qwen-max-longcontext
    ext_file = Path(paths.db_root_path)/"db_schema.json"

    # 读取已有数据
    if os.path.exists(ext_file):
        with open(ext_file, 'r') as f:
            data = json.load(f)#保存格式错了
    else:
        data ={}

    # 获取数据库信息代理
    DB_info_agent = db_agent_string(chat_model)
    
    # 检查是否已处理该数据库
    db = task.db_id
    existing_entry = data.get(db)
    logger.debug(f"Checking existing entry for database {db}: {existing_entry}")

    if existing_entry:
        all_info,db_col = existing_entry
    else:
        logger.debug(f"Generating schema for database {db}...")
        all_info, db_col = DB_info_agent.get_allinfo(db_json_dir, db,sqllite_dir,db_dir,tables_info_dir, bert_model)
        logger.debug(f"Generated all_info: {all_info}")
        logger.info(f"Generated db_col: {db_col}")
        data[db]=[all_info,db_col]
        logger.debug(f"Saving new schema for database {db} to {ext_file}")
        with open(ext_file, 'w') as f:
            json.dump(data, f, indent=4,ensure_ascii=False)
        logger.debug(f"Database schema saved to {ext_file}")
    
    response = {
        "db_list": all_info,
        "db_col_dic": db_col
    }
    return response




