"""All FastAPI routes for ComicCraft.

Route handlers are plain `def` functions (not `async def`) on purpose:
comic generation is slow and blocking, and FastAPI runs plain `def` handlers
in a worker thread so the server stays responsive.
"""
import traceback
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import GEMINI_API_KEY, TEMPLATES_DIR, USE_PLACEHOLDER_IMAGES, static_url
from .exporters import save_pdf
from .gemini_flash import generate_outline
from .gemini_pro import generate_story
from .image_generator import generate_image, pop_image_warning
from .layout_builder import build_comic_layout
from .schemas import PromptRequest

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

SETTINGS = ["Forest", "School", "Space", "City"]
TONES = ["Light-hearted", "Dramatic", "Poetic", "Funny"]
STYLES = ["Anime", "Pixel art", "Comic book", "Realistic"]

DEFAULT_FORM = {
    "prompt": "A brave fox explores an enchanted forest.",
    "character_name": "Free",
    "setting": "Forest",
    "tone": "Dramatic",
    "style": "Realistic",
}


# --------------------------------------------------------------------------- #
# shared logic
# --------------------------------------------------------------------------- #
def _create_comic(prompt: str, character_name: str, setting: str, tone: str, style: str) -> dict:
    """Run the full pipeline: outline -> story -> images -> layout -> PDF."""
    full_prompt = (
        f"{prompt}\n"
        f"The main character is {character_name}. "
        f"The setting is a {setting}. "
        f"The tone is {tone}. The art style is {style}."
    )

    # Step 1: panel outline (Gemini Flash)
    outline = generate_outline(full_prompt)
    if not isinstance(outline, list) or not all("image_prompt" in panel for panel in outline):
        raise ValueError("Invalid outline structure from Gemini response.")

    # Step 2: narration + dialogue (Gemini Pro)
    full_story = generate_story(outline, context=full_prompt)

    # Step 3: one image per panel (Stable Diffusion)
    images = []
    for panel in outline:
        image_prompt = f"{panel['image_prompt']}, {style} style, comic book panel illustration, highly detailed"
        images.append(generate_image(image_prompt))

    # Step 4: layout
    layout = build_comic_layout(images, full_story, outline)

    # Step 5: PDF
    pdf_path = save_pdf(layout)

    return {
        "layout": layout,
        "pdf_url": static_url(pdf_path),
        "warning": pop_image_warning(),
    }


def _render_index(request: Request, form: dict, error: Optional[str] = None, status_code: int = 200):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "settings": SETTINGS,
            "tones": TONES,
            "styles": STYLES,
            "form": form,
            "error": error,
        },
        status_code=status_code,
    )


# --------------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------------- #
@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Homepage with the story form."""
    return _render_index(request, DEFAULT_FORM)


@router.post("/generate", response_class=HTMLResponse)
def generate_comic(
    request: Request,
    prompt: str = Form(...),
    character_name: str = Form(...),
    setting: str = Form(...),
    tone: str = Form(...),
    style: str = Form(...),
):
    """Handle the HTML form: generate the comic and show the preview page."""
    form = {
        "prompt": prompt.strip(),
        "character_name": character_name.strip(),
        "setting": setting.strip(),
        "tone": tone.strip(),
        "style": style.strip(),
    }

    if len(form["prompt"]) < 3:
        return _render_index(request, form, "Please enter a story prompt (at least 3 characters).", 400)
    if len(form["prompt"]) > 1000:
        return _render_index(request, form, "The story prompt is too long (maximum 1000 characters).", 400)
    if not form["character_name"]:
        return _render_index(request, form, "Please enter a main character name.", 400)

    try:
        result = _create_comic(**form)
        return templates.TemplateResponse(
            request=request,
            name="comic_preview.html",
            context={
                "layout": result["layout"],
                "pdf_path": result["pdf_url"],
                "warning": result["warning"],
            },
        )
    except Exception as exc:  # noqa: BLE001 - show a friendly message instead of a crash
        traceback.print_exc()
        return _render_index(request, form, f"Comic generation failed: {exc}", 500)


@router.get("/export-success", response_class=HTMLResponse)
def export_success(request: Request, pdf_path: str):
    """Confirmation page shown after the PDF download."""
    if not (pdf_path.startswith("/static/exports/") and pdf_path.endswith(".pdf") and ".." not in pdf_path):
        raise HTTPException(status_code=400, detail="Invalid PDF path.")
    return templates.TemplateResponse(
        request=request,
        name="export_success.html",
        context={"pdf_path": pdf_path},
    )


# --------------------------------------------------------------------------- #
# JSON API + developer utilities
# --------------------------------------------------------------------------- #
@router.post("/generate-comic/json")
def generate_comic_json(payload: PromptRequest):
    """Generate a comic from a JSON body and return layout data + PDF path."""
    try:
        result = _create_comic(
            prompt=payload.prompt.strip(),
            character_name=payload.character_name.strip(),
            setting=payload.setting.strip(),
            tone=payload.tone.strip(),
            style=payload.style.strip(),
        )
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))

    # Do not expose server file-system paths in the API response.
    layout = [{key: value for key, value in panel.items() if key != "image_path"} for panel in result["layout"]]
    return {"layout": layout, "pdf_path": result["pdf_url"], "warning": result["warning"]}


@router.get("/test-image")
def test_image(prompt: str = "A futuristic city at sunset, sci-fi, cinematic, artstation"):
    """Developer utility: test image generation without making a full comic."""
    try:
        image_path = generate_image(prompt)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "message": "Image generated successfully",
        "path": static_url(image_path),
        "warning": pop_image_warning(),
    }


@router.get("/health")
def health():
    """Quick check that the server is running and configured."""
    return {
        "status": "ok",
        "gemini_key_configured": bool(GEMINI_API_KEY),
        "placeholder_images": USE_PLACEHOLDER_IMAGES,
    }
