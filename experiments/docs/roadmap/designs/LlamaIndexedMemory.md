```mermaid
classDiagram
    direction LR

    subgraph InteractionLayer
        direction LR
        class API {
            <<FastAPI Server>>
        }
        class Agent {
            <<LangChain Agent>>
        }
        class Tools {
            <<Memory Tools>>
            +QueryMemoryBlocks()
            +CreateMemoryBlock()
        }
        API --> Agent : Receives request
        Agent --> Tools : Selects tool
    end

    subgraph PersistenceAndQueryLayer
        direction TB
        class Index {
            <<LlamaIndex Vector Index>>
            +Query()
            +UpdateIndex()
        }
        note for Index "Semantic + graph search via ComposableGraphIndex"
        class Storage {
            <<Dolt Database>>
            +WriteBlock()
            +ReadBlockData()
        }
        class VectorStore {
             <<ChromaDB>>
        }
        Index <|-- VectorStore : Uses
        Index ..> Storage : Reads Data for Indexing
    end

    Tools --> Index : Query Request
    Tools --> Storage : Write Request (MemoryBlock)
    Storage ..> Index : Write Trigger (Updates Index)
    Storage ..> Index : Reverse Graph Links
