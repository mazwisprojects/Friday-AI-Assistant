"""Static sandbox policy for generated Python agents."""

from __future__ import annotations

import ast


BLOCKED_IMPORTS = {"subprocess", "socket", "ctypes", "winreg", "shutil"}
BLOCKED_CALLS = {"eval", "exec", "compile", "open", "system", "Popen", "run"}


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
