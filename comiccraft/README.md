# ComicCraft - AI Comic Story Creator

Turn a story idea into a 5-panel comic with a PDF download.

- **Gemini Flash** writes the panel outline
- **Gemini Pro** writes narration and dialogue
- **Stable Diffusion** (Hugging Face Diffusers) draws each panel
- **FastAPI + Jinja2** serve the website, **fpdf2** makes the PDF

## Project structure

```
comiccraft/
├── app/
│   ├── main.py             # FastAPI app, mounts /static, includes routes
│   ├── routes.py           # /, /generate, /generate-comic/json, /export-success, /test-image, /health
│   ├── config.py           # paths + .env settings
│   ├── schemas.py          # PromptRequest (Pydantic)
│   ├── gemini_client.py    # shared Gemini helper (model fallback + retry)
│   ├── gemini_flash.py     # generate_outline()
│   ├── gemini_pro.py       # generate_story()
│   ├── image_generator.py  # generate_image()
│   ├── layout_builder.py   # build_comic_layout()
│   └── exporters.py        # save_pdf()
├── templates/              # index.html, comic_preview.html, export_success.html
├── static/
│   ├── panels/             # generated images
│   ├── exports/            # generated PDFs
│   └── fonts/              # DejaVu fonts for the PDF (included)
├── tests/test_comiccraft.py
├── check_setup.py          # checks your install
├── .env.example            # copy to .env
└── requirements.txt
```

## 1. Setup in VS Code

**Needs:** Python 3.10, 3.11 or 3.12 and VS Code with the *Python* extension.
Disk: about 6 GB free (Stable Diffusion downloads ~4 GB on the first comic).

1. Unzip the project, then in VS Code: **File > Open Folder...** and pick the `comiccraft` folder.
2. Open a terminal: **Terminal > New Terminal**.
3. Create and activate a virtual environment:

   Windows (PowerShell or Command Prompt):
   ```
   python -m venv env
   env\Scripts\activate
   ```
   If PowerShell blocks it, run `Set-ExecutionPolicy -Scope Process Bypass` first.

   macOS / Linux:
   ```
   python3 -m venv env
   source env/bin/activate
   ```
   If VS Code asks to use the new environment, click **Yes**. (Or press `Ctrl+Shift+P` > *Python: Select Interpreter* > pick the one in `env`.)

4. Install the libraries:
   ```
   pip install -r requirements.txt
   ```
   NVIDIA GPU? For fast images, install the CUDA build of PyTorch first using the command from https://pytorch.org/get-started/locally/ and then run the line above.

5. Create your settings file:

   Windows: `copy .env.example .env`
   macOS / Linux: `cp .env.example .env`

   Open `.env` and set `GEMINI_API_KEY=` to your free key from https://aistudio.google.com/apikey
   (`HF_API_KEY` is optional.)

6. Check everything:
   ```
   python check_setup.py
   ```
   Fix any `[FAIL]` line, then run it again.

## 2. Run

```
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 (API docs: http://127.0.0.1:8000/docs).
You can also press **F5** in VS Code (uses `.vscode/launch.json`).

Fill in the form, click **Generate Comic**, and wait. The first run downloads Stable Diffusion.
Speed: a GPU takes seconds per image, a CPU takes about 1 to 5 minutes per image (5 panels).

## 3. Test

**A. Automatic tests (no API key, no internet needed):**
```
pytest -v
```
These replace Gemini with fake data and use placeholder images. They check the pages, form, JSON API, PDF creation and layout.

**B. Quick manual test without waiting for Stable Diffusion:**
set `USE_PLACEHOLDER_IMAGES=true` in `.env`, restart the server, and generate a comic.
You get the real Gemini story with simple placeholder pictures in seconds. Set it back to `false` for real art.

**C. Check each part:**

| What | How |
|------|-----|
| Server running | open http://127.0.0.1:8000/health -> `{"status":"ok", ...}` |
| Image generation | open http://127.0.0.1:8000/test-image -> returns `"Image generated successfully"` and a path |
| JSON API | at `/docs`, open `POST /generate-comic/json` > **Try it out** > **Execute** |
| Full flow | home page > Generate > preview > **Download Your Comic as PDF** > success page |

JSON API example (macOS / Linux):
```
curl -X POST http://127.0.0.1:8000/generate-comic/json \
  -H "Content-Type: application/json" \
  -d '{"prompt":"A funny robot learns to cook","character_name":"Bolt","setting":"city","tone":"funny","style":"comic book"}'
```

## Settings (.env)

| Setting | Default | Meaning |
|---------|---------|---------|
| `GEMINI_API_KEY` | - | **Required** |
| `GEMINI_FLASH_MODEL` / `GEMINI_PRO_MODEL` | `gemini-2.5-flash` / `gemini-2.5-pro` | Models for outline / story |
| `GEMINI_FALLBACK_MODELS` | `gemini-2.5-flash,gemini-2.0-flash` | Tried automatically if a model fails |
| `SD_MODEL_ID` | `stable-diffusion-v1-5/stable-diffusion-v1-5` | Image model |
| `SD_STEPS` / `SD_IMAGE_SIZE` | `25` / `512` | Lower = faster (try `15` and `384` on CPU) |
| `USE_PLACEHOLDER_IMAGES` | `false` | `true` = fast test mode |
| `FALLBACK_TO_PLACEHOLDER` | `true` | Use placeholders if Stable Diffusion cannot load |

Why not the models in the original document? Google shut down `gemini-1.5-*`, and the
`runwayml/stable-diffusion-v1-5` repo was removed from Hugging Face. The defaults above replace
them, and you can change them in `.env` any time. The text `.docx` is otherwise followed exactly
(same files, functions, routes and pages).

Optional: put a picture at `static/background.jpg` to use it as the homepage background.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `GEMINI_API_KEY is not set` | Check the `.env` file is in the `comiccraft` folder (not `.env.example`), then restart the server |
| `All Gemini models failed ... 404` | Model name retired. Set a current one in `.env` (see https://ai.google.dev/gemini-api/docs/models) |
| `429 / RESOURCE_EXHAUSTED` | Free quota used up. Wait a minute, or use `gemini-2.5-flash` for both models |
| Yellow "placeholder images" banner | Stable Diffusion could not load. Read the message, check internet/disk/RAM (8 GB+), and restart |
| Very slow images | Normal on CPU. Lower `SD_STEPS` and `SD_IMAGE_SIZE`, or use a GPU |
| `CUDA out of memory` | Set `SD_IMAGE_SIZE=384` |
| Black images | The built-in safety filter blocked the prompt. Try a different story |
| `ModuleNotFoundError` | Activate the environment (`env\Scripts\activate`) and run `pip install -r requirements.txt` |
| PDF error about `fpdf` | `pip uninstall fpdf -y` then `pip install --force-reinstall fpdf2` |
| Code changes ignored after a model load failure | Stop the server (Ctrl+C) and start it again |
