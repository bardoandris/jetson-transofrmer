# MVTec-AD Metal Nut - Zero-Shot Inspection

Inspect the supplied image of a metal nut for visible surface, shape, or orientation defects.

Anomaly categories: `bent`, `color`, `flip`, `scratch`.
Use `contains_defect: false` and `defect_category: "good"` for a normal nut. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Judge the query image on its own; no reference images are provided. Return only the JSON object matching the schema supplied with the request.
