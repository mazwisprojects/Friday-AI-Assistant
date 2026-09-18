"""
Security analyst agent for F.R.I.D.A.Y.

Scans for exposed credentials, insecure configurations, and known
vulnerability patterns. Publishes findings to the event bus.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Patterns that indicate exposed secrets
SECRET_PATTERNS = [
    (r'(?i)(api_key|apikey|api-key)\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}["\']', "Exposed API key"),
    (r'(?i)(password|passwd|pwd)\s*[:=]\s*["\'][^"\']{4,}["\']', "Hardcoded password"),
    (r'(?i)(secret|token)\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}["\']', "Exposed secret/token"),
    (r'(?i)-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----', "Exposed private key"),
    (r'(?i)AKIA[0-9A-Z]{16}', "AWS access key ID"),
    (r'(?i)ghp_[A-Za-z0-9]{36}', "GitHub personal access token"),
]

# Files that should never contain secrets
SENSITIVE_FILES = {".env", ".env.local", ".env.production", "id_rsa", "id_ecdsa", ".npmrc", ".pypirc"}


class SecurityAnalystAgent:
    """Scan for security issues in the workspace."""

    def __init__(self, event_bus=None):
        self._bus = event_bus

    def _get_bus(self):
        if self._bus is None:
            from event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    def scan_file(self, file_path: str) -> dict[str, Any]:
        """Scan a single file for security issues."""
        path = Path(file_path)
        if not path.exists():
            return {"ok": False, "error": f"File not found: {file_path}"}

        findings: list[dict[str, Any]] = []
        name = path.name.lower()

        # Check if sensitive file is committed
        if name in SENSITIVE_FILES:
            findings.append({
                "type": "sensitive_file", "severity": "critical",
                "message": f"{path.name} should not be committed to version control",
            })

        # Scan content
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            content = ""

        for pattern, description in SECRET_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                findings.append({
                    "type": "exposed_secret", "severity": "critical",
                    "message": f"{description} ({len(matches)} occurrence(s))",
                })

        result = {
            "ok": True, "file": str(path),
            "findings": findings,
            "risk_score": self._risk_score(findings),
        }

        if findings:
            self._get_bus().publish_simple("anomaly.detected", {
                "category": "security",
                "file": str(path),
                "findings": findings,
            })
        return result

    def scan_directory(self, dir_path: str, max_files: int = 100) -> dict[str, Any]:
        """Scan a directory for security issues."""
        path = Path(dir_path)
        if not path.is_dir():
            return {"ok": False, "error": f"Not a directory: {dir_path}"}

        extensions = {".py", ".js", ".ts", ".json", ".env", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".md"}
        files = [f for f in path.rglob("*") if f.suffix.lower() in extensions and f.is_file()][:max_files]

        # Exclude common non-project dirs
        skip_dirs = {".git", "node_modules", "__pycache__", ".pytest_cache", "venv", ".venv", "dist", "build"}
        files = [f for f in files if not any(sd in f.parts for sd in skip_dirs)]

        results = []
        for f in files:
            try:
                r = self.scan_file(str(f))
                if r.get("findings"):
                    results.append(r)
            except Exception:
                continue

        total_findings = sum(len(r.get("findings", [])) for r in results)
        return {
            "ok": True, "directory": str(path),
            "files_scanned": len(files), "files_with_issues": len(results),
            "total_findings": total_findings, "results": results,
        }

    def check_open_ports(self, ports: list[int] | None = None) -> dict[str, Any]:
        """Check for potentially risky open ports."""
        import socket
        if ports is None:
            ports = [22, 80, 443, 3306, 5432, 6379, 8000, 8080, 9000]
        open_ports = []
        for port in ports:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    open_ports.append(port)
            except (OSError, socket.timeout):
                continue
        return {"ok": True, "open_ports": open_ports, "checked": ports}

    @staticmethod
    def _risk_score(findings: list[dict]) -> int:
        scores = {"critical": 40, "warning": 15, "info": 3}
        return min(100, sum(scores.get(f.get("severity", "info"), 0) for f in findings))
