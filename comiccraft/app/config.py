"""Central configuration for ComicCraft.

All paths are absolute (based on the project folder), so the app works no
matter which folder you start it from.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
PANELS_DIR = STATIC_DIR / "panels"
EXPORTS_DIR = STATIC_DIR / "exports"
FONTS_DIR = STATIC_DIR / "fonts"

for _folder in (STATIC_DIR, TEMPLATES_DIR, PANELS_DIR, EXPORTS_DIR, FONTS_DIR):
    _folder.mkdir(parents=True, exist_ok=True)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _get_list(name: str, default: str) -> list:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _clean_secret(value: str) -> str:
    """Treat the placeholder text from .env.example as 'not set'."""
    value = (value or "").strip().strip('"').strip("'")
    lowered = value.lower()
    if lowered.startswith("your") and ("key" in lowered or "api" in lowered):
        return ""
    return value


# ---- API keys ----
GEMINI_API_KEY = _clean_secret(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "")
HF_TOKEN = _clean_secret(os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN") or "")

# ---- Gemini models ----
GEMINI_FLASH_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-3.8-flash").strip()
GEMINI_PRO_MODEL = os.getenv("GEMINI_PRO_MODEL", "gemini-3.8-pro").strip()
GEMINI_FALLBACK_MODELS = _get_list("GEMINI_FALLBACK_MODELS", "gemini-3.8-flash,gemini-2.0-flash")

# ---- Stable Diffusion ----
SD_MODEL_ID = os.getenv("SD_MODEL_ID", "stable-diffusion-v1-5/stable-diffusion-v1-5").strip()
# Mirrors tried automatically if SD_MODEL_ID cannot be downloaded
SD_FALLBACK_MODEL_IDS = [
    "sd-legacy/stable-diffusion-v1-5",
    "runwayml/stable-diffusion-v1-5",
]
SD_STEPS = max(1, _get_int("SD_STEPS", 25))
# Stable Diffusion needs a multiple of 8, and very small sizes look bad
SD_IMAGE_SIZE = max(256, (_get_int("SD_IMAGE_SIZE", 512) // 8) * 8)

USE_PLACEHOLDER_IMAGES = _get_bool("USE_PLACEHOLDER_IMAGES", False)
FALLBACK_TO_PLACEHOLDER = _get_bool("FALLBACK_TO_PLACEHOLDER", True)

# ---- PDF fonts (DejaVu supports accents, curly quotes, etc.) ----
FONT_REGULAR = FONTS_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONTS_DIR / "DejaVuSans-Bold.ttf"
FONT_ITALIC = FONTS_DIR / "DejaVuSans-Oblique.ttf"


def static_url(path) -> str:
    """Convert a file path inside /static into a web URL like /static/panels/a.png."""
    try:
        relative = Path(path).resolve().relative_to(STATIC_DIR.resolve())
    except (ValueError, OSError):
        return ""
    return "/static/" + relative.as_posix()
