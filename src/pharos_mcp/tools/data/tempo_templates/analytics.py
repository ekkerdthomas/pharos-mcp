"""
Tempo analytics and system query templates.

Templates for MRP runs, lead time analysis, and system metrics.

Tempo uses schema prefixes:
- mrp.* for MRP tables (Runs, Suggestions, etc.)
- analytics.* for lead time analysis
- auth.* for users, companies, audit
"""

ANALYTICS_TEMPLATES = {
    "mrp_runs": '''-- MRP Run History
SELECT
    r.run_id,
    r.company_id,
    r.run_name,
    r.display_name,
    r.created_date,
    r.status,
    r.start_time,
    r.end_time,
    r.items_processed,
    r.planning_orders_created,
    r.planning_horizon_days,
    r.created_by
FROM mrp.Runs r
WHERE r.company_id = '<COMPANY_ID>'
ORDER BY r.created_date DESC''',

    "mrp_run_detail": '''-- MRP Run Detail
SELECT *
FROM mrp.Runs r
WHERE r.run_id = <RUN_ID>''',

    "scheduled_runs": '''-- Scheduled MRP Runs
SELECT
    s.schedule_id,
    s.company_id,
    s.schedule_name,
    s.schedule_type,
    s.next_run_time,
    s.frequency,
    s.is_active,
    s.last_run_time,
    s.last_run_status
FROM mrp.ScheduledMRPRuns s
WHERE s.company_id = '<COMPANY_ID>'
ORDER BY s.next_run_time''',

    "lead_time_analysis": '''-- Lead Time Analysis by Item
SELECT
    d.stock_code,
    i.description_1 as Description,
    i.lead_time as PlannedLeadTime,
    d.avg_lead_time as AvgActualLeadTime,
    d.min_lead_time,
    d.max_lead_time,
    d.std_deviation,
    d.sample_count,
    d.avg_lead_time - i.lead_time as Variance
FROM analytics.LeadTimeDetail d
JOIN master.Items i ON d.company_id = i.company_id AND d.stock_code = i.stock_code
WHERE d.company_id = '<COMPANY_ID>'
ORDER BY ABS(d.avg_lead_time - i.lead_time) DESC''',

    "lead_time_metrics": '''-- Lead Time Metrics Summary
SELECT
    m.supplier,
    m.stock_code,
    m.avg_lead_time,
    m.reliability_score,
    m.on_time_delivery_pct,
    m.sample_count
FROM analytics.LeadTimeMetrics m
WHERE m.company_id = '<COMPANY_ID>'
ORDER BY m.reliability_score DESC''',

    "action_messages": '''-- MRP Action Messages
SELECT
    m.message_id,
    m.stock_code,
    i.description_1 as Description,
    m.message_type,
    m.message_text,
    m.severity,
    m.order_number,
    m.created_date
FROM mrp.ActionMessages m
JOIN master.Items i ON m.company_id = i.company_id AND m.stock_code = i.stock_code
WHERE m.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND m.company_id = '<COMPANY_ID>'
ORDER BY m.severity DESC, m.created_date DESC''',

    "usage_analysis": '''-- Item Usage Analysis
SELECT
    u.stock_code,
    i.description_1 as Description,
    u.total_usage,
    u.avg_daily_usage,
    u.max_daily_usage,
    u.usage_variance,
    u.days_with_usage,
    u.analysis_period_days
FROM analytics.ItemUsageAnalysis u
JOIN master.Items i ON u.company_id = i.company_id AND u.stock_code = i.stock_code
WHERE u.company_id = '<COMPANY_ID>'
ORDER BY u.total_usage DESC''',

    "consumption_data": '''-- Historical Consumption Data (6 months)
SELECT TOP 500
    c.stock_code,
    c.warehouse,
    c.consumption_date,
    c.consumption_type,
    c.quantity,
    c.source_document,
    c.customer
FROM forecast.ConsumptionData c
WHERE c.company_id = '<COMPANY_ID>'
  AND c.consumption_date >= DATEADD(month, -6, GETDATE())
ORDER BY c.consumption_date DESC, c.stock_code''',

    "users": '''-- System Users
SELECT
    u.user_id,
    u.username,
    u.email,
    u.first_name,
    u.last_name,
    u.is_active,
    u.last_login,
    u.created_at
FROM auth.Users u
ORDER BY u.username''',

    "audit_log": '''-- Recent Audit Log Entries
SELECT TOP 100
    a.log_id,
    a.event_date,
    a.event_type,
    a.table_name,
    a.record_id,
    a.user_id,
    a.description
FROM auth.AuditLog a
ORDER BY a.event_date DESC''',

    "suggestion_audit": '''-- Suggestion Status Changes
SELECT TOP 100
    s.audit_id,
    s.suggestion_id,
    s.stock_code,
    s.old_status,
    s.new_status,
    s.changed_by,
    s.change_date,
    s.change_reason
FROM mrp.SuggestionAudit s
WHERE s.company_id = '<COMPANY_ID>'
ORDER BY s.change_date DESC''',

    "job_schedule": '''-- Production Job Schedule
SELECT
    j.job_id,
    j.stock_code,
    i.description_1 as Description,
    j.warehouse,
    j.planned_start_date,
    j.planned_end_date,
    j.quantity,
    j.status,
    j.work_center,
    j.priority
FROM mrp.JobSchedule j
JOIN master.Items i ON j.company_id = i.company_id AND j.stock_code = i.stock_code
WHERE j.company_id = '<COMPANY_ID>'
ORDER BY j.planned_start_date''',

    "resource_availability": '''-- Resource Availability
SELECT
    r.resource_id,
    r.resource_name,
    r.resource_type,
    r.available_date,
    r.capacity_hours,
    r.allocated_hours,
    r.capacity_hours - r.allocated_hours as AvailableHours
FROM mrp.ResourceAvailability r
WHERE r.company_id = '<COMPANY_ID>'
  AND r.available_date >= GETDATE()
ORDER BY r.available_date, r.resource_name''',

    "data_summary": '''-- Tempo Data Summary for Company
SELECT 'Items' as TableName, COUNT(*) as RecordCount FROM master.Items WHERE company_id = '<COMPANY_ID>'
UNION ALL
SELECT 'Inventory', COUNT(*) FROM mrp.Inventory WHERE company_id = '<COMPANY_ID>' AND run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
UNION ALL
SELECT 'Demands', COUNT(*) FROM mrp.Demands WHERE company_id = '<COMPANY_ID>' AND run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
UNION ALL
SELECT 'Supply', COUNT(*) FROM mrp.Supply WHERE company_id = '<COMPANY_ID>' AND run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
UNION ALL
SELECT 'Suggestions', COUNT(*) FROM mrp.Suggestions WHERE company_id = '<COMPANY_ID>' AND run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
UNION ALL
SELECT 'MRP Runs', COUNT(*) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>'
UNION ALL
SELECT 'Forecasts', COUNT(*) FROM forecast.ForecastResults WHERE company_id = '<COMPANY_ID>'
UNION ALL
SELECT 'ABC Classifications', COUNT(*) FROM analytics.ItemClassification WHERE company_id = '<COMPANY_ID>'
ORDER BY TableName''',
}

ANALYTICS_DESCRIPTIONS = {
    "mrp_runs": "History of MRP calculation runs",
    "mrp_run_detail": "Full details for a specific MRP run",
    "scheduled_runs": "Scheduled/recurring MRP run configuration",
    "lead_time_analysis": "Actual vs planned lead time analysis",
    "lead_time_metrics": "Lead time reliability metrics by supplier",
    "action_messages": "MRP-generated action messages and alerts",
    "usage_analysis": "Item usage/consumption analysis",
    "consumption_data": "Historical consumption records (6 months)",
    "users": "System users list",
    "audit_log": "Recent system audit log entries",
    "suggestion_audit": "History of suggestion status changes",
    "job_schedule": "Production job scheduling",
    "resource_availability": "Resource capacity and availability",
    "data_summary": "Record counts for all major tables",
}
