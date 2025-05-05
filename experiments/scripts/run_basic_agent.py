import os
import sys
from pathlib import Path
import logging
from datetime import datetime
import time

from infra_core.memorysystem.tools.memory_core.create_memory_block_tool import (
    create_memory_block,
    CreateMemoryBlockInput,
)
from langchain.tools import Tool
from infra_core.memorysystem.langchain_adapter import CogniStructuredMemoryAdapter
from infra_core.memorysystem.structured_memory_bank import StructuredMemoryBank
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.llms import OpenAI
from langchain.agents import initialize_agent, AgentType

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize memory bank and adapter using the experimental database paths
dolt_db_path = os.path.join(project_root, "experiments", "dolt_data", "memory_db")
chroma_path = os.path.join(project_root, "experiments", "dolt_data", "chroma_db")

memory_bank = StructuredMemoryBank(
    dolt_db_path=dolt_db_path,  # Using experimental database path
    chroma_path=chroma_path,  # Using experimental database path
    chroma_collection="cogni_test_collection",
)
cogni_memory = CogniStructuredMemoryAdapter(memory_bank=memory_bank)

# Initialize the LLM
model_name = "gpt-3.5-turbo-instruct"
llm = OpenAI(temperature=0.7, model=model_name)

# Create the CreateMemoryBlock tool
create_memory_block_tool = Tool(
    name="CreateMemoryBlock",
    func=lambda tool_input: create_memory_block(
        input_data=CreateMemoryBlockInput.model_validate_json(tool_input), memory_bank=memory_bank
    ),
    description="""Create a new memory block. Input should be a JSON string with fields:
- type: one of ["knowledge", "task", "project", "doc", "interaction"]
- text: string content
- state: one of ["draft", "published", "archived"] (optional, default "draft")
- visibility: one of ["internal", "public", "restricted"] (optional, default "internal")
- tags: list of strings (optional)
- metadata: dictionary (optional)
- source_file: string (optional)
- confidence: object with score fields (optional)
- created_by: string (optional)""",
)

# Define a prompt template that includes memory and tool usage
prompt_template = """
You are a helpful assistant with memory capabilities and the ability to create new memory blocks.

Here's what I know from memory:
{relevant_blocks}

You can create new memory blocks using the CreateMemoryBlock tool. Use it to store important information
that might be useful later. The block types are:
- knowledge: For facts, concepts, and information
- task: For todo items and action items
- project: For project definitions and goals
- doc: For documentation and guides

Based on this memory and your knowledge, please respond to:
{input}

If your response contains important information that should be remembered, create a memory block for it.
"""

prompt = PromptTemplate(input_variables=["input", "relevant_blocks"], template=prompt_template)

# Initialize the agent with the tool
agent = initialize_agent(
    tools=[create_memory_block_tool],
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
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
    "token_count": {"prompt": 150, "completion": 0},  # Will be updated after response
}

# Load memory variables explicitly first to get context for the prompt
memory_context = cogni_memory.load_memory_variables(input_data)

# Combine the original input with the loaded memory context
full_input = {**input_data, **memory_context}

logger.info(f"Invoking agent with combined input: {list(full_input.keys())}")

try:
    # Record start time for latency calculation
    start_time = time.time()

    # Run the agent using invoke instead of run
    response = agent.invoke(full_input)

    # Calculate and log latency
    latency = time.time() - start_time
    logger.info(f"Agent response generated in {latency:.2f} seconds")

    # Update token count in input data
    input_data["token_count"]["completion"] = len(response["output"].split())

    # Save the interaction to memory
    cogni_memory.save_context(input_data, {"output": response["output"]})

    logger.info(f"Agent response: {response['output']}")

except Exception as e:
    logger.error(f"Error running agent: {str(e)}")
    raise
