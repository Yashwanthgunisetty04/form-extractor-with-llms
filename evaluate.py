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
ANSWERS = Path("samples/answers.csv")
OUT = Path("output")
UNKNOWN = "?"


def same(value, truth, field):
    return key(normalize(value, field)) == key(truth)


def pct(n, total):
    return f"{100 * n / total:.0f}%" if total else "-"


def main():
    args = sys.argv[1:]
    verbose = "-v" in args
    args = [a for a in args if a != "-v"]
    form_type = args[0] if args else "fda_1932a"
    fields = {f["name"]: f for f in get_fields(form_type)}

    with ANSWERS.open(newline="", encoding="utf-8") as fh:
        answers = list(csv.DictReader(fh))

    stats = defaultdict(Counter)  # field name -> counts
    reasons = Counter()            # review reasons on scored fields
    accepted_wrong, mistakes = [], []
    forms = 0

    for row in answers:
        result_file = OUT / f"{Path(row['file']).stem}.json"
        if not result_file.exists():
            print(f"skip {row['file']}: no {result_file} (run: python run.py samples)")
            continue
        results = {r["field"]: r for r in json.loads(result_file.read_text())["fields"]}
        filled = [n for n in fields if row.get(n, "").strip() != ""]
        if not filled:
            print(f"skip {row['file']}: answers not filled in")
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
                    accepted_wrong.append((row["file"], name, r["value"], cell))
            else:
                s["review_llm_ok"] += llm_ok  # sent to review although the LLM was right
                for reason in r["reason"].split("; "):
                    reasons[reason] += 1
            if not llm_ok or not textract_ok:
                mistakes.append((row["file"], name, cell, r["llm"], r["textract"],
                                 r["textract_confidence"], r["status"]))

    if not forms:
        sys.exit("nothing to evaluate: fill in samples/answers.csv and run run.py first")

    total = sum(stats.values(), Counter())
    n = total["scored"]
    print(f"\n{forms} forms, {n} scored fields\n")

    print(f"{'field':25} {'n':>3} {'LLM':>5} {'Textr':>5} {'agree':>5} "
          f"{'agree ok':>8} {'accept':>6} {'acc ok':>6}")
    for name in fields:
        s = stats[name]
        if not s["scored"]:
            continue
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

    if reasons:
        print("\nReview reasons (a field can have several)")
        for reason, count in reasons.most_common():
            print(f"  {reason:28} {count}")

    print(f"\nAccepted but WRONG: {len(accepted_wrong)}")
    for file, name, value, cell in accepted_wrong:
        print(f"  {file} {name}: accepted {value!r}, answer {cell!r}")

    if verbose:
        print(f"\nFields where an engine was wrong: {len(mistakes)}")
        for file, name, cell, llm, textract, conf, status in mistakes:
            print(f"  {file} {name} [{status}]\n"
                  f"      answer {cell!r}  llm {llm!r}  textract {textract!r} ({conf})")


if __name__ == "__main__":
    main()
