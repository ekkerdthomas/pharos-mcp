"""
Tempo inventory and ABC classification query templates.

Templates for inventory levels, classification, and buffer management.

Tempo uses schema prefixes:
- master.Items for item master
- mrp.Inventory for stock levels
- mrp.ItemBufferLevels for buffer settings
- analytics.ItemClassification for ABC analysis
"""

INVENTORY_TEMPLATES = {
    "inventory_levels": '''-- Current Inventory Levels
SELECT
    v.stock_code,
    i.description_1 as Description,
    v.warehouse,
    v.qty_on_hand,
    v.qty_allocated,
    v.qty_available,
    v.qty_on_order,
    v.safety_stock,
    v.minimum_qty,
    v.maximum_qty
FROM mrp.Inventory v
JOIN master.Items i ON v.company_id = i.company_id AND v.stock_code = i.stock_code
WHERE v.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND v.company_id = '<COMPANY_ID>'
ORDER BY v.stock_code, v.warehouse''',

    "inventory_by_warehouse": '''-- Inventory Summary by Warehouse
SELECT
    v.warehouse,
    COUNT(DISTINCT v.stock_code) as ItemCount,
    SUM(v.qty_on_hand) as TotalOnHand,
    SUM(v.qty_allocated) as TotalAllocated,
    SUM(v.qty_available) as TotalAvailable,
    SUM(v.qty_on_order) as TotalOnOrder
FROM mrp.Inventory v
WHERE v.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND v.company_id = '<COMPANY_ID>'
GROUP BY v.warehouse
ORDER BY v.warehouse''',

    "low_stock_items": '''-- Items Below Safety Stock
SELECT
    v.stock_code,
    i.description_1 as Description,
    v.warehouse,
    v.qty_on_hand,
    v.qty_available,
    v.safety_stock,
    v.safety_stock - v.qty_available as Shortfall,
    i.lead_time
FROM mrp.Inventory v
JOIN master.Items i ON v.company_id = i.company_id AND v.stock_code = i.stock_code
WHERE v.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND v.company_id = '<COMPANY_ID>'
  AND v.qty_available < v.safety_stock
  AND v.safety_stock > 0
ORDER BY (v.safety_stock - v.qty_available) DESC''',

    "abc_classification": '''-- ABC Classification Results
SELECT
    c.stock_code,
    i.description_1 as Description,
    c.abc_class,
    c.hml_class,
    c.combined_class,
    c.total_revenue,
    c.revenue_percentage,
    c.cumulative_revenue_percentage,
    c.total_transaction_count
FROM analytics.ItemClassification c
JOIN master.Items i ON c.company_id = i.company_id AND c.stock_code = i.stock_code
WHERE c.company_id = '<COMPANY_ID>'
ORDER BY c.cumulative_revenue_percentage''',

    "abc_summary": '''-- ABC Classification Summary
SELECT
    abc_class,
    COUNT(*) as ItemCount,
    SUM(total_revenue) as TotalRevenue,
    AVG(revenue_percentage) as AvgRevenuePct
FROM analytics.ItemClassification
WHERE company_id = '<COMPANY_ID>'
GROUP BY abc_class
ORDER BY abc_class''',

    "classification_history": '''-- Classification Changes Over Time
SELECT
    h.stock_code,
    i.description_1 as Description,
    h.previous_abc_class,
    h.new_abc_class,
    h.change_date,
    h.change_reason
FROM analytics.ItemClassificationHistory h
JOIN master.Items i ON h.company_id = i.company_id AND h.stock_code = i.stock_code
WHERE h.company_id = '<COMPANY_ID>'
ORDER BY h.change_date DESC''',

    "buffer_levels": '''-- Buffer/Safety Stock Levels
SELECT
    b.stock_code,
    i.description_1 as Description,
    b.warehouse,
    b.buffer_level,
    b.reorder_point,
    b.safety_stock_qty,
    b.buffer_status,
    b.last_calculated
FROM mrp.ItemBufferLevels b
JOIN master.Items i ON b.company_id = i.company_id AND b.stock_code = i.stock_code
WHERE b.company_id = '<COMPANY_ID>'
ORDER BY b.stock_code, b.warehouse''',

    "buffer_penetration": '''-- Buffer Penetration Analysis
-- Items where available stock is below buffer level
SELECT
    b.stock_code,
    i.description_1 as Description,
    b.warehouse,
    v.qty_available,
    b.buffer_level,
    v.qty_available - b.buffer_level as BufferGap,
    CASE
        WHEN v.qty_available <= 0 THEN 'STOCKOUT'
        WHEN v.qty_available < b.safety_stock_qty THEN 'CRITICAL'
        WHEN v.qty_available < b.buffer_level THEN 'WARNING'
        ELSE 'OK'
    END as BufferStatus
FROM mrp.ItemBufferLevels b
JOIN mrp.Inventory v ON b.company_id = v.company_id
    AND b.stock_code = v.stock_code
    AND b.warehouse = v.warehouse
JOIN master.Items i ON b.company_id = i.company_id AND b.stock_code = i.stock_code
WHERE b.company_id = '<COMPANY_ID>'
  AND v.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = '<COMPANY_ID>')
  AND v.qty_available < b.buffer_level
ORDER BY (v.qty_available - b.buffer_level)''',

    "items_master": '''-- Item Master List
SELECT
    i.stock_code,
    i.description_1 as Description,
    i.part_category,
    i.buying_rule,
    i.lead_time,
    i.safety_stock,
    i.economic_batch_qty,
    i.minimum_qty,
    i.maximum_qty,
    i.unit_cost,
    i.lot_sizing_rule
FROM master.Items i
WHERE i.company_id = '<COMPANY_ID>'
ORDER BY i.stock_code''',

    "items_by_category": '''-- Items by Part Category
SELECT
    i.part_category,
    COUNT(*) as ItemCount,
    AVG(i.lead_time) as AvgLeadTime,
    SUM(i.safety_stock) as TotalSafetyStock,
    AVG(i.unit_cost) as AvgUnitCost
FROM master.Items i
WHERE i.company_id = '<COMPANY_ID>'
GROUP BY i.part_category
ORDER BY ItemCount DESC''',

    "high_value_items": '''-- High Value Items
SELECT TOP 50
    i.stock_code,
    i.description_1 as Description,
    i.part_category,
    i.lead_time,
    i.unit_cost,
    c.abc_class
FROM master.Items i
LEFT JOIN analytics.ItemClassification c
    ON i.stock_code = c.stock_code AND i.company_id = c.company_id
WHERE i.company_id = '<COMPANY_ID>'
  AND i.unit_cost > 0
ORDER BY i.unit_cost DESC''',
}

INVENTORY_DESCRIPTIONS = {
    "inventory_levels": "Current inventory levels by stock code and warehouse",
    "inventory_by_warehouse": "Inventory totals summarized by warehouse",
    "low_stock_items": "Items with stock below safety stock level",
    "abc_classification": "ABC classification results for all items",
    "abc_summary": "ABC class distribution summary",
    "classification_history": "History of ABC classification changes",
    "buffer_levels": "Buffer/safety stock configuration by item",
    "buffer_penetration": "Items with stock below buffer level",
    "items_master": "Item master list with planning parameters",
    "items_by_category": "Item counts by part category",
    "high_value_items": "Top 50 items by unit cost",
}
