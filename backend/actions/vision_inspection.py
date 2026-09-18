"""Direct OCR/description of the current camera or screen frame."""
from __future__ import annotations

import io
import os


def inspect_image_bytes(image_bytes: bytes, instruction: str = "") -> dict:
    if not image_bytes:
        return {"ok": False, "error": "No current visual frame is available."}
    try:
        from PIL import Image
        from google import genai

        image = Image.open(io.BytesIO(image_bytes))
        prompt = instruction.strip() or (
            "Inspect this current visual frame. Extract any visible text exactly, then briefly describe "
            "important objects, interface elements, and warnings. Do not invent details."
        )
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model=os.getenv("FRIDAY_VISION_MODEL", "gemini-3.6-flash"),
            contents=[prompt, image],
        )
        return {"ok": True, "text": (response.text or "").strip(), "source": "current_visual_frame"}
    except Exception as exc:
        return {"ok": False, "error": f"Visual inspection failed: {exc}"}
