"""Offline tests: no API key, no internet and no Stable Diffusion needed.

Gemini calls are replaced with fake data and images are placeholders,
so these tests check everything else (routes, templates, layout, PDF).

Run from the project root:   pytest -v
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import image_generator, routes
from app.config import EXPORTS_DIR, STATIC_DIR
from app.gemini_flash import _extract_json_array, _normalise
from app.layout_builder import build_comic_layout
from app.main import app

client = TestClient(app)

FAKE_OUTLINE = [
    {
        "panel": i,
        "title": f"Title {i}",
        "scene_description": f"Scene {i} happens here.",
        "image_prompt": f"A fox in a forest, scene {i}",
    }
    for i in range(1, 6)
]

FAKE_STORY = "\n\n".join(
    f"**Panel {i}: Title {i}**\n"
    f"**CAPTION:** Wind in the trees {i}.\n"
    f"**NARRATION:** The fox walks on, brave as ever ({i}).\n"
    f'**DIALOGUE:** Free: "Onward! \u2014 caf\u00e9 \u2019quote\u2019"'
    for i in range(1, 6)
)


@pytest.fixture
def fake_ai(monkeypatch):
    monkeypatch.setattr(routes, "generate_outline", lambda prompt: [dict(p) for p in FAKE_OUTLINE])
    monkeypatch.setattr(routes, "generate_story", lambda outline, context="": FAKE_STORY)
    monkeypatch.setattr(image_generator, "USE_PLACEHOLDER_IMAGES", True)


FORM = {
    "prompt": "A brave fox explores an enchanted forest.",
    "character_name": "Free",
    "setting": "Forest",
    "tone": "Dramatic",
    "style": "Anime",
}


# ---------------------------- pages ---------------------------- #
def test_homepage_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "Create Your Comic" in response.text
    assert 'name="character_name"' in response.text


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_generate_form_shows_preview_and_creates_pdf(fake_ai):
    response = client.post("/generate", data=FORM)
    assert response.status_code == 200
    assert "Your Comic Preview" in response.text
    assert "Panel 1: Title 1" in response.text
    assert "Caption: Wind in the trees 1." in response.text
    assert "**" not in response.text  # markdown was cleaned
    assert "Download Your Comic as PDF" in response.text

    pdfs = sorted(EXPORTS_DIR.glob("comic_*.pdf"))
    assert pdfs, "PDF was not created"
    assert pdfs[-1].read_bytes().startswith(b"%PDF")


def test_generate_form_validation_error():
    bad = dict(FORM, prompt="  ")
    response = client.post("/generate", data=bad)
    assert response.status_code == 400
    assert "Please enter a story prompt" in response.text


def test_generate_form_reports_ai_failure(monkeypatch):
    def boom(prompt):
        raise RuntimeError("Gemini is down")

    monkeypatch.setattr(routes, "generate_outline", boom)
    response = client.post("/generate", data=FORM)
    assert response.status_code == 500
    assert "Gemini is down" in response.text


# ---------------------------- JSON API ---------------------------- #
def test_generate_json(fake_ai):
    response = client.post(
        "/generate-comic/json",
        json={"prompt": "A funny robot learns to cook", "tone": "funny", "style": "comic book"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["layout"]) == 5
    assert data["pdf_path"].startswith("/static/exports/")
    assert "image_path" not in data["layout"][0]
    assert client.get(data["pdf_path"]).status_code == 200


def test_generate_json_validation():
    response = client.post("/generate-comic/json", json={"prompt": "x"})
    assert response.status_code == 422


# ---------------------------- utilities ---------------------------- #
def test_test_image_route(fake_ai):
    response = client.get("/test-image", params={"prompt": "A castle in the clouds"})
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Image generated successfully"
    assert client.get(body["path"]).status_code == 200


def test_export_success_page_and_rejects_bad_paths():
    ok = client.get("/export-success", params={"pdf_path": "/static/exports/comic_1.pdf"})
    assert ok.status_code == 200
    assert "Comic Exported Successfully" in ok.text

    for bad in ("/etc/passwd", "/static/exports/../../app/main.py", "https://evil.example/x.pdf"):
        assert client.get("/export-success", params={"pdf_path": bad}).status_code == 400


# ---------------------------- unit tests ---------------------------- #
def test_extract_json_handles_markdown_fences():
    text = '```json\n[{"panel": 1, "title": "A", "scene_description": "S", "image_prompt": "P"}]\n```'
    panels = _normalise(_extract_json_array(text))
    assert panels[0]["title"] == "A"
    assert panels[0]["panel"] == 1


def test_normalise_caps_at_five_and_renumbers():
    raw = [{"panel": 9, "title": f"T{i}", "scene_description": "s", "image_prompt": "p"} for i in range(8)]
    panels = _normalise(raw)
    assert len(panels) == 5
    assert [p["panel"] for p in panels] == [1, 2, 3, 4, 5]


def test_layout_without_panel_headers_still_works(monkeypatch):
    monkeypatch.setattr(image_generator, "USE_PLACEHOLDER_IMAGES", True)
    images = [image_generator.generate_image(f"prompt {i}") for i in range(2)]
    story = "First paragraph.\n\nSecond paragraph."
    layout = build_comic_layout(images, story, FAKE_OUTLINE[:2])
    assert layout[0]["text"] == "First paragraph."
    assert layout[1]["text"] == "Second paragraph."
    assert Path(layout[0]["image_path"]).exists()
    assert layout[0]["image_url"].startswith("/static/panels/")


def test_static_dir_exists():
    assert STATIC_DIR.is_dir()
    assert (STATIC_DIR / "fonts" / "DejaVuSans.ttf").exists()
