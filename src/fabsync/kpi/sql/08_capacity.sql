-- KPI-08 Capacity utilisation, booked against available hours.

CREATE VIEW marts.capacity_utilisation AS
SELECT c.week_commencing, c.site_code, c.available_hours, c.booked_hours,
       round(100 * c.booked_hours / nullif(c.available_hours, 0), 1) AS utilisation_pct,
       coalesce(b.hours, 0) AS hours_on_booking_sheets,
       round(c.booked_hours - coalesce(b.hours, 0), 1) AS supervisor_vs_sheets_hours,
       c._source_file, c._source_row
FROM core.weekly_capacity c
LEFT JOIN (SELECT CAST(date_trunc('week', booking_date) AS DATE) AS week, site_code, sum(hours) AS hours
           FROM core.time_bookings GROUP BY 1, 2) b ON b.week = c.week_commencing AND b.site_code = c.site_code
ORDER BY c.week_commencing, c.site_code;

CREATE VIEW marts.capacity_utilisation_by_site AS
SELECT site_code, count(*) AS weeks, count(booked_hours) AS weeks_reported,
       round(sum(available_hours) FILTER (WHERE booked_hours IS NOT NULL)) AS available_hours,
       round(sum(booked_hours)) AS booked_hours,
       round(100 * sum(booked_hours) / sum(available_hours) FILTER (WHERE booked_hours IS NOT NULL), 1)
           AS utilisation_pct,
       count(*) FILTER (WHERE utilisation_pct > 100) AS weeks_over_100_pct
FROM marts.capacity_utilisation GROUP BY 1 ORDER BY 1;
