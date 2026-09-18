"""
Code analyst agent for F.R.I.D.A.Y.

Reviews code for quality, security issues, and improvement opportunities.
Publishes findings to the event bus.
"""
from __future__ import annotations

import ast
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CodeAnalystAgent:
    """Analyse code files and directories for quality and security."""

    def __init__(self, event_bus=None):
        self._bus = event_bus

    def _get_bus(self):
        if self._bus is None:
            from event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    def analyse_file(self, file_path: str) -> dict[str, Any]:
        """Analyse a single code file."""
        path = Path(file_path)
        if not path.exists():
            return {"ok": False, "error": f"File not found: {file_path}"}

        content = path.read_text(encoding="utf-8", errors="ignore")
        ext = path.suffix.lower()

        findings: list[dict[str, Any]] = []
        metrics: dict[str, Any] = {
            "lines": len(content.splitlines()),
            "size_bytes": len(content.encode("utf-8")),
            "extension": ext,
        }

        if ext == ".py":
            findings.extend(self._analyse_python(content))
        elif ext in (".js", ".jsx", ".ts", ".tsx"):
            findings.extend(self._analyse_javascript(content))
        elif ext in (".json",):
            findings.extend(self._analyse_json(content))

        result = {
            "ok": True,
            "file": str(path),
            "metrics": metrics,
            "findings": findings,
            "summary": self._summarise(findings),
        }

        if findings:
            self._get_bus().publish_simple("anomaly.detected", {
                "category": "code_quality",
                "file": str(path),
                "findings": findings,
            })
        return result

    def analyse_directory(self, dir_path: str, max_files: int = 50) -> dict[str, Any]:
        """Analyse all code files in a directory."""
        path = Path(dir_path)
        if not path.is_dir():
            return {"ok": False, "error": f"Not a directory: {dir_path}"}

        extensions = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".md"}
        files = [f for f in path.rglob("*") if f.suffix.lower() in extensions and f.is_file()][:max_files]

        results = []
        for f in files:
            try:
                results.append(self.analyse_file(str(f)))
            except Exception:
                continue

        total_findings = sum(len(r.get("findings", [])) for r in results)
        return {
            "ok": True,
            "directory": str(path),
            "files_analysed": len(results),
            "total_findings": total_findings,
            "results": results,
        }

    # ---------- language-specific analysis ----------

    def _analyse_python(self, content: str) -> list[dict[str, Any]]:
        findings = []
        # Check for syntax errors
        try:
            ast.parse(content)
        except SyntaxError as e:
            findings.append({"type": "syntax_error", "severity": "critical",
                             "message": f"Syntax error: {e}"})

        # Check for common issues
        if "import subprocess" in content and "shell=True" in content:
            findings.append({"type": "security", "severity": "warning",
                             "message": "subprocess with shell=True is a security risk"})
        if "eval(" in content:
            findings.append({"type": "security", "severity": "warning",
                             "message": "eval() usage detected — potential code injection"})
        if "except:" in content or "except Exception:" in content:
            findings.append({"type": "quality", "severity": "info",
                             "message": "Bare except clause — consider catching specific exceptions"})

        # Check line lengths
        long_lines = [i + 1 for i, line in enumerate(content.splitlines()) if len(line) > 120]
        if long_lines:
            findings.append({"type": "style", "severity": "info",
                             "message": f"{len(long_lines)} lines exceed 120 characters"})

        return findings

    def _analyse_javascript(self, content: str) -> list[dict[str, Any]]:
        findings = []
        if "eval(" in content:
            findings.append({"type": "security", "severity": "warning",
                             "message": "eval() usage detected"})
        if "innerHTML =" in content:
            findings.append({"type": "security", "severity": "warning",
                             "message": "innerHTML assignment — potential XSS"})
        if "var " in content:
            findings.append({"type": "style", "severity": "info",
                             "message": "Use let/const instead of var"})
        return findings

    def _analyse_json(self, content: str) -> list[dict[str, Any]]:
        findings = []
        import json
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            findings.append({"type": "syntax_error", "severity": "critical",
                             "message": f"Invalid JSON: {e}"})
        return findings

    def _summarise(self, findings: list[dict]) -> str:
        if not findings:
            return "No issues found."
        by_sev: dict[str, int] = {}
        for f in findings:
            by_sev[f.get("severity", "info")] = by_sev.get(f.get("severity", "info"), 0) + 1
        parts = [f"{v} {k}" for k, v in sorted(by_sev.items())]
        return "Found: " + ", ".join(parts)
