import os
import platform
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
