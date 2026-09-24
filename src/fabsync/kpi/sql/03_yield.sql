-- KPI-03 Material yield and offcut waste.

-- Cut yield per BOM line for sections bought in stock bars. Pieces = metres / cut length; each bar yields
-- floor(bar / cut length) pieces; the rest of the last bar and each bar's tail is offcut.
CREATE VIEW marts.material_yield_lines AS
WITH l AS (
    SELECT m.*, p.bar_length_mm, round(m.qty * 1000 / m.length_mm) AS pieces,
           floor(p.bar_length_mm / m.length_mm) AS pieces_per_bar
    FROM marts.bom_line_material m, marts.parameters p
    WHERE m.uom = 'M' AND m.section_type <> 'PLATE' AND m.length_mm BETWEEN 1 AND p.bar_length_mm)
SELECT wo_no, line_no, canonical_code, section_type, length_mm, pieces, pieces_per_bar,
       ceil(pieces / pieces_per_bar) AS bars,
       pieces * length_mm / 1000.0 AS used_m,
       ceil(pieces / pieces_per_bar) * bar_length_mm / 1000.0 AS bought_m,
       ceil(pieces / pieces_per_bar) * bar_length_mm / 1000.0 - pieces * length_mm / 1000.0 AS offcut_m,
       kg AS used_kg, kg * (ceil(pieces / pieces_per_bar) * bar_length_mm) / (pieces * length_mm) AS bought_kg,
       _source_file, _source_row
FROM l;

CREATE VIEW marts.material_yield_by_section_type AS
WITH cut AS (
    SELECT section_type, count(*) AS bom_lines, sum(used_kg) AS used_kg, sum(bought_kg) AS bought_kg
    FROM marts.material_yield_lines GROUP BY 1),
issued AS (SELECT section_type, sum(kg) AS issued_kg FROM marts.bom_line_material GROUP BY 1),
received AS (
    SELECT x.section_type, sum(CASE g.uom WHEN 'KG' THEN g.qty_received WHEN 'M' THEN g.qty_received * m.mass
                                          WHEN 'EA' THEN g.qty_received * m.kg_per_ea END) AS received_kg
    FROM staging.corvus_mrp_goods_received g
    JOIN core.material_xref x ON x.source_table = 'goods_received' AND x.source_code = g.material_code
    JOIN core.material_golden m ON m.canonical_code = coalesce(x.canonical_code, x.proposed_code,
                                                               split_part(x.candidates, ', ', 1))
    GROUP BY 1)
SELECT i.section_type, c.bom_lines, round(c.used_kg) AS cut_used_kg, round(c.bought_kg) AS cut_bought_kg,
       round(100 * c.used_kg / c.bought_kg, 1) AS cut_yield_pct,
       round(100 - 100 * c.used_kg / c.bought_kg, 1) AS offcut_waste_pct,
       round(i.issued_kg) AS issued_kg, round(r.received_kg) AS received_kg,
       round(r.received_kg / i.issued_kg, 2) AS received_to_issued
FROM issued i LEFT JOIN cut c USING (section_type) LEFT JOIN received r USING (section_type)
ORDER BY cut_yield_pct NULLS LAST, section_type;
