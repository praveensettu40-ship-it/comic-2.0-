"""Step 4 - combine images, outline and story into one layout list."""
import re
from typing import Dict, List

from .config import static_url

# Matches a panel header line such as "**Panel 2: Into the Woods**" or "Panel 2 - ..."
PANEL_HEADER = re.compile(r"^[ \t>#*_\-]*panel[ \t]*(\d+)\b[^\n]*$", re.IGNORECASE | re.MULTILINE)
LABEL = re.compile(r"^(caption|narration|dialogue|sfx|sound)[ \t]*:[ \t]*", re.IGNORECASE)


def _clean_body(body: str) -> str:
    """Remove markdown noise and unwanted lines from one panel's text."""
    lines = []
    for raw in body.splitlines():
        line = raw.replace("**", "").replace("__", "").strip()
        line = re.sub(r"^[#>]+\s*", "", line)  # markdown headings / quotes
        line = re.sub(r"^[*\-]\s+", "", line)  # bullet markers
        if not line:
            lines.append("")
            continue
        if re.match(r"^image[ \t]*prompt[ \t]*:", line, re.IGNORECASE):
            continue  # the image prompt is not part of the story text
        match = LABEL.match(line)
        if match:
            label = match.group(1).capitalize()
            line = f"{label}: {line[match.end():]}".strip()
        lines.append(line)

    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _split_story(full_story: str, panel_count: int) -> Dict[int, str]:
    """Return {panel_number: text} using the 'Panel N' headers in the story."""
    story = full_story or ""
    sections: Dict[int, str] = {}

    matches = list(PANEL_HEADER.finditer(story))
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(story)
        number = int(match.group(1))
        sections.setdefault(number, story[match.end():end])

    if sections:
        return {number: _clean_body(body) for number, body in sections.items()}

    # No headers found: spread the paragraphs evenly across the panels.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", story) if p.strip()]
    if not paragraphs or panel_count <= 0:
        return {}
    per_panel = max(1, -(-len(paragraphs) // panel_count))  # ceiling division
    for index in range(panel_count):
        chunk = paragraphs[index * per_panel : (index + 1) * per_panel]
        if chunk:
            sections[index + 1] = _clean_body("\n\n".join(chunk))
    return sections


def build_comic_layout(image_paths: List[str], full_story: str, outline: List[dict]) -> List[dict]:
    """Match every image with its panel story.

    Returns:
        A list of dictionaries with: panel, title, image_path, image_url,
        text and scene_description.
    """
    story_by_panel = _split_story(full_story, len(outline))

    layout = []
    for index, (image_path, panel_info) in enumerate(zip(image_paths, outline), start=1):
        layout.append(
            {
                "panel": index,
                "title": panel_info.get("title", f"Panel {index}"),
                "image_path": str(image_path),
                "image_url": static_url(image_path),
                "text": story_by_panel.get(index, "").strip(),
                "scene_description": panel_info.get("scene_description", ""),
            }
        )
    return layout
