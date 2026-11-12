# MVTec-AD Pill - Zero-Shot Inspection

Inspect the supplied image of a pharmaceutical pill for visible surface, imprint, or type defects.

Anomaly categories: `color`, `combined`, `contamination`, `crack`, `faulty_imprint`, `pill_type`, `scratch`.
Use `contains_defect: false` and `defect_category: "good"` for a normal pill. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Judge the query image on its own; no reference images are provided. Return only the JSON object matching the schema supplied with the request.
