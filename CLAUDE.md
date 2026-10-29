# Form Extraction POC

## Goal
Proof of concept: extract field values from phone-scanned, mostly handwritten
PDF forms (often blurry, tilted, low quality) using a vision LLM plus AWS Textract,
then compare the two readings and flag fields that need human review.
POC only — keep it simple. No database, no queues, no frontend capture page,
no template alignment yet.

## Pipeline
load.py → preprocess.py → extract.py → compare.py → result JSON
form_config.py is data read by extract.py and compare.py.
run.py calls the steps in order. app.py + pages/ is the Streamlit UI on top.

## Module contracts (keep these fixed so each file can be tested alone)
| File | Input | Output |
|---|---|---|
| engine/load.py | PDF path | list of page images (numpy BGR, ~300 DPI) |
| engine/preprocess.py | page image + template thumbnails (optional) | cleaned image + blur score + deskew angle + rotation (0/90/180/270) |
| engine/form_config.py | none (data) | field list: name, page, type, Textract query text |
| engine/extract.py | cleaned pages + field list | LLM readings and Textract readings per field |
| engine/compare.py | both readings + field list | per-field result: value, status, reason |
| run.py | PDF path + form type | final JSON saved to output/ |

## Field reading format
Each engine returns per field: field name, raw value, confidence (Textract only,
None for LLM), and illegible flag.

## compare.py output per field
```json
{
  "field": "phone",
  "llm": "9876543217",
  "textract": "987654321",
  "textract_confidence": 91,
  "status": "review",
  "reason": "engines disagree"
}
```
status is "accepted" (both agree after normalization and value passes validation)
or "review" with a reason: engines disagree, low confidence (<70), failed
validation, or illegible.

## Rules
- Normalize before comparing: dates to YYYY-MM-DD, phone digits only, trim spaces,
  case-insensitive text, O→0 and l→1 in numeric fields.
- LLM prompt must say: copy exactly what is written, return "ILLEGIBLE" instead
  of guessing, return JSON matching the field list.
- Textract: use AnalyzeDocument with Queries, one query per field.
- Blur threshold starts at 100 (Laplacian variance); tune on real samples.
- Keep the LLM call behind one function so the model can be swapped.
- API keys come from .env, never hardcoded.
- samples/, output/ and .env are never committed to git (forms contain personal data).

## Folders
- forms/<form_type>/templates/  blank form PDFs
- samples/  real filled test forms
- samples/answers.csv  correct answers per form (one row per file, one column per
  field; "?" = unknown, not scored). Created/extended by make_answers_template.py.
- output/   generated images and JSON (gitignored)

## Status
- [x] load.py — PDF to images
- [x] preprocess.py — blur score, deskew, contrast, orientation. orient() turns the page
      only if the best turn scores >= 1.5x the runner-up (MIN_LEAD); real photos score
      only ~0.2–0.3 even upright, so an absolute cutoff never fired. Fixed a sideways
      page in FORM_2 (turn 270).
- [x] form_config.py — 25 fields for fda_1932a (pages 1–3), 7 of them checkboxes
      (choice/multi_choice). age and weight are type measure ("62lb" = "62 lb").
- [x] extract.py — LLM + Textract (try_extract.py prints both side by side)
      - LLM: OpenAI gpt-6.1-terra (OPENAI_MODEL), Responses API + strict json_schema.
        On synthetic sample medium_tilt_m18deg.pdf: all readable fields correct,
        cut-off fields correctly ILLEGIBLE.
      - Textract: AnalyzeDocument QUERIES for all fields, checkboxes included
        (Queries returns the ticked label; 7/7 correct on the sample). AWS keys in .env.
        Text fields 8/18 correct. Known weaknesses: split Month/Day/Year date boxes
        come back as fragments (low conf); "sender" queries can return the Health
        Care Professional block (last name, email) with high conf; reads cut-off
        text as if complete. If checkboxes fail on real scans, try FORMS
        (SELECTION_ELEMENT) for them. Still needs real handwritten scans.
- [x] compare.py — normalize + validate per type; reasons joined with "; ".
      Also returns "value" (normalized, only when accepted). Textract checkbox text
      is mapped onto the field's options. try_compare.py re-runs compare on saved
      output/extract/*.json (no API calls).
      Synthetic sample: 13 accepted (all correct), 12 review.
- [x] run.py — `python run.py <file or folder> [form_type]` (default fda_1932a).
      process_file(path, form_type, on_step) is what the UI calls.
      Writes output/<name>.json (summary, per-page blur/angle/rotation, per-field
      compare result + page) and output/<name>_p<N>.jpg cleaned pages.
      Synthetic sample end to end: 13 accepted, 12 review (same as try_compare).
- [x] evaluate.py — `python evaluate.py [-v]`: compares output/<name>.json with
      samples/answers.csv (no API calls). Reports per-field and overall LLM/Textract
      accuracy, agreement and whether agreement means correct, accepted-but-wrong
      list (the key safety number), review reasons; -v lists every engine mistake.
      evaluate(output_dir, answers_csv, form_type) returns the numbers for the UI.
      First 2 real handwritten forms: LLM 50/50, Textract 38/50, 34 accepted (all
      correct), 16 review (LLM right in all 16). Textract weak on split date boxes
      and on some checkboxes (blank box read as "No" at 99 conf).
- [ ] Collect 20–30 real handwritten forms + fill answers.csv, then evaluate and tune
      (blur threshold, confidence cutoff, model choice, date queries).
- [x] app.py — Streamlit UI: `streamlit run app.py`. pages/1_Process (upload →
      samples/, run), 2_Review (page image + flagged field cards, typed inputs,
      saves output/<name>_reviewed.json, never touches <name>.json),
      3_Evaluate (metrics from evaluate()). File helpers in ui/files.py.
      Out of scope: bounding boxes, form-type detection, new forms via the UI.

## Success criteria
Run 20–30 real forms; measure per-field accuracy for LLM and Textract,
how often they agree, and whether agreement means correct.

## Environment
Windows, VS Code, project folder D:\Projects\Form_Extraction, Python with a .venv.

## How to work with the user
- Guide one step at a time. Explain what we're doing and why before writing code.
- Let the user write code where it's a good learning opportunity; review it and
  point out problems.
- Keep explanations simple and check that each step works before moving on.
- No fixed schedule; just point to the next step in the Status list.
- Update the Status section in this file as steps are finished.
