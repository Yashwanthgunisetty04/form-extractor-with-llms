import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from engine.form_config import get_fields
from engine.compare import normalize, key, ILLEGIBLE

# usage: python evaluate.py [-v] [form_type]
# compares output/<form>.json (from run.py) with samples/answers.csv; no API calls.
# -v also lists every field where an engine was wrong.
ROOT = Path(__file__).parent
ANSWERS = ROOT / "samples" / "answers.csv"
OUT = ROOT / "output"
UNKNOWN = "?"


def same(value, truth, field):
    return key(normalize(value, field)) == key(truth)


def pct(n, total):
    return f"{100 * n / total:.0f}%" if total else "-"


def evaluate(output_dir=OUT, answers_csv=ANSWERS, form_type="fda_1932a"):
    # scores every form that has both a result file and a filled answers row
    output_dir, answers_csv = Path(output_dir), Path(answers_csv)
    fields = {f["name"]: f for f in get_fields(form_type)}
    stats = defaultdict(Counter)  # field name -> counts
    reasons = Counter()            # review reasons on scored fields
    accepted_wrong, mistakes, skipped = [], [], []
    forms = 0

    answers = []
    if answers_csv.exists():
        with answers_csv.open(newline="", encoding="utf-8-sig") as fh:
            answers = list(csv.DictReader(fh))

    for row in answers:
        result_file = output_dir / f"{Path(row['file']).stem}.json"
        if not result_file.exists():
            skipped.append(f"{row['file']}: no {result_file.name} (run: python run.py samples)")
            continue
        results = {r["field"]: r for r in json.loads(result_file.read_text())["fields"]}
        filled = [n for n in fields if row.get(n, "").strip() != ""]
        if not filled:
            skipped.append(f"{row['file']}: answers not filled in")
            continue
        forms += 1

        for name, field in fields.items():
            cell = row.get(name, "").strip()
            if cell == UNKNOWN or name not in results:
                continue
            truth = normalize(cell or None, field)  # empty cell = blank on the form
            r = results[name]
            s = stats[name]
            s["scored"] += 1

            llm_illegible = r["llm"] == ILLEGIBLE or (isinstance(r["llm"], list)
                                                     and ILLEGIBLE in r["llm"])
            llm_ok = not llm_illegible and same(r["llm"], truth, field)
            textract_ok = same(r["textract"], truth, field)
            agree = not llm_illegible and same(r["textract"], normalize(r["llm"], field), field)

            s["llm_ok"] += llm_ok
            s["llm_illegible"] += llm_illegible
            s["textract_ok"] += textract_ok
            s["agree"] += agree
            s["agree_ok"] += agree and llm_ok
            if r["status"] == "accepted":
                s["accepted"] += 1
                if llm_ok:
                    s["accepted_ok"] += 1
                else:
                    accepted_wrong.append({"file": row["file"], "field": name,
                                           "accepted": r["value"], "answer": cell})
            else:
                s["review_llm_ok"] += llm_ok  # sent to review although the LLM was right
                for reason in r["reason"].split("; "):
                    reasons[reason] += 1
            if not llm_ok or not textract_ok:
                mistakes.append({"file": row["file"], "field": name, "answer": cell,
                                 "llm": r["llm"], "textract": r["textract"],
                                 "textract_confidence": r["textract_confidence"],
                                 "status": r["status"]})

    return {
        "forms": forms,
        "fields": {n: stats[n] for n in fields if stats[n]["scored"]},  # in form order
        "total": sum(stats.values(), Counter()),
        "reasons": reasons,
        "accepted_wrong": accepted_wrong,
        "mistakes": mistakes,
        "skipped": skipped,
    }


def main():
    args = sys.argv[1:]
    verbose = "-v" in args
    args = [a for a in args if a != "-v"]
    form_type = args[0] if args else "fda_1932a"
    result = evaluate(form_type=form_type)

    for message in result["skipped"]:
        print(f"skip {message}")
    if not result["forms"]:
        sys.exit("nothing to evaluate: fill in samples/answers.csv and run run.py first")

    total = result["total"]
    n = total["scored"]
    print(f"\n{result['forms']} forms, {n} scored fields\n")

    print(f"{'field':25} {'n':>3} {'LLM':>5} {'Textr':>5} {'agree':>5} "
          f"{'agree ok':>8} {'accept':>6} {'acc ok':>6}")
    for name, s in result["fields"].items():
        print(f"{name:25} {s['scored']:>3} {pct(s['llm_ok'], s['scored']):>5} "
              f"{pct(s['textract_ok'], s['scored']):>5} {pct(s['agree'], s['scored']):>5} "
              f"{pct(s['agree_ok'], s['agree']):>8} {pct(s['accepted'], s['scored']):>6} "
              f"{pct(s['accepted_ok'], s['accepted']):>6}")

    review = n - total["accepted"]
    print(f"""
Accuracy
  LLM correct            {total['llm_ok']}/{n} ({pct(total['llm_ok'], n)})
  LLM said ILLEGIBLE     {total['llm_illegible']}/{n} ({pct(total['llm_illegible'], n)})
  Textract correct       {total['textract_ok']}/{n} ({pct(total['textract_ok'], n)})

Agreement
  engines agree          {total['agree']}/{n} ({pct(total['agree'], n)})
  correct when agreeing  {total['agree_ok']}/{total['agree']} ({pct(total['agree_ok'], total['agree'])})

Review flagging
  accepted               {total['accepted']}/{n} ({pct(total['accepted'], n)})
  accepted and correct   {total['accepted_ok']}/{total['accepted']} ({pct(total['accepted_ok'], total['accepted'])})
  review                 {review}/{n} ({pct(review, n)})
  review, LLM was right  {total['review_llm_ok']}/{review} ({pct(total['review_llm_ok'], review)})""")

    if result["reasons"]:
        print("\nReview reasons (a field can have several)")
        for reason, count in result["reasons"].most_common():
            print(f"  {reason:28} {count}")

    print(f"\nAccepted but WRONG: {len(result['accepted_wrong'])}")
    for w in result["accepted_wrong"]:
        print(f"  {w['file']} {w['field']}: accepted {w['accepted']!r}, answer {w['answer']!r}")

    if verbose:
        print(f"\nFields where an engine was wrong: {len(result['mistakes'])}")
        for m in result["mistakes"]:
            print(f"  {m['file']} {m['field']} [{m['status']}]\n"
                  f"      answer {m['answer']!r}  llm {m['llm']!r}  "
                  f"textract {m['textract']!r} ({m['textract_confidence']})")


if __name__ == "__main__":
    main()
