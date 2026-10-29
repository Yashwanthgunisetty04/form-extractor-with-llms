import json
import sys
from datetime import datetime
from pathlib import Path

import cv2

from engine.load import load_pages
from engine.preprocess import preprocess, make_templates, BLUR_THRESHOLD
from engine.form_config import get_fields, get_fields_for_page
from engine.extract import llm_read_page, textract_read_page, LLM_MODEL
from engine.compare import compare

ROOT = Path(__file__).parent
OUT = ROOT / "output"
FILE_TYPES = (".pdf", ".jpg", ".jpeg", ".png")


def process_file(path, form_type, on_step=print):
    # one filled form -> output/<name>.json (+ cleaned page images for review)
    # on_step(message) reports progress (print on the command line, live status in the UI)
    path = Path(path)
    fields = get_fields(form_type)
    templates = make_templates(load_pages(ROOT / "forms" / form_type / "templates" / "blank.pdf"))
    pages = load_pages(path)
    page_info, results = [], []
    OUT.mkdir(exist_ok=True)

    for page_no in sorted({f["page"] for f in fields}):
        page_fields = get_fields_for_page(form_type, page_no)
        if page_no > len(pages):
            # page missing from the scan: nothing to read
            results += [{"field": f["name"], "page": page_no, "llm": None, "textract": None,
                         "textract_confidence": None, "value": None,
                         "status": "review", "reason": "page missing"} for f in page_fields]
            continue
        cleaned, blur, angle, rotation = preprocess(pages[page_no - 1], templates)
        blur, angle = float(blur), float(angle)  # numpy numbers -> plain floats for JSON
        image_file = OUT / f"{path.stem}_p{page_no}.jpg"
        cv2.imwrite(str(image_file), cleaned)
        page_info.append({"page": page_no, "blur": round(blur), "blurry": blur < BLUR_THRESHOLD,
                          "angle": round(angle, 2), "rotation": rotation,
                          "image": image_file.name})
        on_step(f"page {page_no}: reading {len(page_fields)} fields...")
        llm = llm_read_page(cleaned, page_fields)
        textract = textract_read_page(cleaned, page_fields)
        results += [{"page": page_no, **r} for r in compare(llm, textract, page_fields)]

    accepted = sum(r["status"] == "accepted" for r in results)
    report = {
        "file": str(path),
        "form_type": form_type,
        "llm_model": LLM_MODEL,
        "created": datetime.now().isoformat(timespec="seconds"),
        "summary": {"fields": len(results), "accepted": accepted,
                    "review": len(results) - accepted},
        "pages": page_info,
        "fields": results,
    }
    out_file = OUT / f"{path.stem}.json"
    out_file.write_text(json.dumps(report, indent=2))
    return out_file, report


if __name__ == "__main__":
    # usage: python run.py <form file or folder> [form_type]
    if len(sys.argv) < 2:
        sys.exit("usage: python run.py <form file or folder> [form_type]")
    target = Path(sys.argv[1])
    form_type = sys.argv[2] if len(sys.argv) > 2 else "fda_1932a"
    files = (sorted(f for f in target.iterdir() if f.suffix.lower() in FILE_TYPES)
             if target.is_dir() else [target])

    for f in files:
        print(f"{f.name} ({form_type})")
        out_file, report = process_file(f, form_type, on_step=lambda m: print(f"  {m}"))
        s = report["summary"]
        blurry = [p["page"] for p in report["pages"] if p["blurry"]]
        print(f"  {s['accepted']} accepted, {s['review']} review"
              + (f"; blurry pages: {blurry}" if blurry else "")
              + f" -> {out_file}")
