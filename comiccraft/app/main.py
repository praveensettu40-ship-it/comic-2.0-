"""ComicCraft - AI Comic Story Creator (FastAPI entry point).

Run from the project root:
    uvicorn app.main:app --reload
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import GEMINI_API_KEY, STATIC_DIR, USE_PLACEHOLDER_IMAGES
from .routes import router

app = FastAPI(
    title="ComicCraft - AI Comic Story Creator",
    description="Generate comic stories with Gemini and illustrate them with Stable Diffusion.",
    version="1.0.0",
)

# Serves generated panel images, exported PDFs and fonts at /static/...
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(router)

if not GEMINI_API_KEY:
    print(
        "\n[ComicCraft] WARNING: GEMINI_API_KEY is not set. "
        "Copy .env.example to .env, add your key, and restart.\n"
    )
if USE_PLACEHOLDER_IMAGES:
    print("[ComicCraft] Placeholder image mode is ON (Stable Diffusion will not be used).")
