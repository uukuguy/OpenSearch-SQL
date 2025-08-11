# OpenSearch-SQL Pipeline - Standalone Implementation

A complete, standalone implementation of the OpenSearch-SQL Text-to-SQL pipeline that achieved first place on the BIRD benchmark. This implementation is self-contained and does not depend on the original `src/` directory.

## Features

- **Complete Pipeline**: All 8 pipeline nodes implemented
- **LLM Integration**: Support for OpenAI GPT, Anthropic Claude, and mock models
- **Standalone**: No dependencies on the original implementation
- **Optimized**: Performance improvements and better error handling
- **Configurable**: JSON-based configuration system
- **Monitoring**: Built-in performance monitoring and statistics
- **Checkpointing**: Resume execution from intermediate stages

## Architecture

```
src_optimized/
├── core/                          # Core components
│   ├── task.py                   # Task representation
│   ├── database_manager.py       # Database operations
│   ├── logger.py                 # Logging system
│   ├── pipeline_manager.py       # Pipeline configuration
│   └── statistics_manager.py     # Performance statistics
├── pipeline/                      # Pipeline components
│   ├── workflow_builder.py       # LangGraph workflow builder
│   ├── utils.py                  # Pipeline utilities
│   └── nodes/                    # Pipeline node implementations
│       ├── generate_db_schema.py
│       ├── extract_col_value.py
│       ├── extract_query_noun.py
│       ├── column_retrieve_and_other_info.py
│       ├── candidate_generate.py
│       ├── align_correct.py
│       ├── vote.py
│       └── evaluation.py
├── llm/                          # LLM integration
│   ├── model.py                  # Model abstraction
│   └── prompts.py                # Prompt management
├── runner/                       # Task execution
│   └── run_manager.py            # Task orchestration
├── utils/                        # Utility functions
│   ├── config_helper.py          # Configuration management
│   ├── data_helper.py            # Dataset handling
│   └── performance_helper.py     # Performance monitoring
└── main.py                       # Main entry point
```

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
pip install "langgraph<0.3"
```

2. Set up environment variables:
```bash
export OPENAI_API_KEY="your-openai-api-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # Optional
```

## Quick Start

### Basic Usage

```bash
python -m src_optimized.main \
    --data_mode dev \
    --db_root_path ./Bird \
    --pipeline_nodes "generate_db_schema+extract_col_value+candidate_generate+vote+evaluation" \
    --pipeline_setup '{"candidate_generate": {"engine": "gpt-4o", "temperature": 0.0, "n": 1}}'
```

### Full Pipeline

```bash
python -m src_optimized.main \
    --data_mode dev \
    --db_root_path ./Bird \
    --pipeline_nodes "generate_db_schema+extract_col_value+extract_query_noun+column_retrieve_and_other_info+candidate_generate+align_correct+vote+evaluation" \
    --pipeline_setup '{
        "generate_db_schema": {"engine": "gpt-4o", "temperature": 0.0},
        "extract_col_value": {"engine": "gpt-4o", "temperature": 0.0},
        "extract_query_noun": {"engine": "gpt-4o", "temperature": 0.0},
        "column_retrieve_and_other_info": {"engine": "gpt-4o", "temperature": 0.0},
        "candidate_generate": {"engine": "gpt-4o", "temperature": 0.0, "n": 5},
        "align_correct": {"engine": "gpt-4o", "temperature": 0.0},
        "vote": {"engine": "gpt-4o", "voting_method": "execution_based"},
        "evaluation": {"engine": "gpt-4o", "temperature": 0.0}
    }' \
    --start 0 \
    --end 10
```

### Using Mock Model (for testing)

```bash
python -m src_optimized.main \
    --data_mode dev \
    --db_root_path ./Bird \
    --pipeline_nodes "candidate_generate+vote+evaluation" \
    --pipeline_setup '{"candidate_generate": {"engine": "mock", "n": 1}}' \
    --start 0 \
    --end 2
```

## Configuration

### Pipeline Setup

The `pipeline_setup` parameter is a JSON string containing configuration for each node:

```json
{
    "generate_db_schema": {
        "engine": "gpt-4o",
        "temperature": 0.0,
        "bert_model": "BAAI/bge-m3",
        "device": "cpu"
    },
    "candidate_generate": {
        "engine": "gpt-4o",
        "temperature": 0.0,
        "n": 5,
        "single": "true"
    },
    "vote": {
        "voting_method": "execution_based",
        "use_llm_voting": false
    }
}
```

### Supported Engines

- `gpt-4o`: OpenAI GPT-4 Omni
- `gpt-4`: OpenAI GPT-4
- `claude-3-opus`: Anthropic Claude 3 Opus
- `mock`: Mock model for testing

### Pipeline Nodes

1. **generate_db_schema**: Generate database schema descriptions
2. **extract_col_value**: Extract specific values from questions
3. **extract_query_noun**: Extract important entities and nouns
4. **column_retrieve_and_other_info**: Retrieve relevant columns and metadata
5. **candidate_generate**: Generate SQL query candidates
6. **align_correct**: Apply alignment corrections
7. **vote**: Vote on the best SQL query
8. **evaluation**: Evaluate the final SQL query

## Advanced Features

### Checkpointing

Resume execution from intermediate stages:

```bash
python -m src_optimized.main \
    --data_mode dev \
    --db_root_path ./Bird \
    --pipeline_nodes "candidate_generate+vote+evaluation" \
    --pipeline_setup '{"candidate_generate": {"engine": "gpt-4o"}}' \
    --use_checkpoint \
    --checkpoint_nodes "generate_db_schema+extract_col_value" \
    --checkpoint_dir ./checkpoints
```

### Performance Monitoring

The system automatically tracks:
- Execution time per node
- Memory usage
- Success/failure rates
- SQL execution results

Results are saved in the results directory with comprehensive statistics.

### Logging

Set logging levels:
```bash
--log_level debug  # For detailed debugging information
--log_level info   # For general information (default)
--log_level warning # For warnings and errors only
```

## Dataset Structure

The system expects the BIRD dataset in this structure:

```
Bird/
├── dev_20240627/
│   ├── dev.json
│   ├── dev_tables.json
│   └── dev_databases/
│       ├── california_schools/
│       │   └── california_schools.sqlite
│       └── ...
├── fewshot/
│   └── questions.json
└── data_preprocess/
    ├── dev.json
    └── tables.json
```

## Results

Results are saved in:
```
results/{data_mode}/{pipeline_nodes}/{dataset_name}/{timestamp}/
├── -args.json              # Execution arguments
├── -statistics.json        # Performance statistics  
├── {question_id}_{db_id}.json  # Individual task results
└── logs/                   # Detailed execution logs
```

## Programmatic Usage

```python
from src_optimized.runner import RunManager
from src_optimized.utils import load_bird_dataset
import json

# Load dataset
dataset = load_bird_dataset("./Bird", "dev")

# Create mock arguments
class Args:
    data_mode = "dev"
    db_root_path = "./Bird"
    pipeline_nodes = "candidate_generate+vote+evaluation"
    pipeline_setup = json.dumps({"candidate_generate": {"engine": "mock"}})
    start = 0
    end = 2
    log_level = "info"
    use_checkpoint = False
    run_start_time = "2024-01-01-00-00-00"

# Run pipeline
with RunManager(Args()) as manager:
    manager.initialize_tasks(0, 2, dataset)
    manager.run_tasks()
    summary = manager.get_execution_summary()
    print(summary)
```

## Troubleshooting

### Common Issues

1. **Dataset not found**: Ensure the BIRD dataset is properly downloaded and extracted
2. **API key errors**: Set the appropriate environment variables for your LLM provider
3. **Memory issues**: Reduce the number of candidates (`n` parameter) or use checkpointing
4. **Database connection errors**: Verify SQLite database files exist

### Debug Mode

Run with debug logging to see detailed execution information:
```bash
python -m src_optimized.main ... --log_level debug
```

### Mock Testing

Use the mock engine to test the pipeline without API calls:
```bash
python -m src_optimized.main ... --pipeline_setup '{"candidate_generate": {"engine": "mock"}}'
```

## Development

### Adding New Pipeline Nodes

1. Create a new file in `pipeline/nodes/`
2. Implement the node function with the `@node_decorator`
3. Add the node to `pipeline/workflow_builder.py`
4. Update configuration documentation

### Adding New LLM Providers

1. Extend `llm/model.py` with a new model class
2. Update the `model_chose` function
3. Add configuration documentation

## Performance

The standalone implementation includes several optimizations:
- Efficient database connection management
- Intelligent caching of schema information
- Parallel processing support (experimental)
- Memory usage monitoring
- Comprehensive error handling

## License

This implementation follows the same license as the original OpenSearch-SQL project.