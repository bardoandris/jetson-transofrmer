# MVTec-AD Carpet - One-Shot Inspection

Inspect the supplied image of a carpet surface for visible texture or material defects.

Anomaly categories: `color`, `cut`, `hole`, `metal_contamination`, `thread`.
Use `contains_defect: false` and `defect_category: "none"` for a normal carpet. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Use the labeled reference images in this system message to learn the visual appearance of each category. A reference from `good` is labeled `none`. Classify the query independently; do not assume it matches a reference. Return only the JSON object matching the schema supplied with the request.
