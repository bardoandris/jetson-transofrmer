# MVTec-AD Tile - Zero-Shot Inspection

Inspect the supplied image of a tile surface for visible texture or material defects.

Anomaly categories: `crack`, `glue_strip`, `gray_stroke`, `oil`, `rough`.
Use `contains_defect: false` and `defect_category: "none"` for a normal tile. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Judge the query image on its own; no reference images are provided. Return only the JSON object matching the schema supplied with the request.
