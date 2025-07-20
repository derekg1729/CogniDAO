Conceptual Guide to LangGraph Components
https://python.langchain.com/docs/concepts/
https://python.langchain.com/api_reference/langchain/

<guide_overview>
Conceptual guide
This guide provides explanations of the key concepts behind the LangChain framework and AI applications more broadly.

We recommend that you go through at least one of the Tutorials before diving into the conceptual guide. This will provide practical context that will make it easier to understand the concepts discussed here.

The conceptual guide does not cover step-by-step instructions or specific implementation examples — those are found in the How-to guides and Tutorials. For detailed reference material, please see the API reference.

High level
Why LangChain?: Overview of the value that LangChain provides.
Architecture: How packages are organized in the LangChain ecosystem.
</guide_overview>

<Concepts>

<chat_models>LLMs exposed via a chat API that process sequences of messages as input and output a message.</chat_models>
<messages>The unit of communication in chat models, used to represent model input and output.</messages>
<chat_history>A conversation represented as a sequence of messages, alternating between user messages and model responses.</chat_history>
<tools>A function with an associated schema defining the function's name, description, and the arguments it accepts.</tools>
<tool_calling>A type of chat model API that accepts tool schemas, along with messages, as input and returns invocations of those tools as part of the output message.</tool_calling>
<structured_output>A technique to make a chat model respond in a structured format, such as JSON that matches a given schema.</structured_output>
<memory>Information about a conversation that is persisted so that it can be used in future conversations.</memory>
<multimodality>The ability to work with data that comes in different forms, such as text, audio, images, and video.</multimodality>
<runnable_interface>The base abstraction that many LangChain components and the LangChain Expression Language are built on.</runnable_interface>
<streaming>LangChain streaming APIs for surfacing results as they are generated.</streaming>
<langchain_expression_language>A syntax for orchestrating LangChain components. Most useful for simpler applications.</langchain_expression_language>
<document_loaders>Load a source as a list of documents.</document_loaders>
<retrieval>Information retrieval systems can retrieve structured or unstructured data from a datasource in response to a query.</retrieval>
<text_splitters>Split long text into smaller chunks that can be individually indexed to enable granular retrieval.</text_splitters>
<embedding_models>Models that represent data such as text or images in a vector space.</embedding_models>
<vector_stores>Storage of and efficient search over vectors and associated metadata.</vector_stores>
<retriever>A component that returns relevant documents from a knowledge base in response to a query.</retriever>
<retrieval_augmented_generation>A technique that enhances language models by combining them with external knowledge bases.</retrieval_augmented_generation>
<agents>Use a language model to choose a sequence of actions to take. Agents can interact with external resources via tool.</agents>
<prompt_templates>Component for factoring out the static parts of a model "prompt" (usually a sequence of messages). Useful for serializing, versioning, and reusing these static parts.</prompt_templates>
<output_parsers>Responsible for taking the output of a model and transforming it into a more suitable format for downstream tasks. Output parsers were primarily useful prior to the general availability of tool calling and structured outputs.</output_parsers>
<few_shot_prompting>A technique for improving model performance by providing a few examples of the task to perform in the prompt.</few_shot_prompting>
<example_selectors>Used to select the most relevant examples from a dataset based on a given input. Example selectors are used in few-shot prompting to select examples for a prompt.</example_selectors>
<async_programming>The basics that one should know to use LangChain in an asynchronous context.</async_programming>
<callbacks>Callbacks enable the execution of custom auxiliary code in built-in components. Callbacks are used to stream outputs from LLMs in LangChain, trace the intermediate steps of an application, and more.</callbacks>
<tracing>The process of recording the steps that an application takes to go from input to output. Tracing is essential for debugging and diagnosing issues in complex applications.</tracing>
<evaluation>The process of assessing the performance and effectiveness of AI applications. This involves testing the model's responses against a set of predefined criteria or benchmarks to ensure it meets the desired quality standards and fulfills the intended purpose. This process is vital for building reliable applications.</evaluation>
<testing>The process of verifying that a component of an integration or application works as expected. Testing is essential for ensuring that the application behaves correctly and that changes to the codebase do not introduce new bugs.</testing>

</concepts>


<glossary>

<AIMessageChunk>A partial response from an AI message. Used when streaming responses from a chat model.</AIMessageChunk>
<AIMessage>Represents a complete response from an AI model.</AIMessage>
<astream_events>Stream granular information from LCEL chains.</astream_events>
<BaseTool>The base class for all tools in LangChain.</BaseTool>
<batch>Use to execute a runnable with batch inputs.</batch>
<bind_tools>Allows models to interact with tools.</bind_tools>
<Caching>Storing results to avoid redundant calls to a chat model.</Caching>
<Chat_models>Chat models that handle multiple data modalities.</Chat_models>
<Configurable_runnables>Creating configurable Runnables.</Configurable_runnables>
<Context_window>The maximum size of input a chat model can process.</Context_window>
<Conversation_patterns>Common patterns in chat interactions.</Conversation_patterns>
<Document>LangChain's representation of a document.</Document>
<Embedding_models>Models that generate vector embeddings for various data types.</Embedding_models>
<HumanMessage>Represents a message from a human user.</HumanMessage>
<InjectedState>A state injected into a tool function.</InjectedState>
<InjectedStore>A store that can be injected into a tool for data persistence.</InjectedStore>
<InjectedToolArg>Mechanism to inject arguments into tool functions.</InjectedToolArg>
<input_and_output_types>Types used for input and output in Runnables.</input_and_output_types>
<Integration_packages>Third-party packages that integrate with LangChain.</Integration_packages>
<Integration_tests>Tests that verify the correctness of the interaction between components, usually run with access to the underlying API that powers an integration.</Integration_tests>
<invoke>A standard method to invoke a Runnable.</invoke>
<JSON_mode>Returning responses in JSON format.</JSON_mode>
<langchain_community>Community-driven components for LangChain.</langchain_community>
<langchain_core>Core langchain package. Includes base interfaces and in-memory implementations.</langchain_core>
<langchain>A package for higher level components (e.g., some pre-built chains).</langchain>
<langgraph>Powerful orchestration layer for LangChain. Use to build complex pipelines and workflows.</langgraph>
<langserve>Used to deploy LangChain Runnables as REST endpoints. Uses FastAPI. Works primarily for LangChain Runnables, does not currently integrate with LangGraph.</langserve>
<LLMs_legacy>Older language models that take a string as input and return a string as output.</LLMs_legacy>
<Managing_chat_history>Techniques to maintain and manage the chat history.</Managing_chat_history>
<OpenAI_format>OpenAI's message format for chat models.</OpenAI_format>
<Propagation_of_RunnableConfig>Propagating configuration through Runnables. Read if working with python 3.9, 3.10 and async.</Propagation_of_RunnableConfig>
<rate_limiting>Client side rate limiting for chat models.</rate_limiting>
<RemoveMessage>An abstraction used to remove a message from chat history, used primarily in LangGraph.</RemoveMessage>
<role>Represents the role (e.g., user, assistant) of a chat message.</role>
<RunnableConfig>Use to pass run time information to Runnables (e.g., run_name, run_id, tags, metadata, max_concurrency, recursion_limit, configurable).</RunnableConfig>
<Standard_parameters_for_chat_models>Parameters such as API key, temperature, and max_tokens.</Standard_parameters_for_chat_models>
<Standard_tests>A defined set of unit and integration tests that all integrations must pass.</Standard_tests>
<stream>Use to stream output from a Runnable or a graph.</stream>
<Tokenization>The process of converting data into tokens and vice versa.</Tokenization>
<Tokens>The basic unit that a language model reads, processes, and generates under the hood.</Tokens>
<Tool_artifacts>Add artifacts to the output of a tool that will not be sent to the model, but will be available for downstream processing.</Tool_artifacts>
<Tool_binding>Binding tools to models.</Tool_binding>
<tool_decorator>Decorator for creating tools in LangChain.</tool_decorator>
<Toolkits>A collection of tools that can be used together.</Toolkits>
<ToolMessage>Represents a message that contains the results of a tool execution.</ToolMessage>
<Unit_tests>Tests that verify the correctness of individual components, run in isolation without access to the Internet.</Unit_tests>
<Vector_stores>Datastores specialized for storing and efficiently searching vector embeddings.</Vector_stores>
<with_structured_output>A helper method for chat models that natively support tool calling to get structured output matching a given schema specified via Pydantic, JSON schema or a function.</with_structured_output>
<with_types>Method to overwrite the input and output types of a runnable. Useful when working with complex LCEL chains and deploying with LangServe.</with_types>
</guide_overview>

</glossary>