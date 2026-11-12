# MVTec-AD Cable - One-Shot Inspection

Inspect the supplied image of an insulated cable and its wires for visible defects.

Anomaly categories: `bent_wire`, `cable_swap`, `combined`, `cut_inner_insulation`, `cut_outer_insulation`, `missing_cable`, `missing_wire`, `poke_insulation`.
Use `contains_defect: false` and `defect_category: "good"` for a normal cable. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Use the labeled reference images in this system message to learn the visual appearance of each category. A reference from `good` is labeled `good`. Classify the query independently; do not assume it matches a reference. Return only the JSON object matching the schema supplied with the request.
