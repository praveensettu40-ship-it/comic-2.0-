"""Step 3 - Stable Diffusion creates one illustration per panel.

The model is loaded once (lazily, on the first image) and reused.
If Stable Diffusion cannot load (no internet, not enough memory, ...) the app
can fall back to simple placeholder images so the rest of the pipeline
(story, layout, PDF) still works.  Control this with the .env settings
USE_PLACEHOLDER_IMAGES and FALLBACK_TO_PLACEHOLDER.
"""
import hashlib
import re
import textwrap
import threading
import uuid
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .config import (
    FALLBACK_TO_PLACEHOLDER,
    FONT_REGULAR,
    HF_TOKEN,
    PANELS_DIR,
    SD_FALLBACK_MODEL_IDS,
    SD_IMAGE_SIZE,
    SD_MODEL_ID,
    SD_STEPS,
    USE_PLACEHOLDER_IMAGES,
)

NEGATIVE_PROMPT = (
    "text, letters, words, watermark, signature, speech bubble, blurry, low quality, "
    "deformed, extra limbs, bad anatomy, cropped"
)

_pipe = None
_pipe_lock = threading.Lock()
_load_error: Optional[str] = None  # set when the model could not be loaded
_placeholder_reason: Optional[str] = None  # why placeholders were used (shown in the UI)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def sanitize_filename(text: str, max_len: int = 40) -> str:
    """Turn a prompt into a safe, unique PNG filename."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text or "").strip("_").lower()[:max_len].strip("_")
    return f"{slug or 'panel'}_{uuid.uuid4().hex[:8]}.png"


def pop_image_warning() -> Optional[str]:
    """Return (and clear) a message if placeholders were used since the last call."""
    global _placeholder_reason
    reason, _placeholder_reason = _placeholder_reason, None
    return reason


def _candidate_model_ids() -> list:
    ids = []
    for model_id in [SD_MODEL_ID, *SD_FALLBACK_MODEL_IDS]:
        if model_id and model_id not in ids:
            ids.append(model_id)
    return ids


def _load_pipeline():
    """Load Stable Diffusion once and keep it in memory."""
    global _pipe
    if _pipe is not None:
        return _pipe

    import torch
    from diffusers import StableDiffusionPipeline

    if torch.cuda.is_available():
        device, dtype = "cuda", torch.float16
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        device, dtype = "mps", torch.float32
    else:
        device, dtype = "cpu", torch.float32
    print(f"[Stable Diffusion] device={device}, dtype={dtype}")

    errors = []
    for model_id in _candidate_model_ids():
        try:
            print(f"[Stable Diffusion] loading '{model_id}' (first run downloads ~4 GB)...")
            kwargs = {"torch_dtype": dtype}
            if HF_TOKEN:
                kwargs["token"] = HF_TOKEN
            pipe = StableDiffusionPipeline.from_pretrained(model_id, **kwargs)
            pipe = pipe.to(device)
            pipe.enable_attention_slicing()
            _pipe = pipe
            print(f"[Stable Diffusion] ready: {model_id}")
            return _pipe
        except Exception as exc:  # noqa: BLE001 - try the next mirror
            print(f"[Stable Diffusion] could not load '{model_id}': {exc}")
            errors.append(f"{model_id}: {exc}")

    raise RuntimeError("Could not load any Stable Diffusion model. " + " | ".join(errors))


def _make_placeholder(prompt: str) -> Image.Image:
    """Draw a simple coloured card containing the prompt text."""
    size = SD_IMAGE_SIZE
    digest = hashlib.sha256((prompt or "").encode("utf-8")).digest()
    top = tuple(50 + digest[i] % 110 for i in range(3))
    bottom = tuple(110 + digest[i + 3] % 130 for i in range(3))

    image = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        t = y / max(1, size - 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line([(0, y), (size, y)], fill=color)

    try:
        font = ImageFont.truetype(str(FONT_REGULAR), max(12, size // 28))
        title_font = ImageFont.truetype(str(FONT_REGULAR), max(16, size // 18))
    except OSError:
        font = title_font = ImageFont.load_default()

    margin = size // 12
    draw.rectangle([margin, margin, size - margin, size - margin], outline=(255, 255, 255), width=3)
    draw.text((margin + 16, margin + 14), "PLACEHOLDER IMAGE", fill=(255, 255, 255), font=title_font)
    wrapped = textwrap.fill((prompt or "")[:260], width=max(20, size // 15))
    draw.multiline_text((margin + 16, margin + 14 + size // 12), wrapped, fill=(255, 255, 255), font=font, spacing=6)
    return image


# --------------------------------------------------------------------------- #
# public function
# --------------------------------------------------------------------------- #
def generate_image(prompt: str, filename: Optional[str] = None) -> str:
    """Create a comic-style image for `prompt` and save it in static/panels.

    Args:
        prompt: Image description for Stable Diffusion.
        filename: Optional file name (a safe unique name is generated if omitted).

    Returns:
        The full file path of the saved PNG.

    Raises:
        RuntimeError: if image generation fails and FALLBACK_TO_PLACEHOLDER is false.
    """
    global _load_error, _placeholder_reason

    if not filename:
        filename = sanitize_filename(prompt)
    filename = Path(filename).name  # never allow folders in the name
    if not filename.lower().endswith(".png"):
        filename += ".png"

    PANELS_DIR.mkdir(parents=True, exist_ok=True)
    path = PANELS_DIR / filename

    image = None

    if USE_PLACEHOLDER_IMAGES:
        _placeholder_reason = "Placeholder images are on (USE_PLACEHOLDER_IMAGES=true)."
    elif _load_error and FALLBACK_TO_PLACEHOLDER:
        _placeholder_reason = f"Stable Diffusion is unavailable, so placeholder images were used. {_load_error}"
    else:
        try:
            with _pipe_lock:
                pipe = _load_pipeline()
                result = pipe(
                    prompt=(prompt or "")[:300],
                    negative_prompt=NEGATIVE_PROMPT,
                    num_inference_steps=SD_STEPS,
                    guidance_scale=7.5,
                    height=SD_IMAGE_SIZE,
                    width=SD_IMAGE_SIZE,
                )
            image = result.images[0]
        except Exception as exc:  # noqa: BLE001
            message = f"Image generation failed: {str(exc)[:300]}"
            print(f"[Stable Diffusion] {message}")
            if not FALLBACK_TO_PLACEHOLDER:
                raise RuntimeError(message) from exc
            if _pipe is None:  # model never loaded -> don't retry for every panel
                _load_error = message
            _placeholder_reason = f"Stable Diffusion is unavailable, so placeholder images were used. {message}"

    if image is None:
        image = _make_placeholder(prompt)

    image.save(path)
    return str(path)
