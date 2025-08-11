# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

OpenSearch-SQL is a comprehensive Text-to-SQL framework that achieved first place on the BIRD benchmark. It converts natural language queries into SQL using a modular pipeline approach with multiple processing nodes. The system supports various LLMs (GPT, Claude, Gemini, DeepSeek) and uses techniques like Chain of Thought reasoning, schema linking, and alignment correction.

## Key Commands

### Installation
```bash
pip install -r requirements.txt
pip install "langgraph<0.3"  # Fix compatibility issues
```

### Data Preprocessing (requires BIRD dataset)
```bash
sh run/run_preprocess.sh  # Processes fewshot, table, and other data
```

### Main Pipeline Execution
```bash
sh run/run_main.sh  # Runs the complete Text-to-SQL pipeline
```

### Using Makefile
```bash
make run_main  # Alternative way to run the main pipeline
```

## Prerequisites

### BIRD Dataset Setup
This repository requires the BIRD dataset to be downloaded and placed in the correct structure:

```
Bird/
├── dev/
│   ├── dev.json
│   ├── dev_tables.json
│   └── dev_databases/
├── train/
│   ├── train.json
│   └── train_tables.json
├── bird_dev.json (DAIL-SQL format)
└── fewshot/
    └── questions.json
```

**Download Instructions:**
1. Download the BIRD dataset from [https://bird-bench.github.io/](https://bird-bench.github.io/)
2. Extract the dataset files into the `Bird/` directory
3. Ensure the structure matches the expected format above

### Model Configuration
Update the following paths in `run/run_preprocess.sh` and `run/run_main.sh`:
- `bert_model_path`: Set to a valid BGE model path (e.g., `BAAI/bge-m3`)
- `AK`: Set your API key for the chosen LLM provider

### API Keys
Configure your API key in `run/run_main.sh`:
- Update the `AK` variable with your API key
- Ensure the selected engine (gpt-4o, claude, etc.) matches your API provider

## Architecture Overview

### Core Components

1. **Pipeline Framework**: Built using LangGraph with a StateGraph workflow system
   - **Pipeline Manager** (`src_optimized/pipeline/pipeline_manager.py`): Singleton pattern manager for pipeline configuration
   - **Workflow Builder** (`src_optimized/pipeline/workflow_builder.py`): Constructs the processing graph with configurable nodes
   - **Run Manager** (`src_optimized/runner/run_manager.py`): Orchestrates task execution with multiprocessing support and data persistence

2. **Processing Pipeline Nodes** (executed in sequence):
   - `generate_db_schema`: Database schema generation and processing
   - `extract_col_value`: Column value extraction from queries
   - `extract_query_noun`: Query noun phrase extraction
   - `column_retrieve_and_other_info`: Column retrieval and metadata gathering
   - `candidate_generate`: SQL candidate generation (n=21 by default)
   - `align_correct`: Multi-stage alignment (style_align+function_align+agent_align)
   - `vote`: Voting mechanism for best SQL selection
   - `evaluation`: Result evaluation and scoring

3. **LLM Integration** (`src_optimized/llm/`):
   - **Model Abstraction** (`model.py`): Supports multiple LLM providers (OpenAI, Claude, Gemini, Dashscope)
   - **Prompt Management** (`prompts.py`, `all_prompt.py`): Centralized prompt templates
   - **Database Conclusion** (`db_conclusion.py`): Schema reasoning logic

4. **Runner System** (`src_optimized/runner/`):
   - **Database Manager** (`database_manager.py`): Database connection and query execution
   - **Task Management** (`task.py`): Individual task representation and execution
   - **Statistics Manager** (`statistics_manager.py`): Performance tracking and metrics
   - **Logger** (`logger.py`): Enhanced logger with loguru integration and backward compatibility

5. **Utilities** (`src_optimized/utils/`):
   - **Loguru Configuration** (`loguru_config.py`): Unified logging system with structured output, rotation, and compression
   - **Results Collector** (`results_collector.py`): Thread-safe data persistence maintaining dataset order
   - **Configuration Helpers**: Performance optimization and caching utilities

### Configuration

Pipeline behavior is controlled through JSON configuration in `run/run_main.sh`:
- **Engine Selection**: Choose from gpt-4o, claude-3-opus, gemini-1.5-pro, etc.
- **Temperature Settings**: Different values for different nodes (0.0 for deterministic, 0.7 for creative)
- **Model Paths**: BERT model paths for embeddings (`bge-m3` by default)
- **Alignment Methods**: Configurable alignment strategies
- **Batch Processing**: Start/end indices for processing subsets

### Data Processing

1. **Database Preprocessing** (`src/database_process/`):
   - `data_preprocess.py`: Processes BIRD dataset files
   - `generate_question.py`: Creates few-shot examples using DAIL-SQL method
   - `make_emb.py`: Generates embeddings for schema linking
   - `prepare_train_queries.py`: Prepares training queries

2. **Expected Data Structure**:
   - Dataset root: `Bird/` directory
   - JSON files: `dev/dev.json`, `train/train.json`
   - Database files: `dev/dev_databases/`
   - Few-shot data: `Bird/fewshot/questions.json`

### Key Features

- **Self-taught CoT**: Extends few-shot format to Query-CoT-SQL pairs
- **SQL-Like Intermediate Language**: Optimizes SQL generation process
- **Multi-stage Alignment**: Reduces hallucination through style, function, and agent alignment
- **Beam Search**: Generates multiple candidates (n=21) with voting mechanism
- **Schema Linking**: Uses BERT embeddings for column retrieval
- **Checkpointing**: Supports resuming from intermediate pipeline stages

### Important Paths and Configuration

- **Results Directory**: `results/{dataset_name}/{YYYY-MM-DD_HH-MM-SS}/` (simplified 3-layer structure)
- **Log Directory**: `results/.../logs/` with loguru structured logging
- **Work Log**: `WORK_LOG.md` for session continuity and development history
- **Configuration**: Pipeline setup is passed as JSON string in shell scripts
- **API Keys**: Set in `run/run_main.sh` (AK variable for API authentication)
- **Model Paths**: Update `bert_model_path` variable for local embeddings model

### Current System Status

- ✅ **Loguru Integration**: Complete migration from standard logging to loguru with structured output
- ✅ **Data Persistence**: ResultsCollector with thread-safe operation and multiple output formats
- ✅ **Multiprocessing Support**: Fixed pickle serialization issues for parallel task execution
- ✅ **Test Set Compatibility**: Automatic handling of datasets with/without ground truth SQL
- ✅ **Directory Simplification**: User-friendly 3-layer result structure

### Execution Flow

1. Load dataset from preprocessed JSON files
2. Initialize RunManager with configuration and ResultsCollector
3. Create Task objects for each query (indexed by start/end parameters)
4. Execute pipeline nodes sequentially via LangGraph workflow
5. Generate candidate SQLs with beam search
6. Apply alignment corrections to reduce hallucination
7. Vote on best SQL candidate
8. Evaluate results (with automatic test/dev set detection)
9. Persist results in multiple formats (JSON, CSV) while maintaining dataset order
10. Generate comprehensive logs and statistics

## Work Log Requirements

**IMPORTANT**: When working on this repository, always maintain the work log (`WORK_LOG.md`) to ensure session continuity. The work log should include:

### Required Log Entries

- **Session Date and Overview**: Brief summary of work performed
- **Major Changes**: List of significant modifications with file paths
- **System Status Updates**: Current functionality and known issues
- **Configuration Changes**: Any updates to settings, paths, or parameters
- **Testing Results**: Verification of new features and bug fixes
- **Next Steps**: Suggestions for future development

### Log Update Triggers

- After completing major features or bug fixes
- When modifying core system components
- After testing and validation phases
- Before ending development sessions
- When encountering and resolving significant issues

### Log Format Standards

- Use clear section headers and bullet points
- Include file paths for modified components
- Document both successful implementations and known limitations
- Provide context for technical decisions
- Include relevant configuration examples