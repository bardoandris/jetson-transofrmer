# MVTec-AD Toothbrush - Zero-Shot Inspection

Inspect the supplied image of a toothbrush head for visible defects.

Anomaly category: `defective`.
Use `contains_defect: false` and `defect_category: "good"` for a normal toothbrush. For a defect, set `contains_defect: true` and use `defective` exactly. Do not invent labels.

Judge the query image on its own; no reference images are provided. Return only the JSON object matching the schema supplied with the request.
