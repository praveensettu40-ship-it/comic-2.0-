"""Step 1 - Gemini Flash creates a structured 5-panel comic outline."""
import json
import re
from typing import List

from .config import GEMINI_FALLBACK_MODELS, GEMINI_FLASH_MODEL
from .gemini_client import generate_text

NUM_PANELS = 5

PROMPT_TEMPLATE = """You are a professional AI comic planner.

Your task is to generate a *strictly formatted* JSON array containing exactly 5 panel descriptions for a comic based on the story idea below.

STORY: "__USER_PROMPT__"

Each JSON object must include:
- "panel" (integer, 1 to 5)
- "title" (string, short)
- "scene_description" (string, 1-2 sentences describing what happens)
- "image_prompt" (string, a detailed visual description for Stable Diffusion: subject, setting, lighting, mood, art style. Do not ask for text or speech bubbles in the image.)

Respond ONLY with valid JSON in this format, without explanations or markdown:
[
  {
    "panel": 1,
    "title": "Title here",
    "scene_description": "Scene description here",
    "image_prompt": "Image prompt for Stable Diffusion"
  }
]
"""


def _extract_json_array(text: str) -> list:
    """Parse a JSON array even if the model wrapped it in markdown fences."""
    cleaned = text.strip()
    cleaned = re.sub(r"^\s*```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON array found in the Gemini response.")
    return json.loads(cleaned[start : end + 1])


def _normalise(panel_data: list) -> List[dict]:
    """Validate the structure and return clean, renumbered panels."""
    if not isinstance(panel_data, list) or not panel_data:
        raise ValueError("Gemini response is not a non-empty list.")

    panels = []
    for index, item in enumerate(panel_data[:NUM_PANELS], start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid panel format: {item!r}")

        scene = str(item.get("scene_description", "")).strip()
        image_prompt = str(item.get("image_prompt", "")).strip() or scene
        if not image_prompt:
            raise ValueError(f"Panel {index} has no image_prompt or scene_description.")

        panels.append(
            {
                "panel": index,
                "title": str(item.get("title", "")).strip() or f"Panel {index}",
                "scene_description": scene,
                "image_prompt": image_prompt,
            }
        )
    return panels


def generate_outline(user_prompt: str) -> list:
    """Generate a 5-panel comic layout based on the user's story idea using Gemini.

    Args:
        user_prompt: The user's comic idea (already combined with character, setting, tone, style).

    Returns:
        A list of dictionaries, one per panel, each with the keys
        "panel", "title", "scene_description" and "image_prompt".

    Raises:
        RuntimeError: if Gemini cannot be reached or never returns valid JSON.
    """
    prompt = PROMPT_TEMPLATE.replace("__USER_PROMPT__", user_prompt.replace('"', "'"))
    models = [GEMINI_FLASH_MODEL, *GEMINI_FALLBACK_MODELS]

    last_error = None
    for attempt in (1, 2):
        output_text = ""
        try:
            output_text = generate_text(prompt, models, json_mode=True, temperature=0.8)
            print(f"\n[Gemini Flash] raw response (attempt {attempt}):\n{output_text}\n")
            return _normalise(_extract_json_array(output_text))
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"[Gemini Flash] could not parse response: {exc}\n{output_text}")
            last_error = exc

    raise RuntimeError(f"Gemini did not return a valid comic outline: {last_error}")
