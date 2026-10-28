import json
import sys
from pathlib import Path

from engine.load import load_pages
from engine.preprocess import preprocess, make_templates
from engine.form_config import get_fields_for_page
from engine.extract import llm_read_page, textract_read_page, LLM_MODEL

# usage: python try_extract.py samples/<file>.pdf [page]
path = sys.argv[1]
page_no = int(sys.argv[2]) if len(sys.argv) > 2 else 1

templates = make_templates(load_pages("forms/fda_1932a/templates/blank.pdf")[:5])
page = load_pages(path)[page_no - 1]
cleaned, blur, angle, rotation = preprocess(page, templates)
print(f"{path} page {page_no}: blur {blur:.0f}, angle {angle:.2f}, turn {rotation}")

fields = get_fields_for_page("fda_1932a", page_no)
print(f"Asking {LLM_MODEL} and Textract for {len(fields)} fields...\n")
llm = {r["field"]: r for r in llm_read_page(cleaned, fields)}
textract = {r["field"]: r for r in textract_read_page(cleaned, fields)}

print(f"{'field':25} {'LLM':35} {'Textract':30} conf")
for f in fields:
    l, t = llm[f["name"]], textract[f["name"]]
    t_conf = "" if t["confidence"] is None else f"{t['confidence']:.0f}"
    print(f"{f['name']:25} {l['raw_value']!r:35} {t['raw_value']!r:30} {t_conf}")

out = Path("output/extract")
out.mkdir(parents=True, exist_ok=True)
out_file = out / f"{Path(path).stem}_p{page_no}.json"
out_file.write_text(json.dumps({"file": path, "page": page_no, "model": LLM_MODEL,
                                "llm": list(llm.values()),
                                "textract": list(textract.values())}, indent=2))
print(f"\nSaved to {out_file}")
