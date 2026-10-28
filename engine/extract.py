import base64
import json
import os

import boto3
import cv2
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ILLEGIBLE = "ILLEGIBLE"
JPEG_QUALITY = 90
LLM_MODEL = os.getenv("OPENAI_MODEL", "gpt-6.1-terra")
LLM_DETAIL = os.getenv("OPENAI_IMAGE_DETAIL", "original")  # use "high" if the model rejects "original"
LLM_EFFORT = os.getenv("OPENAI_EFFORT", "low")

_client = None
_textract = None


def jpeg_bytes(image):
    ok, jpg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise ValueError("could not encode page image")
    return jpg.tobytes()


def call_llm(image, prompt, schema):
    # the only function that knows about the LLM provider; swap the model here
    global _client
    if _client is None:
        _client = OpenAI()  # reads OPENAI_API_KEY from the environment
    b64 = base64.b64encode(jpeg_bytes(image)).decode("ascii")
    response = _client.responses.create(
        model=LLM_MODEL,
        reasoning={"effort": LLM_EFFORT},
        input=[{
            "role": "user",
            "content": [
                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}",
                 "detail": LLM_DETAIL},
                {"type": "input_text", "text": prompt},
            ],
        }],
        text={"format": {"type": "json_schema", "name": "form_fields",
                         "schema": schema, "strict": True}},
    )
    if response.status != "completed":
        raise RuntimeError(f"LLM response {response.status}: {response.incomplete_details}")
    return json.loads(response.output_text)


def build_prompt(fields):
    lines = []
    for f in fields:
        line = f'- {f["name"]} (section "{f["section"]}"): {f["query"]}'
        if f["type"] == "choice":
            line += f' Return the one ticked option from {f["options"]}.'
        elif f["type"] == "multi_choice":
            line += f' Return every ticked option from {f["options"]}.'
        lines.append(line)
    return (
        "This is a page of a filled-in paper form, scanned or photographed, "
        "mostly handwritten.\n"
        "Read the fields below. Rules:\n"
        "- Copy exactly what is written. Do not correct spelling, reformat dates "
        "or numbers, or fill in anything that is not on the page.\n"
        f'- If something is written but you cannot read it with confidence, return "{ILLEGIBLE}" '
        "instead of guessing.\n"
        "- If part of the value is cut off by the page edge or covered, return "
        f'"{ILLEGIBLE}". Do not complete partial words.\n'
        '- If the field is blank or no box is ticked, return "" (or [] for lists).\n'
        "- Labels like City or Telephone Number repeat in different sections; "
        "only read the field from the section given.\n\n"
        "Fields:\n" + "\n".join(lines)
    )


def build_schema(fields):
    props = {}
    for f in fields:
        if f["type"] == "choice":
            props[f["name"]] = {"type": "string", "enum": f["options"] + ["", ILLEGIBLE]}
        elif f["type"] == "multi_choice":
            props[f["name"]] = {"type": "array",
                                "items": {"type": "string", "enum": f["options"] + [ILLEGIBLE]}}
        else:
            props[f["name"]] = {"type": "string"}
    return {"type": "object", "properties": props,
            "required": list(props), "additionalProperties": False}


def llm_read_page(image, fields):
    # one LLM call per page -> one reading per field
    if not fields:
        return []
    values = call_llm(image, build_prompt(fields), build_schema(fields))
    readings = []
    for f in fields:
        value = values.get(f["name"])
        illegible = value == ILLEGIBLE or (isinstance(value, list) and ILLEGIBLE in value)
        readings.append({"field": f["name"], "raw_value": value,
                         "confidence": None, "illegible": illegible})
    return readings


def call_textract(image, queries):
    # credentials and region come from the AWS profile (~/.aws) or AWS_* env vars
    global _textract
    if _textract is None:
        _textract = boto3.client("textract")
    response = _textract.analyze_document(
        Document={"Bytes": jpeg_bytes(image)},
        FeatureTypes=["QUERIES"],
        QueriesConfig={"Queries": queries},
    )
    return response["Blocks"]


def textract_read_page(image, fields):
    # one AnalyzeDocument call per page, one query per field, alias = field name
    if not fields:
        return []
    blocks = call_textract(image, [{"Text": f["query"], "Alias": f["name"]} for f in fields])
    by_id = {b["Id"]: b for b in blocks}
    answers = {}
    for b in blocks:
        if b["BlockType"] != "QUERY":
            continue
        for rel in b.get("Relationships", []):
            if rel["Type"] == "ANSWER":
                results = [by_id[i] for i in rel["Ids"]]
                answers[b["Query"]["Alias"]] = max(results, key=lambda r: r["Confidence"])
    readings = []
    for f in fields:
        a = answers.get(f["name"])  # None: Textract found no answer
        readings.append({"field": f["name"],
                         "raw_value": a["Text"] if a else None,
                         "confidence": round(a["Confidence"], 1) if a else None,
                         "illegible": False})
    return readings
