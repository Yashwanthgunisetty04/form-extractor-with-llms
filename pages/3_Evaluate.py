import pandas as pd
import streamlit as st

from engine.form_config import FORMS
from evaluate import evaluate
from ui.files import OUT, ANSWERS

st.set_page_config(page_title="Evaluate", layout="wide")
st.title("Evaluate")
st.caption("Pipeline results (output/<name>.json) against samples/answers.csv. "
           "No API calls; reviewer edits are not counted.")

form_type = st.selectbox("Form type", list(FORMS))
result = evaluate(OUT, ANSWERS, form_type)

for message in result["skipped"]:
    st.caption(f"Skipped {message}")
if not result["forms"]:
    st.info("Nothing to evaluate: fill in samples/answers.csv and process the forms first.")
    st.stop()


def pct(n, total):
    return 100 * n / total if total else None


t = result["total"]
n = t["scored"]
review = n - t["accepted"]
st.write(f"{result['forms']} forms, {n} scored fields")

c1, c2, c3, c4 = st.columns(4)
c1.metric("LLM accuracy", f"{pct(t['llm_ok'], n):.0f}%", help=f"{t['llm_ok']}/{n} correct")
c2.metric("Textract accuracy", f"{pct(t['textract_ok'], n):.0f}%",
          help=f"{t['textract_ok']}/{n} correct")
c3.metric("Engines agree", f"{pct(t['agree'], n):.0f}%",
          help=f"{t['agree']}/{n}; correct when agreeing: {t['agree_ok']}/{t['agree']}")
c4.metric("Accepted but WRONG", len(result["accepted_wrong"]), border=True,
          help="Fields accepted without review whose value is wrong: the key safety number")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Accepted", f"{t['accepted']}/{n}")
c2.metric("Accepted and correct", f"{t['accepted_ok']}/{t['accepted']}")
c3.metric("Sent to review", f"{review}/{n}")
c4.metric("Review, LLM was right", f"{t['review_llm_ok']}/{review}",
          help="Review work that turned out unnecessary")

if result["accepted_wrong"]:
    st.error("Accepted but WRONG")
    st.dataframe(pd.DataFrame(result["accepted_wrong"]), hide_index=True)

st.subheader("Per field")
table = pd.DataFrame([
    {"field": name, "n": s["scored"],
     "LLM": pct(s["llm_ok"], s["scored"]), "Textract": pct(s["textract_ok"], s["scored"]),
     "agree": pct(s["agree"], s["scored"]), "agree ok": pct(s["agree_ok"], s["agree"]),
     "accepted": pct(s["accepted"], s["scored"]), "accepted ok": pct(s["accepted_ok"], s["accepted"])}
    for name, s in result["fields"].items()
])
bar = dict(format="%.0f%%", min_value=0, max_value=100)
st.dataframe(table, hide_index=True, column_config={
    col: st.column_config.ProgressColumn(col, **bar)
    for col in ("LLM", "Textract", "agree", "agree ok", "accepted", "accepted ok")
})

with st.expander("Review reasons (a field can have several)"):
    st.dataframe(pd.DataFrame(result["reasons"].most_common(), columns=["reason", "count"]),
                 hide_index=True)

with st.expander(f"Fields where an engine was wrong ({len(result['mistakes'])})"):
    st.dataframe(pd.DataFrame(result["mistakes"]).astype(str), hide_index=True)
