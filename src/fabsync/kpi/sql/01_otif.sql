-- KPI-01 OTIF delivery performance.

-- One row per delivery note. A delivery note names a job, not a works order, so the works order it despatched
-- is taken as the one on the same job that finished most recently before despatch, within the window.
CREATE VIEW marts.otif_deliveries AS
WITH link AS (
    SELECT d.dn_no, w.wo_no, ww.kg,
           row_number() OVER (PARTITION BY d.dn_no ORDER BY d.despatch_date - w.actual_finish, w.wo_no) AS rn
    FROM core.delivery_notes d CROSS JOIN marts.parameters p
    JOIN core.works_orders w ON w.job_no = d.job_no
         AND d.despatch_date BETWEEN w.actual_finish AND w.actual_finish + p.despatch_window_days
    JOIN marts.works_order_weight ww ON ww.wo_no = w.wo_no)
SELECT d.dn_no, d.job_no, jc.customer_name, jc.site_code, d.despatch_date,
       CAST(date_trunc('month', d.despatch_date) AS DATE) AS month, d.promised_date, d.tonnage,
       l.wo_no, round(l.kg / 1000, 3) AS works_order_tonnes,
       d.promised_date IS NOT NULL AS measurable,
       d.despatch_date <= d.promised_date AS on_time,
       d.tonnage IS NOT NULL AND l.kg IS NOT NULL AND d.tonnage >= 0.98 * l.kg / 1000 AS in_full,
       d.despatch_date <= d.promised_date AND d.tonnage IS NOT NULL AND l.kg IS NOT NULL
           AND d.tonnage >= 0.98 * l.kg / 1000 AS otif,
       d.despatch_date - d.promised_date AS days_late,
       d._source_file, d._source_row
FROM core.delivery_notes d
LEFT JOIN link l ON l.dn_no = d.dn_no AND l.rn = 1
LEFT JOIN marts.job_customer jc ON jc.job_no = d.job_no;

CREATE VIEW marts.otif_by_month AS
SELECT month, count(*) AS deliveries, count(*) FILTER (WHERE measurable) AS measured,
       round(100 * avg(CAST(on_time AS INTEGER)) FILTER (WHERE measurable), 1) AS on_time_pct,
       round(100 * avg(CAST(in_full AS INTEGER)) FILTER (WHERE measurable), 1) AS in_full_pct,
       round(100 * avg(CAST(otif AS INTEGER)) FILTER (WHERE measurable), 1) AS otif_pct
FROM marts.otif_deliveries GROUP BY 1 ORDER BY 1;

CREATE VIEW marts.otif_by_customer AS
SELECT customer_name, count(*) AS deliveries, count(*) FILTER (WHERE measurable) AS measured,
       round(100 * avg(CAST(on_time AS INTEGER)) FILTER (WHERE measurable), 1) AS on_time_pct,
       round(100 * avg(CAST(in_full AS INTEGER)) FILTER (WHERE measurable), 1) AS in_full_pct,
       round(100 * avg(CAST(otif AS INTEGER)) FILTER (WHERE measurable), 1) AS otif_pct,
       round(avg(days_late) FILTER (WHERE measurable AND NOT on_time), 1) AS avg_days_late_when_late
FROM marts.otif_deliveries GROUP BY 1 ORDER BY otif_pct, customer_name;

CREATE VIEW marts.otif_by_site AS
SELECT site_code, count(*) AS deliveries, count(*) FILTER (WHERE measurable) AS measured,
       round(100 * avg(CAST(on_time AS INTEGER)) FILTER (WHERE measurable), 1) AS on_time_pct,
       round(100 * avg(CAST(in_full AS INTEGER)) FILTER (WHERE measurable), 1) AS in_full_pct,
       round(100 * avg(CAST(otif AS INTEGER)) FILTER (WHERE measurable), 1) AS otif_pct
FROM marts.otif_deliveries GROUP BY 1 ORDER BY 1;
