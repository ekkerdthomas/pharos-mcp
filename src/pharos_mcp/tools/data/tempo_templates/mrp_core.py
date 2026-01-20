"""
Tempo MRP core query templates.

Templates for demands, supply, suggestions, and pegging analysis.

Tempo uses schema prefixes:
- master.* for item master
- mrp.* for MRP tables (Demands, Supply, Suggestions, Inventory, Runs)
- forecast.* for forecasting
- analytics.* for classification/lead times
- auth.* for users/companies

Replace <COMPANY_ID> with actual company ID (e.g., 'TTM', 'TTML', 'IV').
"""

MRP_CORE_TEMPLATES = {
    "demands_summary": '''-- Demand Summary by Stock Code
-- Replace <COMPANY_ID> with company (e.g., 'TTM')
SELECT
    d.stock_code,
    i.description_1 as Description,
    d.warehouse,
    d.demand_type,
    COUNT(*) as DemandCount,
    SUM(d.quantity) as TotalQty,
    MIN(d.required_date) as EarliestDate,
    MAX(d.required_date) as LatestDate
FROM mrp.Demands d
JOIN master.Items i ON d.company_id = i.company_id AND d.stock_code = i.stock_code
WHERE d.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND d.company_id = '<COMPANY_ID>'
GROUP BY d.stock_code, i.description_1, d.warehouse, d.demand_type
ORDER BY TotalQty DESC''',

    "demands_detail": '''-- Demand Detail for Stock Code
SELECT
    d.stock_code,
    d.warehouse,
    d.required_date,
    d.demand_type,
    d.source_type,
    d.quantity,
    d.order_number,
    d.line_number,
    d.customer,
    d.processing_status,
    d.allocation_status,
    d.within_time_fence,
    d.job_confirmed
FROM mrp.Demands d
WHERE d.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND d.company_id = '<COMPANY_ID>'
  AND d.stock_code = '<STOCK_CODE>'
ORDER BY d.required_date, d.demand_type''',

    "supply_summary": '''-- Supply Summary by Stock Code
SELECT
    s.stock_code,
    i.description_1 as Description,
    s.warehouse,
    s.supply_type,
    COUNT(*) as SupplyCount,
    SUM(s.quantity) as TotalQty,
    SUM(s.quantity_available) as AvailableQty,
    MIN(s.due_date) as EarliestDate,
    MAX(s.due_date) as LatestDate
FROM mrp.Supply s
JOIN master.Items i ON s.company_id = i.company_id AND s.stock_code = i.stock_code
WHERE s.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND s.company_id = '<COMPANY_ID>'
GROUP BY s.stock_code, i.description_1, s.warehouse, s.supply_type
ORDER BY TotalQty DESC''',

    "supply_detail": '''-- Supply Detail for Stock Code
SELECT
    s.stock_code,
    s.warehouse,
    s.due_date,
    s.supply_type,
    s.source_type,
    s.quantity,
    s.quantity_allocated,
    s.quantity_available,
    s.order_number,
    s.supplier,
    s.supply_status,
    s.allocation_status,
    s.job_confirmed
FROM mrp.Supply s
WHERE s.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND s.company_id = '<COMPANY_ID>'
  AND s.stock_code = '<STOCK_CODE>'
ORDER BY s.due_date, s.supply_type''',

    "suggestions_open": '''-- Open MRP Suggestions
SELECT
    s.stock_code,
    i.description_1 as Description,
    s.warehouse,
    s.order_type,
    s.planned_quantity,
    s.required_date,
    s.start_date,
    s.due_date,
    s.lead_time,
    s.action_message,
    s.exception_type,
    s.critical_flag,
    s.order_status
FROM mrp.Suggestions s
JOIN master.Items i ON s.company_id = i.company_id AND s.stock_code = i.stock_code
WHERE s.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND s.company_id = '<COMPANY_ID>'
  AND s.order_status = 'PLANNED'
ORDER BY s.critical_flag DESC, s.required_date''',

    "suggestions_by_type": '''-- Suggestions Summary by Order Type
SELECT
    s.order_type,
    s.order_status,
    COUNT(*) as SuggestionCount,
    SUM(s.planned_quantity) as TotalQty,
    SUM(CASE WHEN s.critical_flag = 1 THEN 1 ELSE 0 END) as CriticalCount,
    MIN(s.required_date) as EarliestDate,
    MAX(s.required_date) as LatestDate
FROM mrp.Suggestions s
WHERE s.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND s.company_id = '<COMPANY_ID>'
GROUP BY s.order_type, s.order_status
ORDER BY s.order_type, s.order_status''',

    "suggestions_critical": '''-- Critical Suggestions (Action Required)
SELECT
    s.stock_code,
    i.description_1 as Description,
    s.warehouse,
    s.order_type,
    s.planned_quantity,
    s.required_date,
    s.action_message,
    s.exception_type,
    s.lead_time
FROM mrp.Suggestions s
JOIN master.Items i ON s.company_id = i.company_id AND s.stock_code = i.stock_code
WHERE s.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND s.company_id = '<COMPANY_ID>'
  AND s.critical_flag = 1
ORDER BY s.required_date''',

    "pegging_analysis": '''-- Pegging Analysis for Stock Code
-- Shows demand-supply relationships
SELECT
    p.stock_code,
    p.warehouse,
    p.demand_id,
    p.supply_id,
    d.demand_type,
    d.required_date as DemandDate,
    d.quantity as DemandQty,
    s.supply_type,
    s.due_date as SupplyDate,
    s.quantity as SupplyQty
FROM mrp.Pegging p
JOIN mrp.Demands d ON p.demand_id = d.demand_id AND p.run_id = d.run_id
JOIN mrp.Supply s ON p.supply_id = s.supply_id AND p.run_id = s.run_id
WHERE p.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND p.company_id = '<COMPANY_ID>'
  AND p.stock_code = '<STOCK_CODE>'
ORDER BY d.required_date''',

    "supply_demand_balance": '''-- Supply/Demand Balance by Stock Code
WITH LatestRun AS (
    SELECT MAX(run_id) as run_id FROM mrp.Runs WHERE company_id = '<COMPANY_ID>'
),
DemandTotals AS (
    SELECT stock_code, warehouse, SUM(quantity) as TotalDemand
    FROM mrp.Demands d, LatestRun r
    WHERE d.run_id = r.run_id AND d.company_id = '<COMPANY_ID>'
    GROUP BY stock_code, warehouse
),
SupplyTotals AS (
    SELECT stock_code, warehouse, SUM(quantity_available) as TotalSupply
    FROM mrp.Supply s, LatestRun r
    WHERE s.run_id = r.run_id AND s.company_id = '<COMPANY_ID>'
    GROUP BY stock_code, warehouse
)
SELECT
    COALESCE(d.stock_code, s.stock_code) as stock_code,
    i.description_1 as Description,
    COALESCE(d.warehouse, s.warehouse) as warehouse,
    COALESCE(d.TotalDemand, 0) as TotalDemand,
    COALESCE(s.TotalSupply, 0) as TotalSupply,
    COALESCE(s.TotalSupply, 0) - COALESCE(d.TotalDemand, 0) as NetBalance
FROM DemandTotals d
FULL OUTER JOIN SupplyTotals s ON d.stock_code = s.stock_code AND d.warehouse = s.warehouse
JOIN master.Items i ON COALESCE(d.stock_code, s.stock_code) = i.stock_code
    AND i.company_id = '<COMPANY_ID>'
ORDER BY NetBalance''',

    "companies": '''-- List Available Companies
SELECT
    company_id,
    company_name,
    display_name,
    erp_system,
    erp_database,
    default_warehouse,
    is_active
FROM auth.Companies
ORDER BY company_name''',
}

MRP_CORE_DESCRIPTIONS = {
    "demands_summary": "Demand totals grouped by stock code and type",
    "demands_detail": "Detailed demand records for a specific stock code",
    "supply_summary": "Supply totals grouped by stock code and type",
    "supply_detail": "Detailed supply records for a specific stock code",
    "suggestions_open": "Open/planned MRP suggestions",
    "suggestions_by_type": "Suggestion counts by order type",
    "suggestions_critical": "Critical suggestions requiring immediate action",
    "pegging_analysis": "Demand-supply pegging relationships for a stock code",
    "supply_demand_balance": "Net supply/demand balance by stock code",
    "companies": "List available companies in Tempo",
}
