import platform

_SYSTEM = platform.system()  # "Windows" | "Darwin" | "Linux"


def get_os() -> str:
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(_SYSTEM, "linux")


def is_windows() -> bool:
    return _SYSTEM == "Windows"


def is_mac() -> bool:
    return _SYSTEM == "Darwin"


def is_linux() -> bool:
    return _SYSTEM == "Linux"
