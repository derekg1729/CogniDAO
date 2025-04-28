import logging
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
llm = OpenAI(temperature=0.7)

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

# Input for the chain
input_data = {"input": "What is the core philosophy of Cogni?"}

# Load memory variables explicitly first to get context for the prompt
# The dictionary returned by load_memory_variables needs to be merged with input_data
memory_context = cogni_memory.load_memory_variables(input_data)

# Combine the original input with the loaded memory context
full_input = {**input_data, **memory_context}

logger.info(f"Invoking chain with combined input: {list(full_input.keys())}") 
# Log keys to show memory_key is included

try:
    # Invoke the chain with the combined input
    response = chain.invoke(full_input)
    
    # Extract content from the AIMessage response
    ai_content = response.content if hasattr(response, 'content') else str(response)
    logger.info(f"Agent Response: {ai_content}")
    
    # Manually save context *after* successful invocation
    # This ensures save_context is called, as the simple `prompt | llm` chain doesn't automatically manage it.
    cogni_memory.save_context(input_data, {"output": ai_content})
    logger.info("Manually called save_context after successful chain invocation.")

except Exception as e:
    logger.error(f"Error invoking chain or saving context: {e}", exc_info=True) 