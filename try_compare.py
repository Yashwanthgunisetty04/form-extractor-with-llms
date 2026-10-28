import json
import sys
from pathlib import Path

from engine.form_config import get_fields_for_page
from engine.compare import compare

# usage: python try_compare.py [output/extract/<file>_p<page>.json ...]
# compares saved try_extract.py readings, so no API calls are made
files = [Path(p) for p in sys.argv[1:]] or sorted(Path("output/extract").glob("*.json"))

totals = {"accepted": 0, "review": 0}
for f in files:
    saved = json.loads(f.read_text())
    fields = get_fields_for_page("fda_1932a", saved["page"])
    results = compare(saved["llm"], saved["textract"], fields)
    print(f"\n{f.name}")
    print(f"{'field':25} {'status':9} {'value':28} reason")
    for r in results:
        totals[r["status"]] += 1
        value = "" if r["value"] is None else repr(r["value"])
        print(f"{r['field']:25} {r['status']:9} {value:28} {r['reason'] or ''}")

print(f"\naccepted {totals['accepted']}, review {totals['review']}")
