import json

import streamlit as st

from engine.form_config import get_fields
from engine.compare import normalize, key, is_valid, ILLEGIBLE
from ui.files import (list_results, load_result, load_reviewed, page_image,
                      save_reviewed, reviewed_path, field_label)

st.set_page_config(page_title="Review", layout="wide")
st.title("Review")

stems = list_results()
if not stems:
    st.info("No results yet. Process a form first.")
    st.stop()

wanted = st.session_state.get("review_stem")
stem = st.selectbox("Result", stems, index=stems.index(wanted) if wanted in stems else 0,
                    format_func=lambda s: s + ("  (reviewed)" if reviewed_path(s).exists() else ""))
st.session_state["review_stem"] = stem

result = load_result(stem)
fields = {f["name"]: f for f in get_fields(result["form_type"])}
rows = [r for r in result["fields"] if r["field"] in fields]
saved = {f["field"]: f["final"] for f in (load_reviewed(stem) or {}).get("fields", [])}
pages = {p["page"]: p for p in result["pages"]}


def blank(field):
    return [] if field["type"] == "multi_choice" else ""


def suggestion(r, field):
    # what the reviewer starts from: the accepted value, else the LLM reading (unless illegible)
    if r["status"] == "accepted":
        return r["value"]
    llm = r["llm"]
    if llm is None or llm == ILLEGIBLE or (isinstance(llm, list) and ILLEGIBLE in llm):
        return blank(field)
    return normalize(llm, field)


def show(value):
    if value is None:
        return "—"
    if isinstance(value, list):
        return ", ".join(value) or "(blank)"
    return value or "(blank)"


def final_input(r, field):
    # input that matches the field type, prefilled with the saved review or the suggestion
    start = saved.get(r["field"], suggestion(r, field))
    k = f"{stem}|{r['field']}"
    if field["type"] == "choice":
        options = [""] + field["options"]
        return st.selectbox("Final value", options, key=k,
                            index=options.index(start) if start in options else 0,
                            format_func=lambda o: o or "(blank)")
    if field["type"] == "multi_choice":
        return st.multiselect("Final value", field["options"], key=k,
                              default=[o for o in start if o in field["options"]])
    hint = "mm/dd/yyyy or YYYY-MM-DD" if field["type"] == "date" else None
    return st.text_input("Final value", value=start, key=k, help=hint)


def field_card(r):
    field = fields[r["field"]]
    with st.container(border=True):
        st.markdown(f"**{field_label(field)}**")
        conf = r["textract_confidence"]
        st.markdown(f"LLM: `{show(r['llm'])}`  \n"
                    f"Textract: `{show(r['textract'])}`"
                    + (f" ({conf:.0f})" if conf is not None else ""))
        if r["status"] == "review":
            st.caption(f":orange[{r['reason']}]")
        return final_input(r, field)


s = result["summary"]
c1, c2, c3 = st.columns(3)
c1.metric("Fields", s["fields"])
c2.metric("Accepted", s["accepted"])
c3.metric("Need review", s["review"])

only_review = st.toggle("Only fields needing review", value=True)
finals = {}

for page_no in sorted({r["page"] for r in rows}):
    on_page = [r for r in rows if r["page"] == page_no
               and (r["status"] == "review" or not only_review)]
    if not on_page:
        continue
    st.subheader(f"Page {page_no}")
    left, right = st.columns([3, 2])
    with left:
        image, info = page_image(stem, page_no), pages.get(page_no)
        if image:
            st.image(str(image), width="stretch")
            st.caption(f"blur {info['blur']}{' (blurry)' if info['blurry'] else ''}, "
                       f"deskew {info['angle']}°, rotation {info['rotation']}°")
        else:
            st.info("No page image (page missing from the scan).")
    with right:
        for r in on_page:
            finals[r["field"]] = field_card(r)

if only_review:
    accepted = [r for r in rows if r["status"] == "accepted"]
    with st.expander(f"Accepted fields ({len(accepted)})"):
        for r in accepted:
            field = fields[r["field"]]
            st.markdown(f"**{field_label(field)}** (page {r['page']}): `{show(r['value'])}`")
            finals[r["field"]] = final_input(r, field)


def build_review():
    out, invalid = [], []
    for r in rows:
        field = fields[r["field"]]
        suggested = suggestion(r, field)
        final = normalize(finals[r["field"]], field)
        if not is_valid(final, field):
            invalid.append(r["field"])
        out.append({"field": r["field"], "page": r["page"], "status": r["status"],
                    "pipeline_value": r["value"], "suggested": suggested, "final": final,
                    "changed": key(final) != key(suggested)})
    return {"file": result["file"], "form_type": result["form_type"],
            "source": f"{stem}.json",
            "summary": {"fields": len(out), "changed": sum(f["changed"] for f in out),
                        "invalid": invalid},
            "fields": out}


review = build_review()
st.divider()
for name in review["summary"]["invalid"]:
    st.warning(f"{field_label(fields[name])}: "
               f"`{show(next(f['final'] for f in review['fields'] if f['field'] == name))}` "
               f"does not look like a valid {fields[name]['type']}.")
st.write(f"{review['summary']['changed']} field(s) changed from the suggested value.")

b1, b2 = st.columns([1, 4])
if b1.button("Save review", type="primary"):
    save_reviewed(stem, review)
    st.success(f"Saved to output/{reviewed_path(stem).name}")
b2.download_button("Download JSON", json.dumps(review, indent=2),
                   file_name=f"{stem}_reviewed.json", mime="application/json")
