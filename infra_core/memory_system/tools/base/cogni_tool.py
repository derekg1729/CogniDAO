"""
CogniTool: Base class for all Cogni tools with memory linking support.

This class extends the FunctionTool from autogen_core.tools to add memory linking
capabilities and ensure compatibility with MCP, AutoGen, LangChain, and OpenAI.
"""

from typing import Any, Callable, Dict, Optional, Type, get_type_hints
from pydantic import BaseModel, ValidationError, Field
from pydantic.v1 import BaseModel as V1BaseModel
from autogen_core.tools import FunctionTool
from langchain.tools import Tool as LangChainTool
import logging

logger = logging.getLogger(__name__)


def convert_to_v1_model(v2_model: Type[BaseModel]) -> Type[V1BaseModel]:
    """Convert a Pydantic v2 model to v1 format."""
    # Get type hints and field info from v2 model
    type_hints = get_type_hints(v2_model)
    fields = {}

    # Create field definitions for v1 model
    for field_name, field in v2_model.model_fields.items():
        field_type = type_hints.get(field_name, Any)
        fields[field_name] = (
            field_type,
            Field(
                default=... if field.is_required() else None,
                description=field.description,
            ),
        )

    # Create v1 model dynamically
    v1_model = type(
        v2_model.__name__,
        (V1BaseModel,),
        {
            "__annotations__": type_hints,
            "__module__": v2_model.__module__,
            **{k: v[1] for k, v in fields.items()},
        },
    )

    # Copy over class attributes to make it look like the original
    v1_model.__qualname__ = v2_model.__qualname__
    v1_model.__name__ = v2_model.__name__

    return v1_model


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
                if self.output_model and not isinstance(result, self.output_model):
                    result = self.output_model(**result)

                return result

            except ValidationError as e:
                # Always return a dict for input validation errors
                return {
                    "error": "Validation error",
                    "details": e.errors(),
                    "success": False,
                }
            except Exception as e:
                if self.output_model:
                    # For general exceptions, try to use the output model if available
                    # Ensure all required fields for the error state are provided
                    error_data = {"error": str(e), "success": False}
                    # Attempt to fill missing required fields with defaults or None
                    # This part might need refinement based on specific output model needs
                    for field_name, field_info in self.output_model.model_fields.items():
                        if field_info.is_required() and field_name not in error_data:
                            # A simple default, might need smarter logic
                            error_data[field_name] = None
                    try:
                        return self.output_model(**error_data)
                    except ValidationError:
                        # Fallback if creating output model still fails
                        return {"error": str(e), "success": False}
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

    def as_langchain_tool(self, *, memory_bank=None) -> LangChainTool:
        """Convert to a LangChain Tool.

        This method creates a LangChain Tool that properly handles memory bank injection
        from CrewAI's external_memory. The tool will:
        1. Extract memory_bank from kwargs if present
        2. Validate input using the tool's input model
        3. Call the underlying function with memory_bank if memory_linked
        4. Format the output according to the tool's output model

        Args:
            memory_bank: Optional memory bank to use for this tool instance

        Returns:
            LangChainTool: A LangChain-compatible tool instance
        """

        def langchain_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper for LangChain tool interface."""
            try:
                # Convert positional args to tool_input
                if len(args) == 1:
                    if isinstance(args[0], (str, dict)):
                        tool_input = args[0]
                    else:
                        raise ValueError("Tool only accepts string or dict input")
                elif len(args) > 1:
                    raise ValueError("Tool only accepts a single argument")
                else:
                    tool_input = kwargs

                # Extract memory bank from tool_input if it's a dict
                tool_memory_bank = None
                if isinstance(tool_input, dict):
                    tool_memory_bank = tool_input.pop("memory_bank", None)

                # 1) memory_bank priority: explicit kwarg → captured param → tool_input memory_bank
                mem_from_kwargs = kwargs.pop("memory_bank", None)
                final_memory_bank = mem_from_kwargs or memory_bank or tool_memory_bank

                if self.memory_linked and final_memory_bank is None:
                    raise ValueError(
                        "memory_bank must be supplied when tool is instantiated or called"
                    )

                # Create kwargs dict with memory_bank if needed
                tool_kwargs = {}
                if final_memory_bank is not None:
                    tool_kwargs["memory_bank"] = final_memory_bank

                # Call the tool with the input and memory bank
                if isinstance(tool_input, str):
                    # Map single string to first input_model field
                    field_name = list(self.input_model.model_fields.keys())[0]
                    tool_input = {field_name: tool_input}
                    result = self(**{**tool_input, **tool_kwargs})
                else:
                    result = self(**{**tool_input, **tool_kwargs})

                # Validate output model if specified
                if self.output_model:
                    result = self.output_model.model_validate(result)
                return result

            except Exception as e:
                logger.error(f"Error in {self.name}: {str(e)}", exc_info=True)
                return {"success": False, "error": str(e)}

        # Convert input model to v1 format for LangChain compatibility
        v1_input_model = convert_to_v1_model(self.input_model)

        return LangChainTool(
            name=self.name,
            description=self.description,
            func=langchain_wrapper,
            args_schema=v1_input_model,
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
