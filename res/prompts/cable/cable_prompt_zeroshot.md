# MVTec-AD Cable - Zero-Shot Inspection

Inspect the supplied image of an insulated cable and its wires for visible defects.

Anomaly categories: `bent_wire`, `cable_swap`, `combined`, `cut_inner_insulation`, `cut_outer_insulation`, `missing_cable`, `missing_wire`, `poke_insulation`.
Use `contains_defect: false` and `defect_category: "none"` for a normal cable. For a defect, set `contains_defect: true` and choose the matching category exactly. Do not invent labels.

Judge the query image on its own; no reference images are provided. Return only the JSON object matching the schema supplied with the request.
