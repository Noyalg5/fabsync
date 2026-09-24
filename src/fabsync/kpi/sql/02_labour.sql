-- KPI-02 Labour variance, planned against booked hours.

CREATE VIEW marts.labour_variance_by_works_order AS
SELECT w.wo_no, w.job_no, w.site_code, w.part_code, w.status, w.status IN ('COMPLETE', 'CLOSED') AS complete,
       w.planned_hours, coalesce(b.hours, 0) AS actual_hours,
       coalesce(b.hours, 0) - w.planned_hours AS variance_hours,
       round(100 * (coalesce(b.hours, 0) - w.planned_hours) / nullif(w.planned_hours, 0), 1) AS variance_pct,
       w._source_file, w._source_row
FROM core.works_orders w
LEFT JOIN (SELECT wo_no, sum(hours) AS hours FROM core.time_bookings WHERE wo_matched GROUP BY 1) b
     ON b.wo_no = w.wo_no
WHERE w.status NOT IN ('PLANNED', 'CANCELLED');

CREATE VIEW marts.labour_variance_by_job AS
SELECT * FROM (
SELECT job_no, count(*) AS works_orders, count(*) FILTER (WHERE complete) AS complete_works_orders,
       sum(planned_hours) FILTER (WHERE complete) AS planned_hours,
       sum(actual_hours) FILTER (WHERE complete) AS actual_hours,
       sum(variance_hours) FILTER (WHERE complete) AS variance_hours,
       round(100 * sum(variance_hours) FILTER (WHERE complete)
             / nullif(sum(planned_hours) FILTER (WHERE complete), 0), 1) AS variance_pct
FROM marts.labour_variance_by_works_order GROUP BY 1)
ORDER BY abs(variance_pct) DESC NULLS LAST, job_no;
