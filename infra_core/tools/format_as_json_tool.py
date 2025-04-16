import json
from typing_extensions import Annotated
from autogen_core.tools import FunctionTool

def format_as_json(content_summary: Annotated[str, "Summary to wrap in structured JSON."]) -> str:
    return json.dumps({"content_summary": content_summary}, indent=2)

format_as_json_tool = FunctionTool(
    func=format_as_json,
    description="Formats the provided summary into a structured JSON format with key 'content_summary'."
)

# Fix schema for OpenAI by adding type field
schema = format_as_json_tool.schema
schema["type"] = "function"
