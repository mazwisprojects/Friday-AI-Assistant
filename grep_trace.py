import logging

logger = logging.getLogger(__name__)

try:
    lines = []
    with open("trace.txt", "r", encoding="utf-16le") as f:
        lines = f.readlines()
except Exception as e:
    logger.warning("Failed to read with utf-16le encoding: %s", e)
    try:
        with open("trace.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error("Failed to read with utf-8 encoding: %s", e)
        exit()

for i, line in enumerate(lines):
    if "AttributeError" in line:
        start = max(0, i - 10)
        end = min(len(lines), i + 10)
        logger.info("Match at line %d", i + 1)
        print("".join(lines[start:end]))
