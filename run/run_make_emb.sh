db_root_directory=Bird #root directory
dev_database=dev/dev_databases #dev database directory
bert_model="/opt/local/llm_models/embeddings/BAAI/bge-m3"

python -u src/database_process/make_emb.py \
    --db_root_directory "${db_root_directory}" \
    --dev_database "${dev_database}" \
    --bert_model "${bert_model}"
