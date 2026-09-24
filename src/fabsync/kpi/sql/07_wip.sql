-- KPI-07 WIP value and ageing.
-- WIP: works orders started (planned start on or before the as-of date), not cancelled or closed, and not
-- yet despatched. Valued at BOM material plus hours booked to date at the standard rate.

CREATE VIEW marts.wip_works_orders AS
WITH booked AS (
    SELECT t.wo_no, min(t.booking_date) AS first_booking, sum(t.hours) AS hours
    FROM core.time_bookings t, marts.parameters p WHERE t.wo_matched AND t.booking_date <= p.as_of_date GROUP BY 1)
SELECT w.wo_no, w.job_no, w.site_code, w.status, w.planned_start, w.planned_finish, b.first_booking,
       coalesce(b.first_booking, w.planned_start) AS wip_since,
       p.as_of_date - coalesce(b.first_booking, w.planned_start) AS age_days,
       CASE WHEN p.as_of_date - coalesce(b.first_booking, w.planned_start) <= 30 THEN '0-30 days'
            WHEN p.as_of_date - coalesce(b.first_booking, w.planned_start) <= 60 THEN '31-60 days'
            WHEN p.as_of_date - coalesce(b.first_booking, w.planned_start) <= 90 THEN '61-90 days'
            ELSE '90+ days' END AS age_bucket,
       round(coalesce(ww.material_value, 0), 2) AS material_value,
       round(coalesce(b.hours, 0) * p.labour_rate, 2) AS labour_value,
       round(coalesce(ww.material_value, 0) + coalesce(b.hours, 0) * p.labour_rate, 2) AS wip_value,
       w._source_file, w._source_row
FROM core.works_orders w CROSS JOIN marts.parameters p
LEFT JOIN marts.works_order_despatch d ON d.wo_no = w.wo_no
LEFT JOIN marts.works_order_weight ww ON ww.wo_no = w.wo_no
LEFT JOIN booked b ON b.wo_no = w.wo_no
WHERE w.status IN ('RELEASED', 'OPEN', 'COMPLETE') AND d.dn_no IS NULL AND w.planned_start <= p.as_of_date;

CREATE VIEW marts.wip_ageing AS
SELECT age_bucket, count(*) AS works_orders, round(sum(material_value), 2) AS material_value,
       round(sum(labour_value), 2) AS labour_value, round(sum(wip_value), 2) AS wip_value
FROM marts.wip_works_orders GROUP BY 1
ORDER BY CASE age_bucket WHEN '0-30 days' THEN 1 WHEN '31-60 days' THEN 2 WHEN '61-90 days' THEN 3 ELSE 4 END;
