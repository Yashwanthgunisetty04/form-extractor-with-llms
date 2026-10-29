import os
from pathlib import Path

import streamlit as st

from engine.form_config import FORMS
from engine.preprocess import BLUR_THRESHOLD
from run import process_file
from ui.files import SAMPLES, FILE_TYPES

st.set_page_config(page_title="Process", layout="wide")
st.title("Process a form")

# On Streamlit Cloud the API keys live in st.secrets; copy them into the environment,
# where the OpenAI and AWS clients look. Locally there are no secrets and .env is used.
try:
    for name, value in st.secrets.items():
        if isinstance(value, str):
            os.environ.setdefault(name, value)
except FileNotFoundError:
    pass
if not os.getenv("OPENAI_API_KEY"):
    try:
        found = list(st.secrets.keys())
    except FileNotFoundError:
        found = []
    # names only, never values
    st.error(f"OPENAI_API_KEY is not set. Secret names found: {found or 'none'}")

form_type = st.selectbox("Form type", list(FORMS))
upload = st.file_uploader("Filled form (PDF or photo)", type=[t[1:] for t in FILE_TYPES])

if upload:
    target = SAMPLES / upload.name
    overwrite = True
    if target.exists():
        st.warning(f"samples/{upload.name} already exists. Its row in answers.csv "
                   "describes that file, so only replace it with the same form.")
        overwrite = st.checkbox("Replace the existing file")
    if st.button("Run extraction", type="primary", disabled=not overwrite):
        SAMPLES.mkdir(exist_ok=True)
        target.write_bytes(upload.getvalue())
        with st.status(f"Processing {upload.name}...", expanded=True) as status:
            try:
                out_file, report = process_file(target, form_type, on_step=status.write)
            except Exception as e:
                status.update(label=f"Failed: {e}", state="error")
                st.exception(e)
                st.stop()
            status.update(label=f"Done: {out_file.name}", state="complete", expanded=False)
        # kept in session_state so reruns (any widget click) don't call the APIs again
        st.session_state["last_run"] = {"stem": Path(out_file).stem, "report": report}

run = st.session_state.get("last_run")
if run:
    report = run["report"]
    s = report["summary"]
    st.subheader(f"Result: {Path(report['file']).name}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Fields", s["fields"])
    c2.metric("Accepted", s["accepted"])
    c3.metric("Need review", s["review"])

    st.dataframe(
        [{"page": p["page"], "blur": p["blur"], "blurry": p["blurry"],
          "deskew angle": p["angle"], "rotation": p["rotation"]} for p in report["pages"]],
        hide_index=True,
    )
    for p in report["pages"]:
        if p["blurry"]:
            st.warning(f"Page {p['page']} looks blurry (score {p['blur']} < {BLUR_THRESHOLD}). "
                       "Check its fields carefully, or rescan.")

    if st.button("Open in Review"):
        st.session_state["review_stem"] = run["stem"]
        st.switch_page("pages/2_Review.py")
