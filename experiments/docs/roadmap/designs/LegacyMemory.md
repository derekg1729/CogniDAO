classDiagram
    direction LR

subgraph MemoryBank
    direction LR

    class BaseCogniMemory {
        <<Abstract>>
        +read_history_dicts() List[Dict]
    }

    class FileMemoryBank {
        <<File I/O Logic>>
        +write_history_dicts(history_dicts: List[Dict])
    }

    class MockMemoryBank {
        <<In-Memory Mock>>
        +read_history_dicts() List[Dict]
    }

    class CogniLangchainMemoryAdapter {
        <<LangChain Adapter>>
        +load_memory_variables(inputs) Dict
    }

    class BaseMemory {
        <<LangChain Core>>
        +load_memory_variables(inputs) Dict
    }

    class BaseMessage {
        <<LangChain Core Data>>
    }

    FileMemoryBank --|> BaseCogniMemory : implements
    MockMemoryBank --|> BaseCogniMemory : implements
    CogniLangchainMemoryAdapter --|> BaseMemory : implements
    CogniLangchainMemoryAdapter --> BaseCogniMemory : wraps/uses
    CogniLangchainMemoryAdapter ..> BaseMessage : converts
end

subgraph MemoryClient
    direction LR

    class CogniMemoryClient {
        <<Client Facade>>
        +query(query_text: str, ...) QueryResult
    }

    class CombinedStorage {
        <<Storage Aggregator>>
        +query(...)
    }

    class ChromaStorage {
        <<Vector Store>>
        +query(...)
    }

    class ArchiveStorage {
        <<File Archive>>
        +retrieve_block(block_id) Dict?
    }

    class MemoryBlock {
        <<Data Schema>>
    }

    class QueryResult {
        <<Data Schema>>
    }

    class LogseqParser {
        <<Parser>>
        +extract_all_blocks() List[Dict]
    }

    class memory_tool {
        <<Agent Tool Function>>
        +memory_tool(input_text, ...) Dict
    }

    class memory_indexer {
        <<Indexing Script>>
        +run_indexing(...) int
    }

    CogniMemoryClient --> CombinedStorage : uses
    CombinedStorage --> ChromaStorage : uses
    CombinedStorage --> ArchiveStorage : uses
    CogniMemoryClient ..> MemoryBlock : handles
    CogniMemoryClient ..> QueryResult : handles
    CogniMemoryClient ..> LogseqParser : uses
    memory_tool ..> CogniMemoryClient : uses
    memory_indexer ..> ChromaStorage : writes to
    memory_indexer ..> LogseqParser : uses
end
