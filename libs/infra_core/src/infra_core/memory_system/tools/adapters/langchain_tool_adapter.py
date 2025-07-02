"""LangChain adapter for CogniTool.

This module **monkey-patches** :class:`~infra_core.memory_system.tools.base.cogni_tool.CogniTool`
with an ``as_langchain_tool`` method.  Keeping this logic in a dedicated adapter
module ensures the *core* `CogniTool` class remains free of heavyweight
framework dependencies, aligning with the design goals of minimalism and
portability.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from langchain.tools import Tool as LangChainTool
from pydantic import ValidationError

from infra_core.memory_system.tools.base.cogni_tool import CogniTool, convert_to_v1_model

logger = logging.getLogger(__name__)


def _as_langchain_tool(self: CogniTool, *, memory_bank=None) -> LangChainTool:  # noqa: D401
    """Convert *self* into a LangChain :class:`Tool` instance.

    The generated tool:
    1. Accepts either JSON-serialised strings or dictionaries as input
    2. Performs strict input / output validation via the underlying CogniTool
    3. Injects a *memory_bank* argument when required
    """

    def _wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: D401
        try:
            # ------------------------------------------------------------------
            # Parse *args* – LangChain always passes a *single* positional arg.
            # ------------------------------------------------------------------
            if len(args) == 1:
                first = args[0]
                if isinstance(first, str):
                    try:
                        tool_input = json.loads(first)
                    except json.JSONDecodeError:
                        # Map scalar string to the first field of the input model
                        single_field = list(self.input_model.model_fields.keys())[0]
                        tool_input = {single_field: first}
                elif isinstance(first, dict):
                    tool_input = first
                else:
                    raise ValueError("Tool only accepts a JSON string or dict as positional input.")
            elif len(args) > 1:
                raise ValueError("Tool only accepts a single positional argument.")
            else:
                tool_input = kwargs

            # ------------------------------------------------------------------
            # Memory-bank resolution precedence:
            # 1. Explicit kwarg when *wrapper* invoked
            # 2. Static *memory_bank* captured from closure
            # 3. "memory_bank" key inside *tool_input*
            # ------------------------------------------------------------------
            mb_from_kwargs = kwargs.pop("memory_bank", None)
            mb_from_input = (
                tool_input.pop("memory_bank", None) if isinstance(tool_input, dict) else None
            )
            final_mb = mb_from_kwargs or memory_bank or mb_from_input

            if self.memory_linked and final_mb is None:
                raise ValueError("memory_bank must be supplied when invoking a memory-linked tool.")

            if final_mb is not None:
                tool_input["memory_bank"] = final_mb

            result = self(**tool_input)
            # Ensure the result is a JSON string if it's a Pydantic model or dict
            if hasattr(result, "model_dump_json"):  # Pydantic V2
                return result.model_dump_json()
            elif hasattr(result, "json"):  # Pydantic V1 (fallback)
                return result.json()
            elif isinstance(result, dict):
                return json.dumps(result)
            return result

        except Exception as e:  # noqa: BLE001 (broad-exception-caught)
            logger.error(
                "Error inside LangChain adapter for %s: %s", self.name, str(e), exc_info=True
            )
            if self.output_model:
                base_error = {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(),
                }
                # Fill in required fields with ``None`` so model instantiation succeeds
                for field_name, field_info in self.output_model.model_fields.items():
                    if field_info.is_required() and field_name not in base_error:
                        base_error[field_name] = None
                try:
                    return self.output_model(**base_error)
                except ValidationError:
                    return base_error
            return {"success": False, "error": str(e), "timestamp": datetime.now()}

    # ------------------------------------------------------------------
    # Build the LangChain ``Tool``
    # ------------------------------------------------------------------
    v1_input_model = convert_to_v1_model(self.input_model)

    return LangChainTool(
        name=self.name,
        description=self.description,
        func=_wrapper,
        args_schema=v1_input_model,
    )


# ----------------------------------------------------------------------
# Attach the adapter method to *CogniTool*
# ----------------------------------------------------------------------

setattr(CogniTool, "as_langchain_tool", _as_langchain_tool)
