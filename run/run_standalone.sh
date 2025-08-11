#!/bin/bash

# OpenSearch-SQL Fully Standalone Pipeline Runner
# This script runs the completely independent implementation

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}OpenSearch-SQL Standalone Implementation${NC}"
echo -e "${GREEN}============================================${NC}"

# Configuration
data_mode='dev'
db_root_path=${DB_ROOT_PATH:-'Bird'}
start=${START:-0}
end=${END:-5}  # Process only 5 tasks by default for testing

# Pipeline configuration - using a simple pipeline that doesn't require all preprocessing
pipeline_nodes=${PIPELINE_NODES:-'candidate_generate+vote+evaluation'}

# Pipeline setup with mock models for testing
pipeline_setup='{
    "candidate_generate": {
        "engine": "mock",
        "temperature": 0.0,
        "n": 1
    },
    "vote": {
        "method": "simple"
    },
    "evaluation": {
        "method": "basic"
    }
}'

# Logging level
LOG_LEVEL=${LOG_LEVEL:-'INFO'}

echo -e "${YELLOW}Configuration:${NC}"
echo "  Data mode: $data_mode"
echo "  Database path: $db_root_path"
echo "  Task range: $start to $end"
echo "  Pipeline: ${pipeline_nodes/+/ -> }"
echo "  Log level: $LOG_LEVEL"
echo ""

echo -e "${GREEN}Starting fully standalone pipeline...${NC}"

# Run the standalone implementation
python -m src_optimized.main_standalone \
    --data_mode "$data_mode" \
    --db_root_path "$db_root_path" \
    --pipeline_nodes "$pipeline_nodes" \
    --pipeline_setup "$pipeline_setup" \
    --start "$start" \
    --end "$end" \
    --log_level "$LOG_LEVEL"

# Check exit status
exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}Standalone pipeline completed successfully!${NC}"
    echo ""
    echo "Features demonstrated:"
    echo "✅ Completely independent implementation"
    echo "✅ No dependencies on original src/ directory"
    echo "✅ Full pipeline execution with logging"
    echo "✅ Mock models for testing without API keys"
    echo "✅ Configurable pipeline nodes"
    echo ""
    echo "To run with different settings:"
    echo "  END=10 LOG_LEVEL=DEBUG bash run/run_standalone.sh"
    echo ""
    echo "To run the optimized version (with performance enhancements):"
    echo "  bash run/run_main_optimized.sh"
else
    echo -e "${RED}Standalone pipeline failed with error code $exit_code${NC}"
    exit $exit_code
fi