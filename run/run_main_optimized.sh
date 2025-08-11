#!/bin/bash

# OpenSearch-SQL Optimized Pipeline Runner
# This script provides the same functionality as run_main.sh but with performance optimizations

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}OpenSearch-SQL Optimized Pipeline${NC}"
echo -e "${GREEN}============================================${NC}"

# Define variables (same as original)
data_mode='dev' # Options: 'dev', 'train' 
db_root_path=Bird # Root directory - UPDATE THIS WITH THE PATH TO THE TARGET DATASET
start=0 # Start index (inclusive)
end=${END:-10}  # End index (exclusive, default 10 for demo, use -1 for all)

# Pipeline configuration
pipeline_nodes='generate_db_schema+extract_col_value+extract_query_noun+column_retrieve_and_other_info+candidate_generate+align_correct+vote+evaluation'

# Checkpoint configuration (optional)
# use_checkpoint=true
# checkpoint_nodes='generate_db_schema,extract_col_value,extract_query_noun'
# checkpoint_dir="./results/dev/generate_db_schema+extract_col_value+extract_query_noun+column_retrieve_and_other_info+candidate_generate+align_correct+vote+evaluation/Bird/2024-09-12-01-48-10"

# API Key - Set your API key here or via environment variable
AK=${OPENAI_API_KEY:-'sk-ant-oat01-6a40bf36ee9996679e31acdcb44cb65de9d2068dae3bffdcba07a93e24d3207f'}

# Engine configurations (same as original)
engine0='gpt-4o' # Cursor API refer to gpt-4o-2024-05-13 
engine1='gpt-4o-0513'
engine2='gpt-3.5-turbo-0125'
engine3='gpt-4-turbo'
engine4='claude-3-opus-20240229'
engine5='gemini-1.5-pro-latest'

# BERT model path
bert_model_path="/opt/local/llm_models/embeddings/BAAI/bge-m3"

# ===== OPTIMIZATION SETTINGS =====
# These are new settings for the optimized implementation

# Execution mode: 'sequential', 'thread', 'multiprocess', 'async'
EXECUTION_MODE=${EXECUTION_MODE:-'multiprocess'}

# Number of workers (for parallel execution)
NUM_WORKERS=${NUM_WORKERS:-3}

# Batch size for processing
BATCH_SIZE=${BATCH_SIZE:-10}

# Enable caching
CACHE_ENABLED=${CACHE_ENABLED:-true}

# Enable progress bar
PROGRESS_BAR=${PROGRESS_BAR:-true}

# Log level
LOG_LEVEL=${LOG_LEVEL:-'INFO'}

echo -e "${YELLOW}Configuration:${NC}"
echo "  Data mode: $data_mode"
echo "  Database path: $db_root_path"
echo "  Pipeline: ${pipeline_nodes/+/ -> }"
echo "  Execution mode: $EXECUTION_MODE"
echo "  Workers: $NUM_WORKERS"
echo "  Cache: $CACHE_ENABLED"
echo ""

# Pipeline setup (optimized for production)
# Note: Using mock models by default for demo. Change to real models in production.
pipeline_setup='{
    "generate_db_schema": {
        "engine": "mock",
        "bert_model": "'${bert_model_path}'",
        "device":"cpu"
    },
    "extract_col_value": {
        "engine": "mock",
        "temperature":0.0
    },
    "extract_query_noun": {
        "engine": "mock",
        "temperature":0.0
    },
    "column_retrieve_and_other_info": {
        "engine": "mock",
        "bert_model": "'${bert_model_path}'",
        "device":"cpu",
        "temperature":0.3,
        "top_k":10
    },
    "candidate_generate":{
        "engine": "mock",
        "temperature": 0.7,  
        "n":5,
        "return_question":"True",
        "single":"False"
    },
    "align_correct":{
        "engine": "mock",
        "n":5,
        "bert_model": "'${bert_model_path}'",
        "device":"cpu",
        "align_methods":"style_align+function_align+agent_align"
    },
    "vote": {
        "method": "simple"
    },
    "evaluation": {
        "method": "basic"
    }
}'

# Export environment variables for API access
export OPENAI_API_KEY=$AK
export OPENAI_BASE_URL=${OPENAI_BASE_URL:-"https://api.openai.com/v1"}

# Build the command - use the standalone implementation
CMD="python3 -m src_optimized.main_standalone"
CMD="$CMD --data_mode ${data_mode}"
CMD="$CMD --db_root_path ${db_root_path}"
CMD="$CMD --pipeline_nodes ${pipeline_nodes}"
CMD="$CMD --pipeline_setup '$pipeline_setup'"
CMD="$CMD --start ${start}"
CMD="$CMD --end ${end}"
CMD="$CMD --execution_mode ${EXECUTION_MODE}"
CMD="$CMD --num_workers ${NUM_WORKERS}"
CMD="$CMD --batch_size ${BATCH_SIZE}"
CMD="$CMD --log_level ${LOG_LEVEL}"

# Add optional flags
if [ "$CACHE_ENABLED" = true ]; then
    CMD="$CMD --cache_enabled"
fi

if [ "$PROGRESS_BAR" = true ]; then
    CMD="$CMD --enable_progress_bar"
fi

# Add checkpoint flags if configured
if [ "$use_checkpoint" = true ]; then
    CMD="$CMD --use_checkpoint"
    CMD="$CMD --checkpoint_nodes ${checkpoint_nodes}"
    CMD="$CMD --checkpoint_dir ${checkpoint_dir}"
fi

# Check if profiling is requested
if [ "$ENABLE_PROFILING" = true ]; then
    CMD="$CMD --enable_profiling --save_stats"
fi

echo -e "${GREEN}Starting optimized pipeline...${NC}"
echo "Command: $CMD"
echo ""

# Set Python path and run
PYTHONPATH=$PWD/src:$PWD/src_optimized eval $CMD

# Check exit status
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Pipeline completed successfully!${NC}"
else
    echo -e "${RED}Pipeline failed with error code $?${NC}"
    exit 1
fi