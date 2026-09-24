-- KPI-06 Material traceability coverage. Built on recon.trace_lines.

CREATE VIEW marts.traceability_coverage AS
SELECT CAST(date_trunc('month', t.planned_start) AS DATE) AS month, w.site_code, count(*) AS bom_lines,
       round(sum(t.kg) / 1000, 1) AS tonnes,
       round(100 * sum(t.kg) FILTER (WHERE t.material_chain_complete) / sum(t.kg), 1) AS coverage_pct,
       count(*) FILTER (WHERE t.exposed) AS despatched_untraced_lines
FROM recon.trace_lines t JOIN core.works_orders w ON w.wo_no = t.wo_no
GROUP BY ALL ORDER BY 1, 2;
