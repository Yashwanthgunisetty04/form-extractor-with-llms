"""
Field configuration for each supported form.

Each field:
  name      snake_case key used in the output JSON
  page      1-based page number in the scanned PDF
  section   form section the field sits in (helps the LLM and avoids mixing up
            repeated labels like "City" or "Telephone Number")
  type      text | name | date | phone | email | zip | choice | multi_choice
  query     natural-language question for Textract Queries (checkbox fields
            too: Queries returns the label of the ticked box)
  options   allowed values for choice / multi_choice fields
"""

FORMS = {
    "fda_1932a": [
        # ---------------- Page 1: report + sender information ----------------
        {"name": "submission_type", "page": 1, "section": "Report",
         "type": "choice", "options": ["Initial", "Follow-up"],
         "query": "Which submission type is checked, Initial or Follow-up?"},
        {"name": "report_type", "page": 1, "section": "Report",
         "type": "multi_choice",
         "options": ["Adverse Event", "Product Problem", "Product Use Error"],
         "query": "Which report types are checked?"},
        {"name": "report_date", "page": 1, "section": "Report",
         "type": "date",
         "query": "What is the date of this report?"},
        {"name": "sender_first_name", "page": 1, "section": "Sender Information",
         "type": "name",
         "query": "What is the sender's first name?"},
        {"name": "sender_last_name", "page": 1, "section": "Sender Information",
         "type": "name",
         "query": "What is the sender's last name?"},
        {"name": "sender_city", "page": 1, "section": "Sender Information",
         "type": "text",
         "query": "What is the sender's city?"},
        {"name": "sender_state", "page": 1, "section": "Sender Information",
         "type": "text",
         "query": "What is the sender's state or province?"},
        {"name": "sender_zip", "page": 1, "section": "Sender Information",
         "type": "zip",
         "query": "What is the sender's postal or ZIP code?"},
        {"name": "sender_phone", "page": 1, "section": "Sender Information",
         "type": "phone",
         "query": "What is the sender's telephone number?"},
        {"name": "sender_email", "page": 1, "section": "Sender Information",
         "type": "email",
         "query": "What is the sender's email address?"},
        {"name": "sender_category", "page": 1, "section": "Sender Information",
         "type": "choice",
         "options": ["Veterinarian", "Animal Owner", "Physician", "Patient",
                     "Other Health Care Professional", "Other", "Unknown"],
         "query": "Which sender category is checked?"},

        # ---------------- Page 2: suspected product ----------------
        {"name": "product_name", "page": 2, "section": "Suspected Product Information",
         "type": "text",
         "query": "What is the name of the suspected product?"},
        {"name": "compounded_product", "page": 2, "section": "Suspected Product Information",
         "type": "choice", "options": ["Yes", "No", "Uncertain"],
         "query": "Is this a compounded product? Which box is checked?"},
        {"name": "first_exposure_date", "page": 2, "section": "Suspected Product Information",
         "type": "date",
         "query": "What is the date of first exposure?"},
        {"name": "last_exposure_date", "page": 2, "section": "Suspected Product Information",
         "type": "date",
         "query": "What is the date of last exposure?"},
        {"name": "dose_administered", "page": 2, "section": "Product Use Information",
         "type": "text",
         "query": "What dose was administered?"},
        {"name": "lot_number", "page": 2, "section": "Product Use Information",
         "type": "text",
         "query": "What is the lot number?"},
        {"name": "product_expiration_date", "page": 2, "section": "Product Use Information",
         "type": "date",
         "query": "What is the product expiration date?"},

        # ---------------- Page 3: manufacturer, event, species ----------------
        {"name": "manufacturer_name", "page": 3, "section": "Manufacturer Information",
         "type": "text",
         "query": "What is the name of the manufacturer or compounding pharmacy?"},
        {"name": "suspicion_level", "page": 3, "section": "Adverse Event Information",
         "type": "choice", "options": ["High", "Medium", "Low", "Unknown"],
         "query": "Which level of suspicion is checked?"},
        {"name": "outcome", "page": 3, "section": "Adverse Event Information",
         "type": "choice", "options": ["Recovered", "Died", "Other"],
         "query": "Which outcome is checked?"},
        {"name": "species", "page": 3, "section": "Species and Related Information",
         "type": "choice",
         "options": ["Budgerigar", "Cat", "Cattle", "Cockatiel", "Cockatoo",
                     "Dog", "Ferret", "Fish", "Goat", "Guinea Pig", "Horse",
                     "Human", "Parrot", "Pig", "Rabbit", "Sheep", "Other"],
         "query": "Which species is checked?"},
        {"name": "breed", "page": 3, "section": "Species and Related Information",
         "type": "text",
         "query": "What is the breed?"},
        {"name": "age", "page": 3, "section": "Species and Related Information",
         "type": "text",
         "query": "What is the age?"},
        {"name": "weight", "page": 3, "section": "Species and Related Information",
         "type": "text",
         "query": "What is the weight?"},
    ]
}


def get_fields(form_type: str) -> list[dict]:
    if form_type not in FORMS:
        raise ValueError(f"Unknown form type: {form_type}. Known: {list(FORMS)}")
    return FORMS[form_type]


def get_fields_for_page(form_type: str, page: int) -> list[dict]:
    return [f for f in get_fields(form_type) if f["page"] == page]


if __name__ == "__main__":
    for form_type, fields in FORMS.items():
        print(f"{form_type}: {len(fields)} fields")
        for p in sorted({f["page"] for f in fields}):
            names = [f["name"] for f in get_fields_for_page(form_type, p)]
            print(f"  page {p}: {len(names)} -> {', '.join(names)}")