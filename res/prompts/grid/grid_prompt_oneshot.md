# MVTec-AD Grid - One-Shot Inspection

Inspect the supplied image of a regular grid surface for structural or material defects.

Anomaly categories: `bent`, `broken`, `glue`, `metal_contamination`, `thread`.
Use `contains_defect: false` and `defect_category: "none"` for a normal grid. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Use the labeled reference images in this system message to learn the visual appearance of each category. A reference from `good` is labeled `none`. Classify the query independently; do not assume it matches a reference. Return only the JSON object matching the schema supplied with the request.
