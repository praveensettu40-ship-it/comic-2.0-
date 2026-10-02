"""Step 2 - Gemini Pro writes narration and dialogue for every panel."""
from .config import GEMINI_FALLBACK_MODELS, GEMINI_FLASH_MODEL, GEMINI_PRO_MODEL
from .gemini_client import generate_text

PROMPT_TEMPLATE = """You're a comic book writer.

Given the following panel breakdown, write a comic-style story with engaging narration and character dialogues for each panel.

__CONTEXT__Panel Outline:
__OUTLINE__

Guidelines:
- Use a fun and engaging tone, like an actual comic book.
- Include narration and clearly marked character lines.
- Keep each panel self-contained but part of a cohesive story.
- Write exactly one section per panel, in order.

Use EXACTLY this format for every panel (plain text, no other markdown):

**Panel 1: <title>**
CAPTION: <one short sentence describing the environment or sounds>
NARRATION: <2-3 sentences about the action and emotions>
DIALOGUE: <Character name>: "<what they say>"

**Panel 2: <title>**
...and so on for all panels.
"""


def _format_outline(outline: list) -> str:
    lines = []
    for index, item in enumerate(outline, start=1):
        if isinstance(item, dict):
            number = item.get("panel", index)
            title = item.get("title", "")
            scene = item.get("scene_description", "")
            lines.append(f"{index}. Panel {number}: {title} - {scene}".strip())
        else:
            lines.append(f"{index}. {item}")
    return "\n".join(lines)


def generate_story(outline: list, context: str = "") -> str:
    """Generate a detailed comic story with narration and character dialogue.

    Args:
        outline: The panel list returned by generate_outline().
        context: Optional original user request (character, tone, setting, style)
                 so the story stays consistent with it.

    Returns:
        The full story as one formatted text block.

    Raises:
        RuntimeError: if Gemini cannot be reached or returns nothing.
    """
    context_block = f"Story request: {context}\n\n" if context else ""
    prompt = PROMPT_TEMPLATE.replace("__CONTEXT__", context_block).replace(
        "__OUTLINE__", _format_outline(outline)
    )
    models = [GEMINI_PRO_MODEL, GEMINI_FLASH_MODEL, *GEMINI_FALLBACK_MODELS]
    return generate_text(prompt, models, json_mode=False, temperature=0.9)
