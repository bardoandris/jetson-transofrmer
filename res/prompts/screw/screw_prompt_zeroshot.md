# MVTec-AD Screw - Zero-Shot Inspection

Inspect the supplied image of a screw for visible thread, surface, or shape defects.

Anomaly categories: `manipulated_front`, `scratch_head`, `scratch_neck`, `thread_side`, `thread_top`.
Use `contains_defect: false` and `defect_category: "good"` for a normal screw. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Judge the query image on its own; no reference images are provided. Return only the JSON object matching the schema supplied with the request.
