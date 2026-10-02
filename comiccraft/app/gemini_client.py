"""Small wrapper around the Google Gen AI SDK (package: google-genai).

Features
- One cached client.
- Tries several models in order (main model first, then fallbacks).
- Retries briefly on temporary errors (rate limit / overloaded).
"""
import time
from functools import lru_cache
from typing import Iterable, List

from .config import GEMINI_API_KEY


@lru_cache(maxsize=1)
def get_client():
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and paste your key "
            "(free key: https://aistudio.google.com/apikey), then restart the server."
        )
    # Imported here so the app can still start (and tests can run) without the SDK.
    from google import genai

    return genai.Client(api_key=GEMINI_API_KEY)


def _unique(models: Iterable[str]) -> List[str]:
    seen, result = set(), []
    for name in models:
        name = (name or "").strip()
        if name.startswith("models/"):
            name = name[len("models/"):]
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def _is_temporary(error: Exception) -> bool:
    text = str(error).lower()
    return any(
        marker in text
        for marker in ("429", "503", "500", "unavailable", "overloaded", "resource_exhausted", "timeout")
    )


def generate_text(
    prompt: str,
    models: Iterable[str],
    json_mode: bool = False,
    temperature: float = 0.9,
) -> str:
    """Send `prompt` to Gemini and return the response text.

    Raises RuntimeError with a readable message if every model fails.
    """
    from google.genai import types

    client = get_client()
    config_kwargs = {"temperature": temperature}
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"
    config = types.GenerateContentConfig(**config_kwargs)

    errors = []
    for model in _unique(models):
        for attempt in (1, 2):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                text = (response.text or "").strip()
                if not text:
                    raise RuntimeError("the model returned an empty response")
                return text
            except Exception as exc:  # noqa: BLE001 - we want to try the next model
                print(f"[Gemini] model={model} attempt={attempt} failed: {exc}")
                if attempt == 1 and _is_temporary(exc):
                    time.sleep(3)
                    continue
                errors.append(f"{model}: {exc}")
                break

    raise RuntimeError("All Gemini models failed. Details: " + " | ".join(errors))
