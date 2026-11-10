# MVTec-AD Zipper - Zero-Shot Inspection

Inspect the supplied image of a zipper for visible defects in its teeth, fabric, or assembly.

Anomaly categories: `combined`, `broken_teeth`, `fabric_border`, `fabric_interior`, `rough`, `split_teeth`, `squeezed_teeth`.
Use `contains_defect: false` and `defect_category: "none"` for a normal zipper. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Judge the query image on its own; no reference images are provided. Return only the JSON object matching the schema supplied with the request.
