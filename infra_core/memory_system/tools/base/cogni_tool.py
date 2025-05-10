"""
CogniTool: Base class for all Cogni tools with memory linking support.

Originally this module relied on *FunctionTool* from *autogen_core* and embedded
framework-specific helpers.  It has been rewritten to be **completely
framework-agnostic**.  The class now focuses solely on:

1. Input validation
2. Output validation/formatting
3. Optional memory-bank dispatch
4. JSON-schema exposure for the Model Context Protocol (MCP)

Individual adapter modules (e.g. for LangChain, AutoGen, CrewAI) can extend or
monkey-patch `CogniTool` instances as needed without polluting the core class.
"""

from typing import Any, Callable, Dict, Optional, Type, get_type_hints
from pydantic import BaseModel, ValidationError, Field
from pydantic.v1 import BaseModel as V1BaseModel
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def convert_to_v1_model(v2_model: Type[BaseModel]) -> Type[V1BaseModel]:
    """Convert a Pydantic v2 model to v1 format."""
    # Get type hints and field info from v2 model
    type_hints = get_type_hints(v2_model)
    fields = {}

    # Create field definitions for v1 model
    for field_name, field in v2_model.model_fields.items():
        field_type = type_hints.get(field_name, Any)

        # Handle nested Pydantic models
        if isinstance(field_type, type) and issubclass(field_type, BaseModel):
            field_type = convert_to_v1_model(field_type)

        # Create field with validation
        field_kwargs = {
            "default": ... if field.is_required() else None,
            "description": field.description,
        }

        # Add validation constraints
        if hasattr(field, "ge"):
            field_kwargs["ge"] = field.ge
        if hasattr(field, "le"):
            field_kwargs["le"] = field.le
        if hasattr(field, "gt"):
            field_kwargs["gt"] = field.gt
        if hasattr(field, "lt"):
            field_kwargs["lt"] = field.lt

        fields[field_name] = (field_type, Field(**field_kwargs))

    # Create v1 model dynamically with arbitrary_types_allowed=True
    class Config:
        arbitrary_types_allowed = True

    v1_model = type(
        v2_model.__name__,
        (V1BaseModel,),
        {
            "__annotations__": type_hints,
            "__module__": v2_model.__module__,
            "Config": Config,
            **{k: v[1] for k, v in fields.items()},
        },
    )

    # Copy over class attributes to make it look like the original
    v1_model.__qualname__ = v2_model.__qualname__
    v1_model.__name__ = v2_model.__name__

    return v1_model


class CogniTool:
    """Framework-agnostic base class for Cogni tools.

    Responsibilities:
        1. Rigid input validation using a Pydantic v2 model
        2. Optional output validation using a Pydantic v2 model
        3. Dispatch to the underlying callable, optionally injecting ``memory_bank``
        4. Expose an MCP-compatible schema via :py:meth:`to_mcp_route`

    The class purposefully avoids inheriting from — or even importing — any
    third-party tool abstractions (e.g. LangChain, AutoGen, CrewAI). Framework
    adapters must live in *separate* modules and may choose to monkey-patch a
    CogniTool instance at runtime.  This keeps the core class lightweight and
    fully testable without heavyweight dependencies.
    """

    # ---------------------------------------------------------------------
    # Construction helpers
    # ---------------------------------------------------------------------
    def __init__(
        self,
        *,
        name: str,
        description: str,
        input_model: Type[BaseModel],
        output_model: Optional[Type[BaseModel]] = None,
        function: Callable[..., Any],
        memory_linked: bool = True,
    ) -> None:
        self.name = name
        self.description = description
        self.input_model = input_model
        self.output_model = output_model
        self.memory_linked = memory_linked
        self._function = function

        # Pre-compute JSON schemas once – they are immutable after construction
        self._schema: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "memory_linked": self.memory_linked,
            "type": "function",
            "parameters": self.input_model.model_json_schema(),
            "returns": self.output_model.model_json_schema() if self.output_model else None,
        }

    # ------------------------------------------------------------------
    #  Primary call interface
    # ------------------------------------------------------------------
    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # noqa: C901 (complexity)
        """Invoke the tool.

        Accepted calling patterns (in order of precedence):

        1. ``tool(<InputModel instance>, memory_bank=...)``
        2. ``tool(<dict>, memory_bank=...)``
        3. ``tool(field1=value1, field2=value2, ..., memory_bank=...)``

        For convenience, *one* lone scalar positional argument is also allowed
        if the input model has exactly one field. This is handy for simple
        tools that take a single ``text`` string, for example.
        """

        memory_bank = kwargs.pop("memory_bank", None)

        # ------------------------------------------------------------------
        # Coerce *args / **kwargs into a validated ``input_model`` instance
        # ------------------------------------------------------------------
        try:
            if args and len(args) > 1:
                raise ValueError("CogniTool accepts at most one positional argument.")

            if args:
                first = args[0]
                if isinstance(first, self.input_model):
                    validated_input = first
                elif isinstance(first, dict):
                    validated_input = self.input_model(**first)
                else:
                    # Allow scalar positional when model has exactly one field
                    fields = list(self.input_model.model_fields.keys())
                    if len(fields) != 1:
                        raise TypeError(
                            "Positional value only supported if input model has a single field."  # noqa: E501
                        )
                    validated_input = self.input_model(**{fields[0]: first})
            else:
                # No positional – use kwargs (memory_bank already popped)
                validated_input = self.input_model(**kwargs)
        except ValidationError as e:
            return self._error_response("Validation error", e)
        except Exception as e:
            return self._error_response(str(e))

        # ------------------------------------------------------------------
        # Ensure memory bank presence for memory-linked tools
        # ------------------------------------------------------------------
        if self.memory_linked and memory_bank is None:
            return self._error_response(
                "memory_bank must be supplied when calling a memory-linked tool"
            )

        # ------------------------------------------------------------------
        # Delegate to underlying callable
        # ------------------------------------------------------------------
        try:
            if self.memory_linked:
                result = self._function(validated_input, memory_bank)
            else:
                result = self._function(validated_input)

            # ------------------------------------------------------------------
            # Output validation / coercion
            # ------------------------------------------------------------------
            if self.output_model is None:
                return result

            if isinstance(result, self.output_model):
                return result

            # Attempt to coerce mapping / object into output model
            return self.output_model(**result)  # type: ignore[arg-type]

        except ValidationError as e:
            # Output failed model validation
            return self._error_response("Output validation failed", e)
        except Exception as e:  # noqa: BLE001 (broad-exception-caught)
            # Unhandled runtime error from the underlying function
            return self._error_response(str(e))

    # ------------------------------------------------------------------
    #  Metadata helpers
    # ------------------------------------------------------------------
    @property
    def schema(self) -> Dict[str, Any]:
        """Return the cached JSON schema for the tool."""

        return self._schema

    def openai_schema(self) -> Dict[str, Any]:
        """Return a schema that matches OpenAI function-calling format."""

        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_model.model_json_schema(),
            "returns": self.output_model.model_json_schema() if self.output_model else None,
        }

    def to_openai_function(self) -> Dict[str, Any]:  # Backwards compatibility alias
        return self.openai_schema()

    # ------------------------------------------------------------------
    #  MCP integration
    # ------------------------------------------------------------------
    def to_mcp_route(self) -> Dict[str, Any]:
        """Return an MCP-compatible route definition."""

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
            "handler": self,  # The instance itself is callable and encapsulates validation
        }

    # ------------------------------------------------------------------
    #  Internal utilities
    # ------------------------------------------------------------------
    def _error_response(self, message: str, exc: Optional[Exception] = None) -> Any:
        """Build a structured error response.

        If an ``output_model`` is supplied, attempt to coerce a minimal error-shaped
        object into that model. Otherwise, return a plain dict.
        """

        base: Dict[str, Any] = {
            "success": False,
            "error": f"{message}: {str(exc)}" if exc else message,
            "timestamp": datetime.now(),
        }

        if self.output_model is None:
            return base

        # Fill missing required fields with None so model construction succeeds
        for field_name, field_info in self.output_model.model_fields.items():
            if field_info.is_required() and field_name not in base:
                base[field_name] = None

        try:
            return self.output_model(**base)  # type: ignore[arg-type]
        except ValidationError:
            # Fallback to raw dict if even this fails
            return base
