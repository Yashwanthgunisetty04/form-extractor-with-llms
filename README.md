# Form Extractor with LLMs

Reads handwritten paper forms from phone photos and scans, and tells you which
fields can be trusted.

Every field is read by two independent engines: a vision LLM (OpenAI) and AWS
Textract. If the two readings agree after normalization and the value passes
validation, the field is accepted automatically. Otherwise it goes to a human
reviewer, along with the reason.

**Live demo:** https://form-extractor-with-llms.streamlit.app/

> Proof of concept. Built and tested on FDA Form 1932a (3 pages, 25 fields,
> 7 of them checkboxes).

## Why two engines?

A single OCR or LLM reading gives you a value but no reliable signal for when it
is wrong. LLMs in particular can return a confident, plausible answer for a
smudged field. Two engines that work differently rarely make the *same* mistake,
so agreement is a strong signal that a reading is correct, and disagreement shows
exactly where a human needs to look.

## Results

On the first 2 real handwritten forms (50 scored fields):

| Metric | Result |
|---|---|
| LLM accuracy | 50 / 50 |
| Textract accuracy | 38 / 50 |
| Accepted automatically | 34 fields, **all correct** (0 accepted-but-wrong) |
| Sent to review | 16 fields (the LLM was right in all 16) |

"Accepted but wrong" is the key safety number: fields that would skip human
review with a wrong value. Textract's weak spots were dates written in split
Month/Day/Year boxes and some checkboxes (a blank box read as "No" with 99%
confidence).


## How it works

```
PDF / photo
   │
   ▼
load.py        PDF pages → images at 300 DPI (photos loaded as-is)
   │
   ▼
preprocess.py  find and flatten the paper, fix 90/180/270° rotation,
               deskew, improve contrast, score blur
   │
   ├──────────────────────┐
   ▼                      ▼
LLM (OpenAI)          AWS Textract
one call per page,    AnalyzeDocument with
strict JSON schema    one query per field
   │                      │
   └──────────┬───────────┘
              ▼
compare.py     normalize both readings → validate → agree?
              │
              ▼
   accepted  or  review (with reason)
```

- **LLM prompt rules:** copy exactly what is written, never guess, and return
  `ILLEGIBLE` for anything that can't be read. The output is forced into a JSON
  schema built from the field list.
- **Normalization before comparing:** dates become `YYYY-MM-DD`, phone numbers keep
  only digits, text is trimmed and compared case-insensitively, `O`→`0` and `l`→`1`
  in numeric fields, and measures like `62lb` = `62 lb`. Checkbox text is mapped
  onto the field's allowed options.
- **Review reasons:** engines disagree, low Textract confidence (<70), failed
  validation (bad date, email, phone…), illegible, or page missing. Blurry pages
  get a warning so the reviewer checks them carefully.

Example result for one field:

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

## The app

Built with Streamlit:

1. **Process:** upload a filled form (PDF or photo) and run the pipeline, with live
   progress, page quality (blur, deskew angle, rotation) and an accepted/review summary.
2. **Review:** the cleaned page image next to a card for each flagged field, showing
   both readings and the reason. The reviewer enters the final value, which is saved
   separately from the pipeline output.
3. **Evaluate:** accuracy per engine and per field, agreement, and accepted-but-wrong,
   measured against a CSV of correct answers. This runs locally only, because the
   answers come from real forms with personal data.

## Project structure

```
app.py, pages/         Streamlit UI (Process, Review, Evaluate)
ui/files.py            file helpers for the UI
run.py                 runs the pipeline: python run.py <file or folder> [form_type]
evaluate.py            accuracy report vs samples/answers.csv: python evaluate.py [-v]
engine/
  load.py              PDF/photo → page images
  preprocess.py        paper detection, orientation, deskew, contrast, blur score
  form_config.py       field definitions per form (name, page, type, Textract query)
  extract.py           LLM and Textract readings (the LLM call sits behind one function)
  compare.py           normalize, validate, compare → accepted / review
forms/<form_type>/templates/blank.pdf   blank form, used for orientation checks
```

Adding a new form type means adding its fields to `form_config.py` and its blank
PDF to `forms/<form_type>/templates/`.

## Run it locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; use source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
```

Create a `.env` file:

```
OPENAI_API_KEY=...
OPENAI_MODEL=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=...
```

Then:

```bash
streamlit run app.py                      # the UI
python run.py path/to/form.pdf            # or the command line → output/<name>.json
python evaluate.py -v                     # accuracy report (needs samples/answers.csv)
```

## Privacy

Filled forms contain personal data. `samples/`, `output/` and `.env` are never
committed. The deployed demo should only be used with forms filled with made-up
details.

## Tech

Python · OpenAI Responses API (structured outputs) · AWS Textract (Queries) ·
OpenCV · PyMuPDF · Streamlit
