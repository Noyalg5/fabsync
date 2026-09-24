-- KPI-04 Stock accuracy against target. Built on the stock reconciliation (recon.stock_lines).

CREATE VIEW marts.stock_accuracy AS
SELECT coalesce(site_code, 'All sites') AS site_code, count(*) AS counted_lines,
       count(*) FILTER (WHERE accurate) AS accurate_lines,
       round(100 * avg(CAST(accurate AS INTEGER)), 1) AS accuracy_pct,
       any_value(p.stock_accuracy_target_pct) AS target_pct,
       round(100 * avg(CAST(accurate AS INTEGER)), 1) >= any_value(p.stock_accuracy_target_pct) AS meets_target,
       round(sum(value_error), 2) AS value_error, round(sum(book_value), 2) AS book_value
FROM recon.stock_lines, marts.parameters p
GROUP BY ROLLUP (site_code) ORDER BY site_code = 'All sites', site_code;
