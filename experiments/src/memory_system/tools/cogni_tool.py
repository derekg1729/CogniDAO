"""
CogniTool: Base class for all Cogni tools with memory linking support.

This class extends the FunctionTool from autogen_core.tools to add memory linking
capabilities and ensure compatibility with MCP, AutoGen, LangChain, and OpenAI.
"""

from typing import Any, Callable, Dict, Optional, Type
from pydantic import BaseModel, ValidationError
from autogen_core.tools import FunctionTool
from langchain.tools import Tool as LangChainTool


class CogniTool(FunctionTool):
    """CogniTool supporting memory-linked or ephemeral actions."""

    def __init__(
        self,
        name: str,
        description: str,
        input_model: Type[BaseModel],
        output_model: Optional[Type[BaseModel]],
        function: Callable[..., Any],  # Allow any callable signature
        memory_linked: bool = True,
    ):
        """
        Initialize a new CogniTool.

        Args:
            name: Name of the tool
            description: Description of what the tool does
            input_model: Pydantic model for input validation
            output_model: Pydantic model for output validation (optional)
            function: Callable that implements the tool's logic
            memory_linked: Whether this tool interacts with the memory system
        """
        # Create the wrapper function
        wrapped_func = self._create_wrapper(function)

        # Initialize parent class
        super().__init__(name=name, func=wrapped_func, description=description)

        # Store additional attributes
        self._input_model = input_model
        self._output_model = output_model
        self._memory_linked = memory_linked
        self._raw_function = function

        # Update schema with memory_linked property and OpenAI compatibility
        self._schema = {
            "name": name,
            "description": description,
            "memory_linked": memory_linked,
            "type": "function",
            "parameters": input_model.model_json_schema(),
            "returns": output_model.model_json_schema() if output_model else None,
        }

    @property
    def schema(self) -> Dict[str, Any]:
        """Get the tool's schema."""
        return self._schema

    @property
    def input_model(self) -> Type[BaseModel]:
        """Get the input model."""
        return self._input_model

    @property
    def output_model(self) -> Optional[Type[BaseModel]]:
        """Get the output model."""
        return self._output_model

    @property
    def memory_linked(self) -> bool:
        """Get whether this tool is memory-linked."""
        return self._memory_linked

    @property
    def raw_function(self) -> Callable[..., Any]:
        """Get the original function."""
        return self._raw_function

    @raw_function.setter
    def raw_function(self, value: Callable[..., Any]) -> None:
        """Set the original function (for testing)."""
        self._raw_function = value

    @raw_function.deleter
    def raw_function(self) -> None:
        """Delete the original function (for testing)."""
        self._raw_function = None

    def _create_wrapper(self, func: Callable[..., Any]) -> Callable[[Dict[str, Any]], Any]:
        """Create a wrapper function that handles input validation and output formatting."""

        def wrapper(kwargs: Dict[str, Any]) -> Any:
            try:
                # Extract memory_bank if present
                memory_bank = kwargs.pop("memory_bank", None) if self.memory_linked else None

                # Validate input
                validated_input = self.input_model(**kwargs)

                # Call function with validated input and memory_bank if needed
                if self.memory_linked and memory_bank is not None:
                    result = func(validated_input, memory_bank)
                else:
                    result = func(validated_input)

                # Validate output if model exists
                if self.output_model:
                    if not isinstance(result, self.output_model):
                        result = self.output_model(**result)
                    # Always convert output model to dict
                    result = result.model_dump()

                return result

            except ValidationError as e:
                return {"error": "Validation error", "details": e.errors(), "success": False}
            except Exception as e:
                return {"error": str(e), "success": False}

        return wrapper

    def __call__(self, **kwargs: Any) -> Any:
        """Enable direct invocation of the tool with kwargs."""
        # Extract memory_bank from kwargs if memory_linked
        memory_bank = kwargs.pop("memory_bank", None) if self.memory_linked else None

        # Create input dict with memory_bank if needed
        input_dict = kwargs
        if memory_bank is not None:
            input_dict["memory_bank"] = memory_bank

        return self._create_wrapper(self.raw_function)(input_dict)

    def as_langchain_tool(self) -> LangChainTool:
        """Convert to a LangChain Tool."""
        return LangChainTool(
            name=self.name,
            description=self.description,
            func=self._create_wrapper(self.raw_function),
            args_schema=self.input_model,
        )

    def openai_schema(self) -> Dict[str, Any]:
        """Return OpenAI function calling schema."""
        schema = {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_model.model_json_schema(),
        }
        if self.output_model:
            schema["returns"] = self.output_model.model_json_schema()
        return schema

    def to_openai_function(self) -> Dict[str, Any]:
        """Alias for openai_schema() for compatibility."""
        return self.openai_schema()

    def to_mcp_route(self) -> Dict[str, Any]:
        """Return MCP-compatible route definition."""
        return {
            "schema": {
                "name": self.name,
                "description": self.description,
                "memory_linked": self.memory_linked,
                "inputSchema": self.input_model.model_json_schema(),
                "outputSchema": self.output_model.model_json_schema()
                if self.output_model
                else None,
            },
            "handler": self._create_wrapper(self.raw_function),
        }
