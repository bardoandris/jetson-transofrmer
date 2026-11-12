import pydantic


def create_category_schema(defect_categories: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "contains_defect": {
                "type": "boolean",
            },
            "defect_category": {
                "type": "string",
                "enum": [*sorted(set(defect_categories)), "good"],
            },
        },
        "required": ["contains_defect", "defect_category"],
        "additionalProperties": False,
    }


defect_schema = {
    "type": "object",
    "properties": {
        "contains_defect": {
            "type": "boolean",
        }
    },
    "required": ["contains_defect"],
    "additionalProperties": False,
}

category_schema = {
    "type": "object",
    "properties": {
        "contains_defect": {
            "type": "boolean",
        },
        "defect_category": {
            "type": "string",
            "enum": ["leads", "casing", "misplaced", "good"],
        },
    },
    "required": ["contains_defect", "defect_category"],
    "additionalProperties": False,
}