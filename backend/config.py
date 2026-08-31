import os
import sys
import platform
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


MAIN_GEMINI_MODEL = os.getenv(
    "FRIDAY_MODEL",
    "models/gemini-2.5-flash-native-audio-preview-12-2025",
)
FACT_GEMINI_MODEL = os.getenv("FRIDAY_FACT_MODEL", "models/gemini-3.5-flash-lite")
CAD_GEMINI_MODEL = os.getenv("FRIDAY_CAD_MODEL", "gemini-3-pro-preview")

_SYSTEM = platform.system()  # "Windows" | "Darwin" | "Linux"


def get_os() -> str:
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(_SYSTEM, "linux")


def is_windows() -> bool:
    return _SYSTEM == "Windows"


def is_mac() -> bool:
    return _SYSTEM == "Darwin"


def is_linux() -> bool:
    return _SYSTEM == "Linux"


def get_api_key() -> str:
    """Get the Gemini API key from environment variables."""
    return os.getenv("GEMINI_API_KEY", "")


def get_config_path() -> Path:
    """Get the path to the config/api_keys.json file."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "config" / "api_keys.json"
    return Path(__file__).resolve().parent.parent / "config" / "api_keys.json"


def load_config() -> dict:
    """Load configuration from api_keys.json file."""
    try:
        config_path = get_config_path()
        if config_path.exists():
            return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def get_os_system() -> str:
    """Get the OS system from config or detect from platform."""
    config = load_config()
    return config.get("os_system", get_os()).lower()
