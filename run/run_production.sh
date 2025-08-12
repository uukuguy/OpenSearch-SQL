#!/bin/bash

# OpenSearch-SQL Production Pipeline Runner
# This is the MAIN script you should use for production workloads
# Combines full functionality with complete independence

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}OpenSearch-SQL Production Pipeline${NC}"
echo -e "${GREEN}(Complete Independent Implementation)${NC}"
echo -e "${GREEN}============================================${NC}"

# Configuration (same as original but with sensible defaults)
data_mode=${DATA_MODE:-'dev'} # Options: 'dev', 'train' 
db_root_path=${DB_ROOT_PATH:-'Bird'}
start=${START:-0}
end=${END:-10}  # Default to 10 samples for demo, use -1 for all data

# Pipeline configuration - COMPLETE 8-node pipeline
pipeline_nodes=${PIPELINE_NODES:-'generate_db_schema+extract_col_value+extract_query_noun+column_retrieve_and_other_info+candidate_generate+align_correct+vote+evaluation'}

# Model configuration
USE_REAL_MODELS=${USE_REAL_MODELS:-false}  # Set to true for production
API_KEY=${OPENAI_API_KEY:-'your-api-key-here'}

# BERT model path
bert_model_path=${BERT_MODEL_PATH:-"/opt/local/llm_models/embeddings/BAAI/bge-m3"}

# 🚀 Performance optimization configuration
# Concurrency settings
NUM_WORKERS=${NUM_WORKERS:-3}              # Number of concurrent workers (default: 3)
POOL_SIZE=${POOL_SIZE:-2}                  # Model pool size (default: 2)
ENABLE_MULTIPROCESSING=${ENABLE_MULTIPROCESSING:-true}  # Enable multiprocessing
ENABLE_THREADING=${ENABLE_THREADING:-true} # Enable threading
ENABLE_ASYNC=${ENABLE_ASYNC:-false}        # Enable async processing (experimental)

# Cache settings  
ENABLE_CACHE=${ENABLE_CACHE:-true}         # Enable multi-level caching
CACHE_L1_SIZE=${CACHE_L1_SIZE:-1000}       # L1 memory cache size (default: 1000)
ENABLE_REDIS=${ENABLE_REDIS:-false}        # Enable Redis L2 cache (requires Redis server)
REDIS_HOST=${REDIS_HOST:-'localhost'}      # Redis host
REDIS_PORT=${REDIS_PORT:-6379}             # Redis port
REDIS_DB=${REDIS_DB:-0}                    # Redis database number

# Model management
PRELOAD_MODELS=${PRELOAD_MODELS:-true}     # Preload models to avoid reloading
MODEL_POOL_TIMEOUT=${MODEL_POOL_TIMEOUT:-30}  # Model pool timeout in seconds

if [ "$USE_REAL_MODELS" = true ]; then
    echo -e "${BLUE}Using real LLM models (requires API key)${NC}"
    engine="gpt-4o"
    if [ "$API_KEY" = "your-api-key-here" ]; then
        echo -e "${RED}Warning: Using real models but API key not set!${NC}"
        echo "Set OPENAI_API_KEY environment variable or USE_REAL_MODELS=false"
    fi
else
    echo -e "${BLUE}Using mock models (no API key required)${NC}"
    engine="mock"
fi

# Pipeline setup - Complete configuration for all 8 nodes
pipeline_setup="{
    \"generate_db_schema\": {
        \"engine\": \"$engine\",
        \"bert_model\": \"$bert_model_path\",
        \"device\": \"cpu\"
    },
    \"extract_col_value\": {
        \"engine\": \"$engine\",
        \"temperature\": 0.0
    },
    \"extract_query_noun\": {
        \"engine\": \"$engine\",
        \"temperature\": 0.0
    },
    \"column_retrieve_and_other_info\": {
        \"engine\": \"$engine\",
        \"bert_model\": \"$bert_model_path\",
        \"device\": \"cpu\",
        \"temperature\": 0.3,
        \"top_k\": 10
    },
    \"candidate_generate\": {
        \"engine\": \"$engine\",
        \"temperature\": 0.7,
        \"n\": 5,
        \"return_question\": \"True\",
        \"single\": \"False\"
    },
    \"align_correct\": {
        \"engine\": \"$engine\",
        \"n\": 5,
        \"bert_model\": \"$bert_model_path\",
        \"device\": \"cpu\",
        \"align_methods\": \"style_align+function_align+agent_align\"
    },
    \"vote\": {
        \"method\": \"simple\"
    },
    \"evaluation\": {
        \"method\": \"basic\"
    }
}"

# Logging
LOG_LEVEL=${LOG_LEVEL:-'INFO'}

# Display configuration
echo -e "${YELLOW}Configuration:${NC}"
echo "  Data mode: $data_mode"
echo "  Database path: $db_root_path"
echo "  Task range: $start to $end"
echo "  Pipeline: ALL 8 NODES (complete pipeline)"
echo "  Model type: $engine"
echo "  Log level: $LOG_LEVEL"
echo ""
echo -e "${YELLOW}Performance Optimization:${NC}"
echo "  Workers: $NUM_WORKERS (concurrent processing)"
echo "  Model pool: $POOL_SIZE (avoid reloading)"
echo "  Multiprocessing: $ENABLE_MULTIPROCESSING"
echo "  Threading: $ENABLE_THREADING"
echo "  Caching: $ENABLE_CACHE (L1 size: $CACHE_L1_SIZE)"
echo "  Redis cache: $ENABLE_REDIS"
if [ "$ENABLE_REDIS" = true ]; then
    echo "  Redis: $REDIS_HOST:$REDIS_PORT (DB: $REDIS_DB)"
fi
echo ""

# Validate environment
if [ ! -d "$db_root_path" ]; then
    echo -e "${RED}Warning: Database path '$db_root_path' not found${NC}"
    echo "The pipeline will use mock data for demonstration"
fi

# Export API key if using real models
if [ "$USE_REAL_MODELS" = true ]; then
    export OPENAI_API_KEY=$API_KEY
fi

echo -e "${GREEN}Starting production pipeline with complete independent implementation...${NC}"
echo "Features:"
echo "✅ Complete 8-node pipeline"
echo "✅ Fully independent implementation"
echo "✅ No dependencies on original src/"
echo "✅ Production-ready configuration"
echo ""

# Run the production pipeline with optimization settings
python -m opensearch_sql.main \
    --data_mode "$data_mode" \
    --db_root_path "$db_root_path" \
    --pipeline_nodes "$pipeline_nodes" \
    --pipeline_setup "$pipeline_setup" \
    --start "$start" \
    --end "$end" \
    --log_level "$LOG_LEVEL" \
    --num_workers "$NUM_WORKERS" \
    --pool_size "$POOL_SIZE" \
    --enable_multiprocessing "$ENABLE_MULTIPROCESSING" \
    --enable_threading "$ENABLE_THREADING" \
    --enable_async "$ENABLE_ASYNC" \
    --enable_cache "$ENABLE_CACHE" \
    --cache_l1_size "$CACHE_L1_SIZE" \
    --enable_redis "$ENABLE_REDIS" \
    --redis_host "$REDIS_HOST" \
    --redis_port "$REDIS_PORT" \
    --redis_db "$REDIS_DB" \
    --preload_models "$PRELOAD_MODELS" \
    --model_pool_timeout "$MODEL_POOL_TIMEOUT"

# Check exit status
exit_code=$?
echo ""
if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}Production pipeline completed successfully!${NC}"
    echo ""
    echo -e "${BLUE}What was accomplished:${NC}"
    echo "✅ Processed $((end-start)) tasks through complete 8-node pipeline"
    echo "✅ Used fully independent implementation"
    echo "✅ Generated results in results/ directory"
    echo ""
    echo -e "${BLUE}Usage examples:${NC}"
    echo "# Process 50 tasks:"
    echo "  END=50 bash run/run_production.sh"
    echo ""
    echo "# Process ALL data with real models:"
    echo "  END=-1 USE_REAL_MODELS=true OPENAI_API_KEY=your-key bash run/run_production.sh"
    echo ""
    echo "# High-performance mode with more workers and Redis cache:"
    echo "  NUM_WORKERS=6 POOL_SIZE=4 ENABLE_REDIS=true bash run/run_production.sh"
    echo ""
    echo "# Quick test with 3 tasks:"
    echo "  END=3 bash run/run_production.sh"
else
    echo -e "${RED}Pipeline failed with error code $exit_code${NC}"
    echo "Check the logs above for details"
    exit $exit_code
fi