"""
Tempo forecasting query templates.

Templates for forecast analysis, accuracy metrics, and method performance.

Tempo uses schema prefixes:
- forecast.* for all forecasting tables
- master.Items for item details
"""

FORECASTING_TEMPLATES = {
    "forecast_results": '''-- Latest Forecast Results
SELECT TOP 100
    f.stock_code,
    i.description_1 as Description,
    f.warehouse,
    f.forecast_date,
    f.forecast_quantity,
    f.forecast_method,
    f.confidence_level
FROM forecast.ForecastResults f
JOIN master.Items i ON f.company_id = i.company_id AND f.stock_code = i.stock_code
WHERE f.company_id = '<COMPANY_ID>'
ORDER BY f.forecast_date, f.stock_code''',

    "forecast_by_item": '''-- Forecast for Specific Item
SELECT
    f.stock_code,
    f.warehouse,
    f.forecast_date,
    f.forecast_quantity,
    f.forecast_method,
    f.confidence_level
FROM forecast.ForecastResults f
WHERE f.company_id = '<COMPANY_ID>'
  AND f.stock_code = '<STOCK_CODE>'
ORDER BY f.forecast_date''',

    "forecast_accuracy": '''-- Forecast Accuracy Metrics
SELECT
    a.stock_code,
    i.description_1 as Description,
    a.forecast_method,
    a.mape as MeanAbsolutePercentageError,
    a.mae as MeanAbsoluteError,
    a.rmse as RootMeanSquareError,
    a.bias,
    a.tracking_signal,
    a.periods_evaluated
FROM forecast.ForecastAccuracy a
JOIN master.Items i ON a.company_id = i.company_id AND a.stock_code = i.stock_code
WHERE a.company_id = '<COMPANY_ID>'
  AND a.mape IS NOT NULL
ORDER BY a.mape DESC''',

    "forecast_accuracy_summary": '''-- Forecast Accuracy Summary by Method
SELECT
    a.forecast_method,
    COUNT(DISTINCT a.stock_code) as ItemCount,
    AVG(a.mape) as AvgMAPE,
    AVG(a.mae) as AvgMAE,
    AVG(a.rmse) as AvgRMSE,
    AVG(a.bias) as AvgBias
FROM forecast.ForecastAccuracy a
WHERE a.company_id = '<COMPANY_ID>'
  AND a.mape IS NOT NULL
GROUP BY a.forecast_method
ORDER BY AvgMAPE''',

    "forecast_method_performance": '''-- Forecast Method Performance Comparison
SELECT
    p.stock_code,
    i.description_1 as Description,
    p.forecast_method,
    p.accuracy_score,
    p.periods_tested,
    p.recommended_method
FROM forecast.ForecastMethodPerformance p
JOIN master.Items i ON p.company_id = i.company_id AND p.stock_code = i.stock_code
WHERE p.company_id = '<COMPANY_ID>'
ORDER BY p.accuracy_score DESC''',

    "forecast_runs": '''-- Forecast Run History
SELECT
    r.run_id,
    r.company_id,
    r.run_date,
    r.run_type,
    r.items_processed,
    r.periods_forecast,
    r.run_status,
    r.duration_seconds
FROM forecast.ForecastRuns r
WHERE r.company_id = '<COMPANY_ID>'
ORDER BY r.run_date DESC''',

    "item_forecast_strategy": '''-- Item Forecast Strategy Configuration
SELECT
    s.stock_code,
    i.description_1 as Description,
    s.forecast_method,
    s.seasonality_enabled,
    s.trend_enabled,
    s.history_periods,
    s.forecast_periods
FROM forecast.ItemForecastStrategy s
JOIN master.Items i ON s.company_id = i.company_id AND s.stock_code = i.stock_code
WHERE s.company_id = '<COMPANY_ID>'
ORDER BY s.stock_code''',

    "forecast_consumption": '''-- Forecast vs Actual Consumption Tracking
SELECT
    t.stock_code,
    i.description_1 as Description,
    t.period_date,
    t.forecast_quantity,
    t.actual_quantity,
    t.variance,
    t.variance_pct,
    t.consumed_by_date
FROM forecast.ForecastConsumptionTracking t
JOIN master.Items i ON t.company_id = i.company_id AND t.stock_code = i.stock_code
WHERE t.company_id = '<COMPANY_ID>'
ORDER BY t.period_date DESC, ABS(t.variance_pct) DESC''',

    "forecast_poor_performers": '''-- Items with Poor Forecast Accuracy (MAPE > 30%)
SELECT
    a.stock_code,
    i.description_1 as Description,
    i.part_category,
    a.forecast_method,
    a.mape as MeanAbsolutePercentageError,
    a.periods_evaluated
FROM forecast.ForecastAccuracy a
JOIN master.Items i ON a.company_id = i.company_id AND a.stock_code = i.stock_code
WHERE a.company_id = '<COMPANY_ID>'
  AND a.mape > 30
ORDER BY a.mape DESC''',
}

FORECASTING_DESCRIPTIONS = {
    "forecast_results": "Latest forecast results for all items",
    "forecast_by_item": "Forecast details for a specific item",
    "forecast_accuracy": "Forecast accuracy metrics by item",
    "forecast_accuracy_summary": "Accuracy summary grouped by forecast method",
    "forecast_method_performance": "Method performance comparison by item",
    "forecast_runs": "History of forecast runs",
    "item_forecast_strategy": "Forecast configuration by item",
    "forecast_consumption": "Forecast vs actual consumption tracking",
    "forecast_poor_performers": "Items with poor forecast accuracy (MAPE > 30%)",
}
