import logging
import uuid
from datetime import datetime

# Relative imports assuming the script is run from the workspace root
# or that the path is adjusted appropriately.
# If running directly, might need path adjustments (e.g., using sys.path.append)
from experiments.src.memory_system.llama_memory import LlamaMemory
from experiments.src.memory_system.schemas.memory_block import MemoryBlock

# Configure logging for the test script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - TEST - %(message)s')

def run_basic_memory_test():
    """Performs the basic add and query test for LlamaMemory."""
    logging.info("Starting basic LlamaMemory test...")

    # 1. Define a sample MemoryBlock instance
    sample_id = str(uuid.uuid4())
    sample_text = "Mars is the fourth planet from the Sun and the second-smallest planet in the Solar System."
    query_text = "Tell me about the planet Mars"

    sample_block = MemoryBlock(
        id=sample_id,
        type="knowledge",
        text=sample_text,
        tags=["test", "solar_system", "planet", "mars"],
        metadata={"source": "basic_test_script"},
        created_at=datetime.utcnow()
    )
    logging.info(f"Created sample MemoryBlock with ID: {sample_id}")
    logging.info(f"Sample Text: '{sample_block.text}'")

    # 2. Initialize LlamaMemory
    # It will load or create the index based on the default path ./storage/chroma
    memory = LlamaMemory()

    if not memory.is_ready():
        logging.error("LlamaMemory failed to initialize. Aborting test.")
        return

    logging.info("LlamaMemory initialized successfully.")

    # 3. Add the sample block to the index
    logging.info(f"Adding sample block (ID: {sample_id}) to the index...")
    memory.add_block(sample_block)
    logging.info("add_block function called.")

    # Optional: Add a small delay or check if insertion is synchronous if needed
    # time.sleep(1) # Usually not necessary for Chroma in-process

    # 4. Perform a semantic query
    logging.info(f"Performing query: '{query_text}'")
    response = memory.query(query_text)

    # 5. Print and verify results
    print("-" * 30)
    print(f"Query: {query_text}")
    print("-" * 30)
    if response:
        print("Query Response:")
        print(response)
        print("\nRetrieved Nodes:")
        found_match = False
        for node in response.source_nodes:
            print(f"  Node ID: {node.node_id}, Score: {node.score:.4f}")
            print(f"    Text: {node.text}")
            # Check if the retrieved node ID matches our sample block ID
            if node.node_id == sample_id:
                found_match = True
                logging.info(f"Successfully retrieved the added sample block (ID: {sample_id})!")
        print("-" * 30)
        if found_match:
            logging.info("Basic memory test PASSED!")
        else:
            logging.error(f"Basic memory test FAILED: Did not retrieve node with ID {sample_id}")

    else:
        logging.error("Query returned no response.")
        print("Query returned no response.")
        print("-" * 30)
        logging.error("Basic memory test FAILED: Query returned None.")

    logging.info("Basic LlamaMemory test finished.")


if __name__ == "__main__":
    run_basic_memory_test() 