-- KPI-09 NCR rate and cost of quality as a percentage of turnover.

CREATE VIEW marts.quality_cost_by_month AS
WITH n AS (SELECT CAST(date_trunc('month', raised_date) AS DATE) AS month, count(*) AS ncrs,
                  count(cost_impact) AS ncrs_costed, sum(cost_impact) AS ncr_cost
           FROM core.ncrs GROUP BY 1),
     s AS (SELECT CAST(date_trunc('month', invoice_date) AS DATE) AS month, sum(net_amount) AS turnover
           FROM staging.finance_sales_invoices GROUP BY 1),
     d AS (SELECT CAST(date_trunc('month', despatch_date) AS DATE) AS month, sum(tonnage) AS tonnes
           FROM core.delivery_notes GROUP BY 1)
SELECT coalesce(n.month, s.month, d.month) AS month, coalesce(n.ncrs, 0) AS ncrs, coalesce(n.ncrs_costed, 0) AS ncrs_costed,
       round(coalesce(n.ncr_cost, 0), 2) AS ncr_cost, round(coalesce(s.turnover, 0), 2) AS turnover,
       round(coalesce(d.tonnes, 0), 1) AS tonnes_despatched,
       round(100 * coalesce(n.ncr_cost, 0) / nullif(s.turnover, 0), 2) AS cost_of_quality_pct,
       round(100 * coalesce(n.ncrs, 0) / nullif(d.tonnes, 0), 2) AS ncrs_per_100_tonnes
FROM n FULL JOIN s ON s.month = n.month FULL JOIN d ON d.month = coalesce(n.month, s.month)
ORDER BY 1;

CREATE VIEW marts.ncr_by_category AS
SELECT mode(category_raw) AS category, count(*) AS ncrs, count(cost_impact) AS ncrs_costed,
       round(sum(cost_impact), 2) AS ncr_cost, count(*) FILTER (WHERE closed_date IS NULL) AS open_ncrs
FROM core.ncrs GROUP BY lower(category_raw) ORDER BY ncr_cost DESC NULLS LAST;
