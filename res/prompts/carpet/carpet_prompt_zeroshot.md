# MVTec-AD Carpet - Zero-Shot Inspection

Inspect the supplied image of a carpet surface for visible texture or material defects.

Anomaly categories: `color`, `cut`, `hole`, `metal_contamination`, `thread`.
Use `contains_defect: false` and `defect_category: "none"` for a normal carpet. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Judge the query image on its own; no reference images are provided. Return only the JSON object matching the schema supplied with the request.
