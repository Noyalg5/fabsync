-- Shared building blocks for the KPI views. All data is synthetic.
-- marts.parameters is a one-row table written by the KPI build from config.

-- Average price paid per kg for each canonical material, from Corvus purchase orders.
CREATE VIEW marts.material_price AS
SELECT x.canonical_code,
       sum(p.qty * p.unit_price) / sum(CASE p.uom WHEN 'KG' THEN p.qty WHEN 'M' THEN p.qty * g.mass
                                                   WHEN 'EA' THEN p.qty * g.kg_per_ea END) AS price_per_kg
FROM staging.corvus_mrp_purchase_orders p
JOIN core.material_xref x ON x.source_table = 'purchase_orders' AND x.source_code = p.material_code
     AND x.status = 'auto'
JOIN core.material_golden g ON g.canonical_code = x.canonical_code
GROUP BY 1;

-- Every BOM line with its canonical material, section type, kilograms and value.
CREATE VIEW marts.bom_line_material AS
SELECT b.wo_no, b.line_no, x.canonical_code, g.section_type, b.uom, b.qty, b.length_mm,
       CASE b.uom WHEN 'KG' THEN b.qty ELSE b.qty * g.mass END AS kg,
       CASE b.uom WHEN 'KG' THEN b.qty ELSE b.qty * g.mass END * pr.price_per_kg AS material_value,
       b._source_file, b._source_row
FROM staging.corvus_mrp_bom_lines b
JOIN core.material_xref x ON x.source_table = 'bom_lines' AND x.source_code = b.material_code
     AND x.source_description IS NOT DISTINCT FROM b.description AND x.source_grade IS NOT DISTINCT FROM b.grade
     AND x.source_section_type IS NOT DISTINCT FROM b.section_type
JOIN core.material_golden g ON g.canonical_code = x.canonical_code
LEFT JOIN marts.material_price pr ON pr.canonical_code = x.canonical_code;

-- Weight and material value of each works order.
CREATE VIEW marts.works_order_weight AS
SELECT wo_no, sum(kg) AS kg, sum(material_value) AS material_value FROM marts.bom_line_material GROUP BY 1;

-- Delivery note that despatched each finished works order: same job, despatched within the window after finish.
CREATE VIEW marts.works_order_despatch AS
SELECT w.wo_no, min(d.dn_no) AS dn_no, min(d.despatch_date) AS despatch_date
FROM core.works_orders w CROSS JOIN marts.parameters p
JOIN core.delivery_notes d ON d.job_no = w.job_no
     AND d.despatch_date BETWEEN w.actual_finish AND w.actual_finish + p.despatch_window_days
WHERE w.actual_finish IS NOT NULL
GROUP BY 1;

-- Customer and site of each Corvus job. Corvus holds only a customer order reference, so the name is the
-- customer finance invoices the job to.
CREATE VIEW marts.job_customer AS
SELECT j.job_no, j.finance_job_code, j.site_code, s.site_name, coalesce(c.customer_name, '(not invoiced)') AS customer_name
FROM core.jobs j
LEFT JOIN core.sites s ON s.site_code = j.site_code
LEFT JOIN (SELECT job_code, mode(customer_name) AS customer_name FROM staging.finance_sales_invoices GROUP BY 1) c
     ON c.job_code = j.finance_job_code;
