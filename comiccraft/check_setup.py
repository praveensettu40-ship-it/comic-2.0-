"""Run this once after installing:  python check_setup.py

It checks Python, packages, fonts, folders and your .env settings, and tells
you exactly what to fix.
"""
import importlib
import sys

OK, BAD, WARN = "[ OK ]", "[FAIL]", "[WARN]"
problems = 0


def report(status: str, message: str) -> None:
    global problems
    if status == BAD:
        problems += 1
    print(f"{status} {message}")


# Python version
if sys.version_info >= (3, 9):
    report(OK, f"Python {sys.version.split()[0]}")
else:
    report(BAD, f"Python {sys.version.split()[0]} is too old. Use Python 3.10 - 3.12.")

# Packages
packages = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "jinja2": "jinja2",
    "multipart": "python-multipart",
    "dotenv": "python-dotenv",
    "google.genai": "google-genai",
    "torch": "torch",
    "diffusers": "diffusers",
    "transformers": "transformers",
    "accelerate": "accelerate",
    "PIL": "Pillow",
    "fpdf": "fpdf2",
}
for module, pip_name in packages.items():
    try:
        importlib.import_module(module)
        report(OK, f"package '{pip_name}'")
    except Exception as exc:  # noqa: BLE001
        report(BAD, f"package '{pip_name}' not usable ({exc}). Fix: pip install -r requirements.txt")

# The exporter needs fpdf2 (2.7.9 or newer); the old "fpdf" package does not work
try:
    import inspect

    import fpdf

    if "new_x" not in inspect.signature(fpdf.FPDF.multi_cell).parameters:
        report(BAD, "Wrong PDF library installed. Fix: pip uninstall fpdf -y && pip install --force-reinstall fpdf2")
except Exception:  # noqa: BLE001
    pass  # a missing package is already reported above

# Project settings
try:
    from app import config

    report(OK if config.FONT_REGULAR.exists() else BAD, f"PDF font {config.FONT_REGULAR.name}")
    if config.GEMINI_API_KEY:
        report(OK, "GEMINI_API_KEY is set")
    else:
        report(BAD, "GEMINI_API_KEY is missing. Copy .env.example to .env and add your key.")
    if config.USE_PLACEHOLDER_IMAGES:
        report(WARN, "USE_PLACEHOLDER_IMAGES=true -> quick test mode (no real Stable Diffusion images)")
    print(f"       Gemini models : {config.GEMINI_FLASH_MODEL} (outline), {config.GEMINI_PRO_MODEL} (story)")
    print(f"       Stable Diffusion: {config.SD_MODEL_ID}, {config.SD_IMAGE_SIZE}px, {config.SD_STEPS} steps")
except Exception as exc:  # noqa: BLE001
    report(BAD, f"Could not load app settings: {exc}")

# Hardware
try:
    import torch

    if torch.cuda.is_available():
        report(OK, f"GPU found: {torch.cuda.get_device_name(0)} (fast image generation)")
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        report(OK, "Apple GPU (MPS) found")
    else:
        report(WARN, "No GPU found. Images will use the CPU: about 1-5 minutes per image.")
except Exception:  # noqa: BLE001
    pass

print()
if problems:
    print(f"{problems} problem(s) found. Fix the [FAIL] lines above and run this again.")
    sys.exit(1)
print("All good! Start the app with:  uvicorn app.main:app --reload")
