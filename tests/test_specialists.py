"""Tests for specialist analysis agents."""
import os
import pytest
import tempfile
from pathlib import Path
from backend.agents.specialists.code_analyst import CodeAnalystAgent
from backend.agents.specialists.security_analyst import SecurityAnalystAgent
from backend.agents.specialists.system_analyst import SystemAnalystAgent


class TestCodeAnalystAgent:
    def test_analyse_python_file(self):
        agent = CodeAnalystAgent()
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("import os\nprint('hello')\n")
            f.flush()
            result = agent.analyse_file(f.name)
        assert result["ok"] is True
        assert result["metrics"]["lines"] == 2

    def test_analyse_python_with_issues(self):
        agent = CodeAnalystAgent()
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("import subprocess\nsubprocess.run('ls', shell=True)\nexcept: pass\n")
            f.flush()
            result = agent.analyse_file(f.name)
        assert result["ok"] is True
        assert len(result["findings"]) > 0

    def test_analyse_nonexistent_file(self):
        agent = CodeAnalystAgent()
        result = agent.analyse_file("/nonexistent/file.py")
        assert result["ok"] is False

    def test_analyse_syntax_error(self):
        agent = CodeAnalystAgent()
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def broken(\n")
            f.flush()
            result = agent.analyse_file(f.name)
        assert result["ok"] is True
        assert any(f["type"] == "syntax_error" for f in result["findings"])


class TestSecurityAnalystAgent:
    def test_scan_file_with_secret(self):
        agent = SecurityAnalystAgent()
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write('api_key = "sk-1234567890abcdef1234567890abcdef"\n')
            f.flush()
            result = agent.scan_file(f.name)
        assert result["ok"] is True
        assert len(result["findings"]) > 0
        assert result["risk_score"] > 0

    def test_scan_file_clean(self):
        agent = SecurityAnalystAgent()
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("print('hello world')\n")
            f.flush()
            result = agent.scan_file(f.name)
        assert result["ok"] is True
        assert len(result["findings"]) == 0

    def test_scan_nonexistent_file(self):
        agent = SecurityAnalystAgent()
        result = agent.scan_file("/nonexistent/file.py")
        assert result["ok"] is False

    def test_sensitive_file_detected(self):
        agent = SecurityAnalystAgent()
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = os.path.join(tmpdir, ".env")
            with open(env_file, "w") as f:
                f.write("DB_HOST=localhost\n")
            result = agent.scan_file(env_file)
        assert any(f["type"] == "sensitive_file" for f in result["findings"])

    def test_risk_score_calculation(self):
        assert SecurityAnalystAgent._risk_score([]) == 0
        assert SecurityAnalystAgent._risk_score([{"severity": "critical"}]) == 40


class TestSystemAnalystAgent:
    def test_healthy_system(self):
        agent = SystemAnalystAgent()
        result = agent.check_health(cpu_percent=30, ram_percent=40)
        assert result["healthy"] is True
        assert len(result["findings"]) == 0

    def test_high_cpu(self):
        agent = SystemAnalystAgent()
        result = agent.check_health(cpu_percent=95, ram_percent=40)
        assert result["healthy"] is False
        assert any(f["type"] == "cpu_high" for f in result["findings"])

    def test_high_ram(self):
        agent = SystemAnalystAgent()
        result = agent.check_health(cpu_percent=30, ram_percent=95)
        assert result["healthy"] is False
        assert any(f["type"] == "ram_high" for f in result["findings"])

    def test_high_temperature(self):
        agent = SystemAnalystAgent()
        result = agent.check_health(cpu_percent=50, ram_percent=50, cpu_temp=90)
        assert any(f["type"] == "temp_high" for f in result["findings"])

    def test_record_sample(self):
        agent = SystemAnalystAgent()
        agent.record_sample(50.0, 60.0)
        history = agent.get_history()
        assert len(history["cpu"]) == 1
        assert len(history["ram"]) == 1

    def test_trend_analysis(self):
        agent = SystemAnalystAgent()
        for v in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            agent.record_sample(v, 50)
        trends = agent._analyse_trends()
        assert trends.get("cpu_increasing") is True
