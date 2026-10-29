"""
File helpers for the Streamlit pages: list and load results, save reviews.
The UI only reads and writes files here; extraction logic stays in engine/ and run.py.
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "output"
SAMPLES = ROOT / "samples"
ANSWERS = SAMPLES / "answers.csv"
REVIEWED = "_reviewed"  # output/<name>_reviewed.json holds the reviewer's final values
FILE_TYPES = (".pdf", ".jpg", ".jpeg", ".png")


def list_results():
    # pipeline results (output/<name>.json), newest first; reviewed copies are left out
    files = [f for f in OUT.glob("*.json") if not f.stem.endswith(REVIEWED)]
    return [f.stem for f in sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)]


def list_samples():
    if not SAMPLES.exists():
        return []
    return sorted(f.name for f in SAMPLES.iterdir() if f.suffix.lower() in FILE_TYPES)


def load_result(stem):
    return json.loads((OUT / f"{stem}.json").read_text())


def page_image(stem, page):
    path = OUT / f"{stem}_p{page}.jpg"
    return path if path.exists() else None


def reviewed_path(stem):
    return OUT / f"{stem}{REVIEWED}.json"


def load_reviewed(stem):
    path = reviewed_path(stem)
    return json.loads(path.read_text()) if path.exists() else None


def save_reviewed(stem, review):
    # never touches output/<name>.json, so evaluate.py keeps measuring the pipeline itself
    review = {**review, "reviewed_at": datetime.now().isoformat(timespec="seconds")}
    text = json.dumps(review, indent=2)
    reviewed_path(stem).write_text(text)
    return text


def field_label(field):
    # "Sender Information → Sender zip", so the reviewer knows where to look on the page
    return f"{field['section']} → {field['name'].replace('_', ' ').capitalize()}"
