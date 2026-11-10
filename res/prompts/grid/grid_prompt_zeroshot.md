# MVTec-AD Grid - Zero-Shot Inspection

Inspect the supplied image of a regular grid surface for structural or material defects.

Anomaly categories: `bent`, `broken`, `glue`, `metal_contamination`, `thread`.
Use `contains_defect: false` and `defect_category: "none"` for a normal grid. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Judge the query image on its own; no reference images are provided. Return only the JSON object matching the schema supplied with the request.
