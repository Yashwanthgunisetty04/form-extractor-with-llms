import csv
import sys
from pathlib import Path

from engine.form_config import get_fields

# usage: python make_answers_template.py [form_type]
# writes samples/answers.csv: one row per sample file, one column per field.
# Fill in what is really written on each form; existing rows are kept.
#   - copy the value as written (dates as on the form, e.g. 10/26/2026)
#   - leave a cell empty if the field is blank on the form
#   - multi-choice: ticked options separated by ";"  e.g. Adverse Event; Product Problem
#   - "?" if you can't tell what the right answer is (not scored)
form_type = sys.argv[1] if len(sys.argv) > 1 else "fda_1932a"
columns = ["file"] + [f["name"] for f in get_fields(form_type)]
answers = Path("samples/answers.csv")

rows = {}
if answers.exists():
    with answers.open(newline="", encoding="utf-8") as fh:
        rows = {r["file"]: r for r in csv.DictReader(fh)}

files = sorted(f.name for f in Path("samples").iterdir()
               if f.suffix.lower() in (".pdf", ".jpg", ".jpeg", ".png"))
for name in files:
    rows.setdefault(name, {"file": name})

with answers.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for name in sorted(rows):
        writer.writerow(rows[name])

print(f"{answers}: {len(rows)} forms, {len(columns) - 1} fields")
