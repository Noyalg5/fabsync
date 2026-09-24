-- KPI-05 Three-way match exception rate and value at risk. Built on recon.three_way_lines.
-- The rate is over purchase order lines, the population a three-way match applies to. Invoices with no PO
-- cannot be matched at all; they are counted separately and included in value at risk.
-- Lines not yet due are excluded: they cannot be judged yet.

CREATE VIEW marts.three_way_exception_rate AS
SELECT CAST(date_trunc('month', coalesce(order_date, invoice_date)) AS DATE) AS month,
       count(*) FILTER (WHERE line_type = 'PO line') AS po_lines_assessed,
       count(*) FILTER (WHERE line_type = 'PO line' AND is_exception) AS po_line_exceptions,
       round(100 * avg(CAST(is_exception AS INTEGER)) FILTER (WHERE line_type = 'PO line'), 1) AS exception_rate_pct,
       count(*) FILTER (WHERE line_type = 'invoice') AS invoices_with_no_po,
       round(sum(value_at_risk), 2) AS value_at_risk
FROM recon.three_way_lines WHERE category <> 'not yet due'
GROUP BY 1 ORDER BY 1;

CREATE VIEW marts.three_way_value_at_risk AS
SELECT category, count(*) AS lines, round(sum(value_at_risk), 2) AS value_at_risk,
       count(*) FILTER (WHERE age_days > 90) AS over_90_days
FROM recon.three_way_lines WHERE category <> 'not yet due'
GROUP BY 1 ORDER BY value_at_risk DESC;
