# MVTec-AD Bottle - Zero-Shot Inspection

Inspect the supplied image of a glass bottle for visible defects.

Anomaly categories: `broken_large`, `broken_small`, `contamination`.
Use `contains_defect: false` and `defect_category: "good"` for a normal bottle. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Judge the query image on its own; no reference images are provided. Return only the JSON object matching the schema supplied with the request.
