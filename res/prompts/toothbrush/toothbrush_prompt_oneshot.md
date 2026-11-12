# MVTec-AD Toothbrush - One-Shot Inspection

Inspect the supplied image of a toothbrush head for visible defects.

Anomaly category: `defective`.
Use `contains_defect: false` and `defect_category: "good"` for a normal toothbrush. For a defect, set `contains_defect: true` and use `defective` exactly. Do not invent labels.

Use the labeled reference images in this system message to learn the visual appearance of each category. A reference from `good` is labeled `good`. Classify the query independently; do not assume it matches a reference. Return only the JSON object matching the schema supplied with the request.
