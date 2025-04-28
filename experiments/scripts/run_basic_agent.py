import logging
import time
import datetime
from experiments.src.memory_system.langchain_adapter import CogniStructuredMemoryAdapter
from experiments.src.memory_system.structured_memory_bank import StructuredMemoryBank
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.llms import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize memory bank and adapter
memory_bank = StructuredMemoryBank(
    dolt_db_path="./data/memory_dolt",
    chroma_path="./data/memory_chroma",
    chroma_collection="cogni_test_collection"
)
cogni_memory = CogniStructuredMemoryAdapter(memory_bank=memory_bank)

# Initialize the LLM
model_name = "gpt-3.5-turbo-instruct"
llm = OpenAI(temperature=0.7, model=model_name)

# Define a prompt template that includes memory
prompt_template = """
You are a helpful assistant with memory capabilities.

Here's what I know from memory:
{relevant_blocks}

Based on this memory and your knowledge, please respond to:
{input}
"""

prompt = PromptTemplate(
    input_variables=["input", "relevant_blocks"],
    template=prompt_template
)

# Initialize the chain with the LLM and prompt
chain = LLMChain(llm=llm, prompt=prompt)

# Generate a session ID for this run
session_id = f"test_session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

# Input for the chain with additional metadata for enhanced save_context
input_data = {
    "input": "What is the core philosophy of Cogni?",
    "session_id": session_id,
    "model": model_name,
    "token_count": {"prompt": 150, "completion": 0}  # Will be updated after response
}

# Load memory variables explicitly first to get context for the prompt
# The dictionary returned by load_memory_variables needs to be merged with input_data
memory_context = cogni_memory.load_memory_variables(input_data)

# Combine the original input with the loaded memory context
full_input = {**input_data, **memory_context}

logger.info(f"Invoking chain with combined input: {list(full_input.keys())}") 
# Log keys to show memory_key is included

try:
    # Record start time for latency calculation
    start_time = time.time()
    
    # Invoke the chain with the combined input
    response = chain.invoke(full_input)
    
    # Calculate latency
    latency_ms = int((time.time() - start_time) * 1000)
    input_data["latency"] = latency_ms
    
    # Extract content from the AIMessage response
    ai_content = response.content if hasattr(response, 'content') else str(response)
    
    # Update token counts (estimate for completion)
    input_data["token_count"]["completion"] = len(ai_content.split()) * 1.3  # Rough estimate
    
    logger.info(f"Agent Response: {ai_content}")
    
    # Manually save context *after* successful invocation
    # This ensures save_context is called, as the simple `prompt | llm` chain doesn't automatically manage it.
    cogni_memory.save_context(input_data, {"output": ai_content})
    logger.info(f"Manually called save_context after successful chain invocation. Session ID: {session_id}")

except Exception as e:
    logger.error(f"Error invoking chain or saving context: {e}", exc_info=True) 