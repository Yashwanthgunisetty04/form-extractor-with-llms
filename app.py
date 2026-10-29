import streamlit as st

from engine.form_config import FORMS
from ui.files import list_results, list_samples, load_reviewed

# usage: streamlit run app.py
st.set_page_config(page_title="Form Extraction", layout="wide")

st.title("Form Extraction POC")
st.write(
    "Reads handwritten form scans with two engines (an LLM and AWS Textract), compares "
    "the readings and flags fields that need a human check."
)

results = list_results()
reviewed = sum(load_reviewed(stem) is not None for stem in results)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Form types", len(FORMS))
c2.metric("Samples", len(list_samples()))
c3.metric("Processed", len(results))
c4.metric("Reviewed", reviewed)

st.page_link("pages/1_Process.py", label="Process: upload a form and run extraction")
st.page_link("pages/2_Review.py", label="Review: check flagged fields and save final values")
st.page_link("pages/3_Evaluate.py", label="Evaluate: accuracy against samples/answers.csv")
