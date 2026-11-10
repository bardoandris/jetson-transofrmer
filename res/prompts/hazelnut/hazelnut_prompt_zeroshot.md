# MVTec-AD Hazelnut - Zero-Shot Inspection

Inspect the supplied image of a hazelnut for visible surface or shape defects.

Anomaly categories: `crack`, `cut`, `hole`, `print`.
Use `contains_defect: false` and `defect_category: "none"` for a normal hazelnut. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Judge the query image on its own; no reference images are provided. Return only the JSON object matching the schema supplied with the request.
