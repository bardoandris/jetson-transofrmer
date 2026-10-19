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
            "enum": ["scratch", "dent", "crack", "discoloration", "other"],
        },
    },
    "required": ["contains_defect", "defect_category"],
    "additionalProperties": False,
}