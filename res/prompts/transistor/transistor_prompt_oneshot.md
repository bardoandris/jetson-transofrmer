# MVTec-AD Transistor - One-Shot Inspection

Inspect the supplied image of a transistor and its leads for visible defects.

Anomaly categories: `bent_lead`, `cut_lead`, `damaged_case`, `misplaced`.
Use `contains_defect: false` and `defect_category: "good"` for a normal transistor. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Use the labeled reference images in this system message to learn the visual appearance of each category. A reference from `good` is labeled `good`. Classify the query independently; do not assume it matches a reference. Return only the JSON object matching the schema supplied with the request.
