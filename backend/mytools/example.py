"""Reference format for a Friday-generated custom tool.

Friday creates one module per verified tool in this directory. Runtime execution
still goes through backend/tool_builder.py and its approved operation templates.
"""

TOOL_MANIFEST = {
    "name": "example_tool",
    "description": "Example verified custom tool manifest.",
    "operation": "http_json_get",
    "parameters": {
        "query": {"type": "STRING", "description": "Optional query value."}
    },
    "config": {
        "url": "https://example.com/api?query={query}"
    }
}


def describe():
    return TOOL_MANIFEST.copy()