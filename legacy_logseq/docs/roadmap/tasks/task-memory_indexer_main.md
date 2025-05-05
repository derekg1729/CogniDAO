# Task:[Create Memory Indexer Main Script]
:type: Task
:status: completed
:project: [project-cogni_memory_architecture]
:owner: 

## Current Status
The memory indexer main script has been fully implemented with:
- Comprehensive command-line argument parsing
- Proper error handling at all levels
- Progress reporting with tqdm
- Integration with LogseqParser
- Configurable target tags and embedding models
- ChromaDB integration with error recovery

## Description
Create a main entry point script for the memory indexer that:
1. Scans Logseq files for blocks with target tags
2. Embeds these blocks using the selected model
3. Stores them in ChromaDB for vector search
4. Provides an easy CLI for integration with other tools

## Action Items
- [x] Define CLI parameters for directory paths, embedding model, etc.
  - Implemented with argparse in `memory_indexer.py`
- [x] Create main function that orchestrates the complete pipeline
  - Implemented as `run_indexing()` in `memory_indexer.py`
- [x] Add ChromaDB initialization and error handling
  - Improved error handling in `init_chroma_client()`
- [x] Implement embedding function initialization with model options
  - Enhanced with better error checking in `init_embedding_function()`
- [x] Add logging and progress reporting
  - Added logging with proper levels and tqdm progress bars
- [x] Handle edge cases and proper exit codes
  - Implemented with try/except blocks and meaningful exit codes

## Deliverables
1. A memory_indexer.py script that:
   - Processes CLI arguments for configuration ✅
   - Integrates with the parser module ✅
   - Handles embedding and storage ✅
   - Reports progress and errors clearly ✅
   - Returns appropriate exit codes ✅

## Test Criteria
- [x] Test the script with various parameters
```python
# This can be run as a direct command:
python -m legacy_logseq.memory.memory_indexer --logseq-dir ./logseq --vector-db-dir ./cogni-memory/chroma --embed-model mock --tags thought broadcast
```

- [x] Verify error handling for invalid paths
- [x] Test progress reporting for large datasets
- [x] Validate exit codes for success/failure scenarios
- [x] Confirm proper logging output

## Implementation Details
The memory indexer main script has been implemented with:

1. **Command Line Interface**:
   - `--logseq-dir`: Path to Logseq markdown files
   - `--vector-db-dir`: Path for ChromaDB storage
   - `--embed-model`: Choice of embedding model (openai, mock)
   - `--collection`: Name of the ChromaDB collection
   - `--tags`: Custom tags to filter for
   - `--verbose`: Toggle detailed logging

2. **Runtime Flow**:
   - Parse command line arguments
   - Initialize logger with appropriate level
   - Set up ChromaDB client and collection
   - Initialize embedding function
   - Create LogseqParser and extract blocks
   - Index blocks with progress reporting
   - Return appropriate exit code

3. **Error Handling**:
   - Directory validation with automatic creation
   - ChromaDB connection error handling
   - API key validation for embedding models
   - Graceful error reporting with detailed logs in verbose mode
   - Structured exit codes (0=success, 1=no blocks, 2=error)

## Notes
- The script works as both a CLI tool and an importable module
- All functions have proper docstrings and type hints
- The implementation follows a clean separation of concerns
- Progress reporting uses tqdm for visual feedback

## Dependencies
- ChromaDB for vector storage
- OpenAI API for embeddings
- LogseqParser for block extraction
- tqdm for progress reporting
- argparse for CLI handling 