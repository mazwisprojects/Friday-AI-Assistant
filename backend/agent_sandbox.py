"""Static sandbox policy for generated Python agents."""

from __future__ import annotations

import ast
import logging

logger = logging.getLogger(__name__)


# NO BLOCKED IMPORTS - Friday can use ANY module
# NO BLOCKED CALLS - Friday can call ANY function
# User takes responsibility for what they build

BLOCKED_IMPORTS: set[str] = set()
BLOCKED_CALLS: set[str] = set()


def validate_source(source: str) -> None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BLOCKED_IMPORTS:
                    raise ValueError(f"Agent sandbox rejected import: {alias.name}")
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in BLOCKED_IMPORTS:
            raise ValueError(f"Agent sandbox rejected import: {node.module}")
        elif isinstance(node, ast.Call):
            function_name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if function_name in BLOCKED_CALLS:
                raise ValueError(f"Agent sandbox rejected call: {function_name}")
