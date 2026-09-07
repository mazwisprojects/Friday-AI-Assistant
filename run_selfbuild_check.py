"""Definitive check: run the exact test leg that self_build/self_heal run."""
import sys

sys.path.insert(0, "backend")
from actions import self_maintenance as sm  # noqa: E402

result = sm.run_backend_tests()
print("=== SELF_BUILD_TEST_LEG ===")
print("ok:", result.get("ok"))
print("issues:", result.get("issues"))
stdout = result.get("stdout") or ""
stderr = result.get("stderr") or ""
print("--- stdout tail ---")
print(stdout[-1200:])
if stderr.strip():
    print("--- stderr tail ---")
    print(stderr[-600:])
print("=== END ===")