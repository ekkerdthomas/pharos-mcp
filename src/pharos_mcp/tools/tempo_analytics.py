"""
Tempo MRP analytics tools for Pharos MCP.

Provides KPIs, shortage analysis, and data quality metrics specific to
Tempo's MRP data model (run-based snapshots, multi-tenant companies).
"""

from mcp.server.fastmcp import FastMCP

from ..core.audit import audit_tool_call
from ..core.database import get_database_registry


def get_tempo_db():
    """Get the Tempo database connection."""
    return get_database_registry().get_connection("tempo")


def register_tempo_analytics_tools(mcp: FastMCP) -> None:
    """Register Tempo analytics tools with the MCP server."""

    @mcp.tool()
    @audit_tool_call("get_tempo_dashboard")
    async def get_tempo_dashboard(company_id: str) -> str:
        """Get a high-level MRP dashboard for a Tempo company.

        Shows key metrics including:
        - MRP run status and history
        - Demand/supply balance summary
        - Critical suggestions count
        - Inventory coverage metrics
        - Data quality indicators

        Args:
            company_id: Company identifier (e.g., 'TTM', 'TTML', 'IV').

        Returns:
            Formatted dashboard with KPIs and status indicators.
        """
        db = get_tempo_db()

        # Get latest run info
        run_sql = """
        SELECT TOP 1
            run_id,
            run_name,
            created_date,
            status,
            items_processed,
            planning_orders_created,
            planning_horizon_days
        FROM mrp.Runs
        WHERE company_id = %s
        ORDER BY created_date DESC
        """

        # Get demand/supply totals for latest run
        # Note: quantity_available may be NULL, so use COALESCE with quantity
        balance_sql = """
        WITH LatestRun AS (
            SELECT MAX(run_id) as run_id FROM mrp.Runs WHERE company_id = %s
        )
        SELECT
            (SELECT COUNT(DISTINCT stock_code) FROM mrp.Demands d, LatestRun r
             WHERE d.run_id = r.run_id AND d.company_id = %s) as DemandItems,
            (SELECT SUM(quantity) FROM mrp.Demands d, LatestRun r
             WHERE d.run_id = r.run_id AND d.company_id = %s) as TotalDemand,
            (SELECT COUNT(DISTINCT stock_code) FROM mrp.Supply s, LatestRun r
             WHERE s.run_id = r.run_id AND s.company_id = %s) as SupplyItems,
            (SELECT SUM(COALESCE(quantity_available, quantity)) FROM mrp.Supply s, LatestRun r
             WHERE s.run_id = r.run_id AND s.company_id = %s) as TotalSupply
        """

        # Get suggestion counts
        suggestion_sql = """
        SELECT
            order_status,
            COUNT(*) as Count,
            SUM(CASE WHEN critical_flag = 1 THEN 1 ELSE 0 END) as Critical
        FROM mrp.Suggestions s
        WHERE s.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
          AND s.company_id = %s
        GROUP BY order_status
        """

        # Get inventory status
        inventory_sql = """
        SELECT
            COUNT(DISTINCT stock_code) as TotalItems,
            SUM(CASE WHEN qty_available < safety_stock AND safety_stock > 0 THEN 1 ELSE 0 END) as BelowSafety,
            SUM(CASE WHEN qty_available <= 0 THEN 1 ELSE 0 END) as OutOfStock
        FROM mrp.Inventory v
        WHERE v.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
          AND v.company_id = %s
        """

        # Data quality checks
        quality_sql = """
        SELECT
            (SELECT COUNT(*) FROM master.Items WHERE company_id = %s AND lead_time = 0) as ZeroLeadTime,
            (SELECT COUNT(*) FROM master.Items WHERE company_id = %s AND (unit_cost = 0 OR unit_cost IS NULL)) as ZeroCost,
            (SELECT COUNT(*) FROM master.Items WHERE company_id = %s) as TotalItems
        """

        try:
            run_result = db.execute_query(run_sql, (company_id,), max_rows=1)
            balance_result = db.execute_query(
                balance_sql,
                (company_id, company_id, company_id, company_id, company_id),
                max_rows=1,
            )
            suggestion_result = db.execute_query(
                suggestion_sql, (company_id, company_id), max_rows=10
            )
            inventory_result = db.execute_query(
                inventory_sql, (company_id, company_id), max_rows=1
            )
            quality_result = db.execute_query(
                quality_sql, (company_id, company_id, company_id), max_rows=1
            )
        except Exception as e:
            return f"Failed to get Tempo dashboard for {company_id}: {e}"

        output = f"\nTEMPO MRP DASHBOARD - {company_id}\n"
        output += "=" * 60 + "\n"

        # Latest MRP Run
        output += "\nLATEST MRP RUN\n"
        output += "-" * 60 + "\n"
        if run_result:
            run = run_result[0]
            output += f"  Run ID:              {run.get('run_id', 'N/A')}\n"
            output += f"  Run Name:            {run.get('run_name', 'N/A')}\n"
            output += f"  Created:             {run.get('created_date', 'N/A')}\n"
            output += f"  Status:              {run.get('status', 'N/A')}\n"
            output += f"  Items Processed:     {run.get('items_processed', 0):,}\n"
            output += f"  Planning Orders:     {run.get('planning_orders_created', 0):,}\n"
            output += f"  Horizon (days):      {run.get('planning_horizon_days', 0)}\n"
        else:
            output += "  No MRP runs found for this company.\n"

        # Demand/Supply Balance
        output += "\nDEMAND/SUPPLY BALANCE\n"
        output += "-" * 60 + "\n"
        if balance_result:
            bal = balance_result[0]
            total_demand = float(bal.get("TotalDemand", 0) or 0)
            total_supply = float(bal.get("TotalSupply", 0) or 0)
            coverage = (total_supply / total_demand * 100) if total_demand > 0 else 0
            output += f"  Items with Demand:   {bal.get('DemandItems', 0):,}\n"
            output += f"  Total Demand Qty:    {total_demand:,.0f}\n"
            output += f"  Items with Supply:   {bal.get('SupplyItems', 0):,}\n"
            output += f"  Total Supply Qty:    {total_supply:,.0f}\n"
            output += f"  Supply Coverage:     {coverage:.1f}%\n"

        # Suggestions Summary
        output += "\nMRP SUGGESTIONS\n"
        output += "-" * 60 + "\n"
        total_suggestions = 0
        total_critical = 0
        for row in suggestion_result or []:
            status = row.get("order_status", "Unknown")
            count = int(row.get("Count", 0) or 0)
            critical = int(row.get("Critical", 0) or 0)
            total_suggestions += count
            total_critical += critical
            output += f"  {status:15} {count:>8,}  (critical: {critical:,})\n"
        output += f"  {'TOTAL':15} {total_suggestions:>8,}  (critical: {total_critical:,})\n"

        if total_critical > 0:
            output += f"\n  WARNING: {total_critical:,} critical suggestions require attention\n"

        # Inventory Status
        output += "\nINVENTORY STATUS\n"
        output += "-" * 60 + "\n"
        if inventory_result:
            inv = inventory_result[0]
            total = int(inv.get("TotalItems", 0) or 0)
            below = int(inv.get("BelowSafety", 0) or 0)
            out = int(inv.get("OutOfStock", 0) or 0)
            output += f"  Total Items:         {total:,}\n"
            output += f"  Below Safety Stock:  {below:,}\n"
            output += f"  Out of Stock:        {out:,}\n"

            if out > 0:
                output += f"\n  ALERT: {out} items are out of stock\n"

        # Data Quality
        output += "\nDATA QUALITY INDICATORS\n"
        output += "-" * 60 + "\n"
        if quality_result:
            qual = quality_result[0]
            total = int(qual.get("TotalItems", 0) or 0)
            zero_lt = int(qual.get("ZeroLeadTime", 0) or 0)
            zero_cost = int(qual.get("ZeroCost", 0) or 0)
            lt_pct = (zero_lt / total * 100) if total > 0 else 0
            cost_pct = (zero_cost / total * 100) if total > 0 else 0

            output += f"  Items with 0 lead time:  {zero_lt:,} ({lt_pct:.1f}%)\n"
            output += f"  Items with 0 cost:       {zero_cost:,} ({cost_pct:.1f}%)\n"

            if lt_pct > 50:
                output += "\n  WARNING: >50% items missing lead time data\n"
            if cost_pct > 10:
                output += f"  WARNING: {cost_pct:.0f}% items missing cost data\n"

        return output

    @mcp.tool()
    @audit_tool_call("analyze_tempo_shortages")
    async def analyze_tempo_shortages(
        company_id: str, horizon_days: int = 30
    ) -> str:
        """Analyze potential stockouts and shortages for a Tempo company.

        Performs time-phased analysis to identify items where demand
        exceeds supply within the specified horizon.

        Args:
            company_id: Company identifier (e.g., 'TTM', 'TTML', 'IV').
            horizon_days: Days to look ahead (default 30).

        Returns:
            Shortage analysis report with critical items.
        """
        db = get_tempo_db()

        # Time-phased shortage analysis
        # Note: master.Items may have duplicates, so use ROW_NUMBER to get one row per item
        shortage_sql = """
        WITH LatestRun AS (
            SELECT MAX(run_id) as run_id FROM mrp.Runs WHERE company_id = %s
        ),
        DemandByItem AS (
            SELECT
                d.stock_code,
                SUM(d.quantity) as TotalDemand
            FROM mrp.Demands d, LatestRun r
            WHERE d.run_id = r.run_id
              AND d.company_id = %s
              AND d.required_date <= DATEADD(day, %s, GETDATE())
            GROUP BY d.stock_code
        ),
        SupplyByItem AS (
            SELECT
                s.stock_code,
                SUM(COALESCE(s.quantity_available, s.quantity)) as TotalSupply
            FROM mrp.Supply s, LatestRun r
            WHERE s.run_id = r.run_id
              AND s.company_id = %s
              AND s.due_date <= DATEADD(day, %s, GETDATE())
            GROUP BY s.stock_code
        ),
        ItemInfo AS (
            SELECT stock_code, description_1, part_category, lead_time,
                   ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY stock_code) as rn
            FROM master.Items
            WHERE company_id = %s
        )
        SELECT TOP 25
            d.stock_code,
            i.description_1 as Description,
            i.part_category,
            i.lead_time,
            d.TotalDemand,
            COALESCE(s.TotalSupply, 0) as TotalSupply,
            COALESCE(s.TotalSupply, 0) - d.TotalDemand as NetPosition
        FROM DemandByItem d
        LEFT JOIN SupplyByItem s ON d.stock_code = s.stock_code
        JOIN ItemInfo i ON d.stock_code = i.stock_code AND i.rn = 1
        WHERE COALESCE(s.TotalSupply, 0) < d.TotalDemand
        ORDER BY (COALESCE(s.TotalSupply, 0) - d.TotalDemand)
        """

        # Items with long lead times and potential issues
        # Use ROW_NUMBER to deduplicate master.Items
        risk_sql = """
        WITH ItemInfo AS (
            SELECT stock_code, description_1, lead_time, company_id,
                   ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY stock_code) as rn
            FROM master.Items
            WHERE company_id = %s
        )
        SELECT TOP 15
            i.stock_code,
            i.description_1 as Description,
            i.lead_time,
            v.qty_on_hand,
            v.qty_available,
            d.DemandQty
        FROM ItemInfo i
        JOIN mrp.Inventory v ON i.stock_code = v.stock_code AND i.company_id = v.company_id
        LEFT JOIN (
            SELECT stock_code, SUM(quantity) as DemandQty
            FROM mrp.Demands
            WHERE run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
              AND company_id = %s
            GROUP BY stock_code
        ) d ON i.stock_code = d.stock_code
        WHERE i.rn = 1
          AND v.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
          AND i.lead_time > 60
          AND v.qty_available < COALESCE(d.DemandQty, 0) * 0.5
        ORDER BY i.lead_time DESC, (COALESCE(d.DemandQty, 0) - v.qty_available) DESC
        """

        # Shortage severity counts
        severity_sql = """
        WITH LatestRun AS (
            SELECT MAX(run_id) as run_id FROM mrp.Runs WHERE company_id = %s
        ),
        ItemBalance AS (
            SELECT
                d.stock_code,
                SUM(d.quantity) as Demand,
                COALESCE((
                    SELECT SUM(COALESCE(s.quantity_available, s.quantity))
                    FROM mrp.Supply s, LatestRun r
                    WHERE s.run_id = r.run_id
                      AND s.stock_code = d.stock_code
                      AND s.company_id = d.company_id
                ), 0) as Supply
            FROM mrp.Demands d, LatestRun r
            WHERE d.run_id = r.run_id AND d.company_id = %s
            GROUP BY d.stock_code, d.company_id
        )
        SELECT
            CASE
                WHEN Supply = 0 THEN 'CRITICAL (No Supply)'
                WHEN Supply < Demand * 0.5 THEN 'SEVERE (<50% coverage)'
                WHEN Supply < Demand THEN 'WARNING (<100% coverage)'
                ELSE 'OK'
            END as Severity,
            COUNT(*) as ItemCount
        FROM ItemBalance
        GROUP BY
            CASE
                WHEN Supply = 0 THEN 'CRITICAL (No Supply)'
                WHEN Supply < Demand * 0.5 THEN 'SEVERE (<50% coverage)'
                WHEN Supply < Demand THEN 'WARNING (<100% coverage)'
                ELSE 'OK'
            END
        ORDER BY ItemCount DESC
        """

        try:
            shortage_result = db.execute_query(
                shortage_sql,
                (company_id, company_id, horizon_days, company_id, horizon_days, company_id),
                max_rows=25,
            )
            risk_result = db.execute_query(
                risk_sql,
                (company_id, company_id, company_id, company_id),
                max_rows=15,
            )
            severity_result = db.execute_query(
                severity_sql, (company_id, company_id), max_rows=10
            )
        except Exception as e:
            return f"Failed to analyze shortages for {company_id}: {e}"

        output = f"\nTEMPO SHORTAGE ANALYSIS - {company_id}\n"
        output += f"Horizon: {horizon_days} days\n"
        output += "=" * 70 + "\n"

        # Severity Summary
        output += "\nSHORTAGE SEVERITY SUMMARY\n"
        output += "-" * 70 + "\n"
        for row in severity_result or []:
            severity = row.get("Severity", "Unknown")
            count = int(row.get("ItemCount", 0) or 0)
            marker = " <-- ACTION REQUIRED" if "CRITICAL" in severity else ""
            output += f"  {severity:30} {count:>8,}{marker}\n"

        # Critical Shortages
        output += f"\nCRITICAL SHORTAGES (next {horizon_days} days)\n"
        output += "-" * 70 + "\n"
        output += f"{'Stock Code':<20} {'Demand':>10} {'Supply':>10} {'Net':>10} {'Lead':>6}\n"
        output += "-" * 70 + "\n"

        critical_count = 0
        for row in shortage_result or []:
            net = float(row.get("NetPosition", 0) or 0)
            lead = row.get("lead_time", 0) or 0
            stock = row.get("stock_code", "")[:19]
            demand = float(row.get("TotalDemand", 0) or 0)
            supply = float(row.get("TotalSupply", 0) or 0)

            if net < 0:
                critical_count += 1
                output += f"{stock:<20} {demand:>10,.0f} {supply:>10,.0f} {net:>10,.0f} {lead:>6}\n"

        if critical_count == 0:
            output += "  No critical shortages found.\n"

        # Long Lead Time Risks
        output += "\nLONG LEAD TIME RISKS (>60 days)\n"
        output += "-" * 70 + "\n"
        output += f"{'Stock Code':<20} {'Lead Time':>10} {'On Hand':>10} {'Demand':>10}\n"
        output += "-" * 70 + "\n"

        for row in risk_result or []:
            stock = row.get("stock_code", "")[:19]
            lead = row.get("lead_time", 0) or 0
            on_hand = float(row.get("qty_on_hand", 0) or 0)
            demand = float(row.get("DemandQty", 0) or 0)
            output += f"{stock:<20} {lead:>10} {on_hand:>10,.0f} {demand:>10,.0f}\n"

        if not risk_result:
            output += "  No long lead time items at risk.\n"

        # Recommendations
        output += "\nRECOMMENDATIONS\n"
        output += "-" * 70 + "\n"
        if critical_count > 10:
            output += f"  ALERT: {critical_count} items have critical shortages\n"
            output += "  - Review MRP suggestions for expedite opportunities\n"
            output += "  - Consider alternative suppliers for long-lead items\n"
        if critical_count > 0:
            output += "  - Process open MRP suggestions promptly\n"
            output += "  - Review demand forecasts for accuracy\n"

        return output

    @mcp.tool()
    @audit_tool_call("get_tempo_data_quality")
    async def get_tempo_data_quality(company_id: str) -> str:
        """Generate a data quality report for Tempo MRP data.

        Identifies data quality issues that can affect MRP accuracy:
        - Missing lead times
        - Missing costs
        - Orphan demands/supply
        - Stale MRP runs
        - Master data gaps

        Args:
            company_id: Company identifier (e.g., 'TTM', 'TTML', 'IV').

        Returns:
            Data quality assessment report with recommendations.
        """
        db = get_tempo_db()

        # Item master quality
        item_sql = """
        SELECT
            COUNT(*) as TotalItems,
            SUM(CASE WHEN lead_time = 0 OR lead_time IS NULL THEN 1 ELSE 0 END) as ZeroLeadTime,
            SUM(CASE WHEN unit_cost = 0 OR unit_cost IS NULL THEN 1 ELSE 0 END) as ZeroCost,
            SUM(CASE WHEN safety_stock = 0 OR safety_stock IS NULL THEN 1 ELSE 0 END) as ZeroSafetyStock,
            SUM(CASE WHEN buying_rule IS NULL OR buying_rule = '' THEN 1 ELSE 0 END) as NoBuyingRule,
            SUM(CASE WHEN lot_sizing_rule IS NULL OR lot_sizing_rule = '' THEN 1 ELSE 0 END) as NoLotRule
        FROM master.Items
        WHERE company_id = %s
        """

        # MRP run history
        run_sql = """
        SELECT
            COUNT(*) as TotalRuns,
            MAX(created_date) as LastRun,
            DATEDIFF(day, MAX(created_date), GETDATE()) as DaysSinceLastRun,
            AVG(items_processed) as AvgItemsProcessed
        FROM mrp.Runs
        WHERE company_id = %s
        """

        # Demand quality for latest run
        demand_sql = """
        WITH LatestRun AS (
            SELECT MAX(run_id) as run_id FROM mrp.Runs WHERE company_id = %s
        )
        SELECT
            COUNT(*) as TotalDemands,
            COUNT(DISTINCT stock_code) as UniqueItems,
            SUM(CASE WHEN required_date < GETDATE() THEN 1 ELSE 0 END) as PastDue,
            SUM(CASE WHEN quantity <= 0 THEN 1 ELSE 0 END) as ZeroQty
        FROM mrp.Demands d, LatestRun r
        WHERE d.run_id = r.run_id AND d.company_id = %s
        """

        # Supply quality for latest run
        supply_sql = """
        WITH LatestRun AS (
            SELECT MAX(run_id) as run_id FROM mrp.Runs WHERE company_id = %s
        )
        SELECT
            COUNT(*) as TotalSupply,
            COUNT(DISTINCT stock_code) as UniqueItems,
            SUM(CASE WHEN due_date < GETDATE() THEN 1 ELSE 0 END) as PastDue,
            SUM(CASE WHEN quantity_available <= 0 THEN 1 ELSE 0 END) as ZeroAvailable
        FROM mrp.Supply s, LatestRun r
        WHERE s.run_id = r.run_id AND s.company_id = %s
        """

        # Forecast data availability
        # Note: forecast table uses item_code, not stock_code
        forecast_sql = """
        SELECT
            COUNT(*) as ForecastRecords,
            COUNT(DISTINCT item_code) as ForecastItems,
            MAX(period_date) as LatestForecast
        FROM forecast.ForecastResults
        WHERE company_id = %s
        """

        # Classification coverage
        # Use DISTINCT to handle duplicates in both tables
        class_sql = """
        SELECT
            COUNT(DISTINCT stock_code) as ClassifiedItems,
            (SELECT COUNT(DISTINCT stock_code) FROM master.Items WHERE company_id = %s) as TotalItems
        FROM analytics.ItemClassification
        WHERE company_id = %s
        """

        try:
            item_result = db.execute_query(item_sql, (company_id,), max_rows=1)
            run_result = db.execute_query(run_sql, (company_id,), max_rows=1)
            demand_result = db.execute_query(
                demand_sql, (company_id, company_id), max_rows=1
            )
            supply_result = db.execute_query(
                supply_sql, (company_id, company_id), max_rows=1
            )
            forecast_result = db.execute_query(forecast_sql, (company_id,), max_rows=1)
            class_result = db.execute_query(
                class_sql, (company_id, company_id), max_rows=1
            )
        except Exception as e:
            return f"Failed to generate data quality report for {company_id}: {e}"

        output = f"\nTEMPO DATA QUALITY REPORT - {company_id}\n"
        output += "=" * 65 + "\n"

        issues = []
        warnings = []

        # Item Master Quality
        output += "\nITEM MASTER DATA QUALITY\n"
        output += "-" * 65 + "\n"
        if item_result:
            item = item_result[0]
            total = int(item.get("TotalItems", 0) or 0)
            zero_lt = int(item.get("ZeroLeadTime", 0) or 0)
            zero_cost = int(item.get("ZeroCost", 0) or 0)
            zero_ss = int(item.get("ZeroSafetyStock", 0) or 0)
            no_buy = int(item.get("NoBuyingRule", 0) or 0)
            no_lot = int(item.get("NoLotRule", 0) or 0)

            lt_pct = (zero_lt / total * 100) if total > 0 else 0
            cost_pct = (zero_cost / total * 100) if total > 0 else 0

            output += f"  Total Items:           {total:,}\n"
            output += f"  Missing Lead Time:     {zero_lt:,} ({lt_pct:.1f}%)\n"
            output += f"  Missing Cost:          {zero_cost:,} ({cost_pct:.1f}%)\n"
            output += f"  Missing Safety Stock:  {zero_ss:,}\n"
            output += f"  Missing Buying Rule:   {no_buy:,}\n"
            output += f"  Missing Lot Size Rule: {no_lot:,}\n"

            if lt_pct > 50:
                issues.append(f"CRITICAL: {lt_pct:.0f}% of items missing lead time")
            elif lt_pct > 10:
                warnings.append(f"WARNING: {lt_pct:.0f}% of items missing lead time")

            if cost_pct > 10:
                warnings.append(f"WARNING: {cost_pct:.0f}% of items missing cost")

        # MRP Run Status
        output += "\nMRP RUN STATUS\n"
        output += "-" * 65 + "\n"
        if run_result:
            run = run_result[0]
            total_runs = int(run.get("TotalRuns", 0) or 0)
            last_run = run.get("LastRun", "Never")
            days_since = int(run.get("DaysSinceLastRun", 999) or 999)
            avg_items = int(run.get("AvgItemsProcessed", 0) or 0)

            output += f"  Total MRP Runs:        {total_runs:,}\n"
            output += f"  Last Run:              {last_run}\n"
            output += f"  Days Since Last Run:   {days_since}\n"
            output += f"  Avg Items Processed:   {avg_items:,}\n"

            if days_since > 7:
                warnings.append(f"WARNING: MRP hasn't run in {days_since} days")
            if total_runs == 0:
                issues.append("CRITICAL: No MRP runs found")

        # Demand Data Quality
        output += "\nDEMAND DATA QUALITY (Latest Run)\n"
        output += "-" * 65 + "\n"
        if demand_result:
            dem = demand_result[0]
            total = int(dem.get("TotalDemands", 0) or 0)
            unique = int(dem.get("UniqueItems", 0) or 0)
            past_due = int(dem.get("PastDue", 0) or 0)
            zero_qty = int(dem.get("ZeroQty", 0) or 0)

            output += f"  Total Demand Records:  {total:,}\n"
            output += f"  Unique Items:          {unique:,}\n"
            output += f"  Past Due Demands:      {past_due:,}\n"
            output += f"  Zero Quantity:         {zero_qty:,}\n"

            if past_due > total * 0.2:
                warnings.append(f"WARNING: {past_due:,} past-due demands need review")

        # Supply Data Quality
        output += "\nSUPPLY DATA QUALITY (Latest Run)\n"
        output += "-" * 65 + "\n"
        if supply_result:
            sup = supply_result[0]
            total = int(sup.get("TotalSupply", 0) or 0)
            unique = int(sup.get("UniqueItems", 0) or 0)
            past_due = int(sup.get("PastDue", 0) or 0)
            zero_avail = int(sup.get("ZeroAvailable", 0) or 0)

            output += f"  Total Supply Records:  {total:,}\n"
            output += f"  Unique Items:          {unique:,}\n"
            output += f"  Past Due Supply:       {past_due:,}\n"
            output += f"  Zero Available:        {zero_avail:,}\n"

            if past_due > total * 0.2:
                warnings.append(f"WARNING: {past_due:,} past-due supplies need review")

        # Forecast Coverage
        output += "\nFORECAST DATA COVERAGE\n"
        output += "-" * 65 + "\n"
        if forecast_result:
            fc = forecast_result[0]
            records = int(fc.get("ForecastRecords", 0) or 0)
            items = int(fc.get("ForecastItems", 0) or 0)
            latest = fc.get("LatestForecast", "None")

            output += f"  Forecast Records:      {records:,}\n"
            output += f"  Items with Forecast:   {items:,}\n"
            output += f"  Latest Forecast Date:  {latest}\n"

            if records == 0:
                warnings.append("INFO: No forecast data available")

        # ABC Classification Coverage
        output += "\nCLASSIFICATION COVERAGE\n"
        output += "-" * 65 + "\n"
        if class_result:
            cls = class_result[0]
            classified = int(cls.get("ClassifiedItems", 0) or 0)
            total = int(cls.get("TotalItems", 0) or 0)
            coverage = (classified / total * 100) if total > 0 else 0

            output += f"  Classified Items:      {classified:,}\n"
            output += f"  Total Items:           {total:,}\n"
            output += f"  Coverage:              {coverage:.1f}%\n"

            if coverage < 50:
                warnings.append(f"INFO: Only {coverage:.0f}% of items have ABC classification")

        # Summary and Recommendations
        output += "\nDATA QUALITY SUMMARY\n"
        output += "-" * 65 + "\n"

        if issues:
            output += "\nCRITICAL ISSUES:\n"
            for issue in issues:
                output += f"  - {issue}\n"

        if warnings:
            output += "\nWARNINGS:\n"
            for warning in warnings:
                output += f"  - {warning}\n"

        if not issues and not warnings:
            output += "  No significant data quality issues detected.\n"

        output += "\nRECOMMENDATIONS:\n"
        output += "-" * 65 + "\n"
        if any("lead time" in i.lower() for i in issues + warnings):
            output += "  1. Update item master with accurate lead times\n"
        if any("cost" in w.lower() for w in warnings):
            output += "  2. Review and update item costs in master data\n"
        if any("mrp hasn't run" in w.lower() for w in warnings):
            output += "  3. Schedule regular MRP runs\n"
        if any("past-due" in w.lower() for w in warnings):
            output += "  4. Review and clean up past-due records\n"

        return output

    @mcp.tool()
    @audit_tool_call("analyze_lead_time_reliability")
    async def analyze_lead_time_reliability(company_id: str) -> str:
        """Analyze lead time reliability comparing master data vs actual performance.

        Uses historical lead time metrics to identify:
        - Items where actual lead times differ significantly from master
        - High-variability suppliers/items
        - Items needing master data updates
        - P95 lead times for safety stock calculations

        Args:
            company_id: Company identifier (e.g., 'TTM', 'TTML', 'IV').

        Returns:
            Lead time reliability analysis report.
        """
        db = get_tempo_db()

        # Items where actual LT is significantly different from master
        variance_sql = """
        WITH ItemMetrics AS (
            SELECT
                m.stock_code,
                m.avg_lead_time_days,
                m.p95_lead_time_days,
                m.lead_time_variability,
                m.sample_count,
                m.trend_direction,
                m.data_quality_score,
                ROW_NUMBER() OVER (PARTITION BY m.stock_code ORDER BY m.sample_count DESC) as rn
            FROM analytics.LeadTimeMetrics m
            WHERE m.company_id = %s AND m.sample_count >= 3
        ),
        ItemMaster AS (
            SELECT stock_code, lead_time, description_1,
                   ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY stock_code) as rn
            FROM master.Items WHERE company_id = %s
        )
        SELECT TOP 20
            m.stock_code,
            i.description_1 as Description,
            i.lead_time as MasterLT,
            m.avg_lead_time_days as ActualLT,
            m.p95_lead_time_days as P95_LT,
            m.avg_lead_time_days - i.lead_time as Variance,
            m.lead_time_variability as Variability,
            m.sample_count as Samples,
            m.trend_direction as Trend,
            m.data_quality_score as Quality
        FROM ItemMetrics m
        JOIN ItemMaster i ON m.stock_code = i.stock_code AND i.rn = 1
        WHERE m.rn = 1 AND i.lead_time > 0
        ORDER BY ABS(m.avg_lead_time_days - i.lead_time) DESC
        """

        # High variability items
        variability_sql = """
        WITH ItemMetrics AS (
            SELECT
                m.stock_code,
                m.avg_lead_time_days,
                m.lead_time_variability,
                m.sample_count,
                ROW_NUMBER() OVER (PARTITION BY m.stock_code ORDER BY m.sample_count DESC) as rn
            FROM analytics.LeadTimeMetrics m
            WHERE m.company_id = %s AND m.sample_count >= 5
        ),
        ItemMaster AS (
            SELECT stock_code, description_1,
                   ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY stock_code) as rn
            FROM master.Items WHERE company_id = %s
        )
        SELECT TOP 10
            m.stock_code,
            i.description_1 as Description,
            m.avg_lead_time_days as AvgLT,
            m.lead_time_variability as Variability,
            m.sample_count as Samples
        FROM ItemMetrics m
        JOIN ItemMaster i ON m.stock_code = i.stock_code AND i.rn = 1
        WHERE m.rn = 1 AND m.lead_time_variability > 50
        ORDER BY m.lead_time_variability DESC
        """

        # Summary statistics
        summary_sql = """
        SELECT
            COUNT(DISTINCT stock_code) as ItemsWithMetrics,
            AVG(avg_lead_time_days) as OverallAvgLT,
            AVG(lead_time_variability) as OverallAvgVariability,
            SUM(CASE WHEN sample_count >= 5 THEN 1 ELSE 0 END) as HighConfidenceItems
        FROM analytics.LeadTimeMetrics
        WHERE company_id = %s
        """

        try:
            variance_result = db.execute_query(
                variance_sql, (company_id, company_id), max_rows=20
            )
            variability_result = db.execute_query(
                variability_sql, (company_id, company_id), max_rows=10
            )
            summary_result = db.execute_query(summary_sql, (company_id,), max_rows=1)
        except Exception as e:
            return f"Failed to analyze lead time reliability for {company_id}: {e}"

        output = f"\nLEAD TIME RELIABILITY ANALYSIS - {company_id}\n"
        output += "=" * 75 + "\n"

        # Summary
        output += "\nSUMMARY\n"
        output += "-" * 75 + "\n"
        if summary_result:
            s = summary_result[0]
            output += f"  Items with lead time metrics: {int(s.get('ItemsWithMetrics', 0) or 0):,}\n"
            output += f"  High confidence items (5+ samples): {int(s.get('HighConfidenceItems', 0) or 0):,}\n"
            output += f"  Overall avg lead time: {float(s.get('OverallAvgLT', 0) or 0):.1f} days\n"
            output += f"  Overall avg variability: {float(s.get('OverallAvgVariability', 0) or 0):.1f}%\n"

        # Variance analysis
        output += "\nLEAD TIME VARIANCE (Actual vs Master)\n"
        output += "-" * 75 + "\n"
        output += f"{'Stock Code':<22} {'Master':>7} {'Actual':>7} {'P95':>7} {'Var':>7} {'Variab%':>8} {'Trend':<8}\n"
        output += "-" * 75 + "\n"

        longer_count = 0
        shorter_count = 0
        for row in variance_result or []:
            var = float(row.get("Variance", 0) or 0)
            if var > 5:
                longer_count += 1
                marker = " LONGER"
            elif var < -5:
                shorter_count += 1
                marker = " shorter"
            else:
                marker = ""

            output += f"{str(row.get('stock_code', ''))[:21]:<22} "
            output += f"{row.get('MasterLT', 0):>7} "
            output += f"{float(row.get('ActualLT', 0) or 0):>7.0f} "
            output += f"{float(row.get('P95_LT', 0) or 0):>7.0f} "
            output += f"{var:>+7.0f} "
            output += f"{float(row.get('Variability', 0) or 0):>7.1f}% "
            output += f"{str(row.get('Trend', ''))[:7]:<8}{marker}\n"

        # High variability items
        output += "\nHIGH VARIABILITY ITEMS (>50% variability)\n"
        output += "-" * 75 + "\n"
        if variability_result:
            output += f"{'Stock Code':<25} {'Avg LT':>10} {'Variability':>12} {'Samples':>10}\n"
            output += "-" * 75 + "\n"
            for row in variability_result:
                output += f"{str(row.get('stock_code', ''))[:24]:<25} "
                output += f"{float(row.get('AvgLT', 0) or 0):>10.0f} "
                output += f"{float(row.get('Variability', 0) or 0):>11.1f}% "
                output += f"{row.get('Samples', 0):>10}\n"
        else:
            output += "  No high-variability items found.\n"

        # Recommendations
        output += "\nRECOMMENDATIONS\n"
        output += "-" * 75 + "\n"
        if longer_count > 0:
            output += f"  - {longer_count} items have actual LT longer than master - update master data\n"
            output += "  - Use P95 lead times for safety stock calculations\n"
        if shorter_count > 0:
            output += f"  - {shorter_count} items have shorter actual LT - potential to reduce master LT\n"
        if variability_result:
            output += "  - High-variability items need safety stock buffers\n"
            output += "  - Consider alternate suppliers for unreliable items\n"

        return output

    @mcp.tool()
    @audit_tool_call("get_cross_company_status")
    async def get_cross_company_status() -> str:
        """Get MRP health status across all Tempo companies.

        Provides a cross-company view of:
        - MRP run status and recency
        - Item and suggestion counts
        - Stale company alerts
        - Demand/supply balance by company

        Returns:
            Cross-company MRP health dashboard.
        """
        db = get_tempo_db()

        # Company MRP status
        status_sql = """
        SELECT
            c.company_id,
            c.company_name,
            c.is_active,
            (SELECT MAX(created_date) FROM mrp.Runs WHERE company_id = c.company_id) as LastRun,
            (SELECT DATEDIFF(day, MAX(created_date), GETDATE()) FROM mrp.Runs WHERE company_id = c.company_id) as DaysSinceRun,
            (SELECT MAX(items_processed) FROM mrp.Runs WHERE company_id = c.company_id) as ItemsProcessed,
            (SELECT COUNT(*) FROM mrp.Suggestions s
             WHERE s.company_id = c.company_id
               AND s.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = c.company_id)) as OpenSuggestions,
            (SELECT SUM(CASE WHEN s.critical_flag = 1 THEN 1 ELSE 0 END) FROM mrp.Suggestions s
             WHERE s.company_id = c.company_id
               AND s.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = c.company_id)) as CriticalSuggestions
        FROM auth.Companies c
        WHERE c.is_active = 1
        ORDER BY c.company_name
        """

        # Demand/Supply balance by company
        balance_sql = """
        SELECT
            r.company_id,
            (SELECT SUM(d.quantity) FROM mrp.Demands d WHERE d.run_id = r.run_id AND d.company_id = r.company_id) as TotalDemand,
            (SELECT SUM(COALESCE(s.quantity_available, s.quantity)) FROM mrp.Supply s WHERE s.run_id = r.run_id AND s.company_id = r.company_id) as TotalSupply
        FROM mrp.Runs r
        WHERE r.run_id = (SELECT MAX(run_id) FROM mrp.Runs r2 WHERE r2.company_id = r.company_id)
        """

        try:
            status_result = db.execute_query(status_sql, max_rows=20)
            balance_result = db.execute_query(balance_sql, max_rows=20)
        except Exception as e:
            return f"Failed to get cross-company status: {e}"

        # Create balance lookup
        balance_lookup = {}
        for row in balance_result or []:
            balance_lookup[row.get("company_id")] = {
                "demand": float(row.get("TotalDemand", 0) or 0),
                "supply": float(row.get("TotalSupply", 0) or 0),
            }

        output = "\nCROSS-COMPANY MRP STATUS\n"
        output += "=" * 80 + "\n"

        # Status table
        output += "\nMRP RUN STATUS\n"
        output += "-" * 80 + "\n"
        output += f"{'Company':<8} {'Name':<22} {'Last Run':<12} {'Days':>5} {'Items':>10} {'Suggest':>8} {'Crit':>6} {'Status':<10}\n"
        output += "-" * 80 + "\n"

        stale_companies = []
        active_count = 0
        for row in status_result or []:
            company_id = row.get("company_id", "")
            days = int(row.get("DaysSinceRun", 999) or 999)
            last_run = str(row.get("LastRun", "Never"))[:10] if row.get("LastRun") else "Never"

            if days <= 7:
                status = "OK"
                active_count += 1
            elif days <= 14:
                status = "WARNING"
                stale_companies.append(company_id)
            else:
                status = "STALE"
                stale_companies.append(company_id)

            output += f"{company_id:<8} "
            output += f"{str(row.get('company_name', ''))[:21]:<22} "
            output += f"{last_run:<12} "
            output += f"{days:>5} "
            output += f"{int(row.get('ItemsProcessed', 0) or 0):>10,} "
            output += f"{int(row.get('OpenSuggestions', 0) or 0):>8} "
            output += f"{int(row.get('CriticalSuggestions', 0) or 0):>6} "
            output += f"{status:<10}\n"

        # Demand/Supply balance
        output += "\nDEMAND/SUPPLY COVERAGE\n"
        output += "-" * 80 + "\n"
        output += f"{'Company':<8} {'Total Demand':>15} {'Total Supply':>15} {'Coverage':>12} {'Status':<10}\n"
        output += "-" * 80 + "\n"

        for row in status_result or []:
            company_id = row.get("company_id", "")
            bal = balance_lookup.get(company_id, {"demand": 0, "supply": 0})
            demand = bal["demand"]
            supply = bal["supply"]
            coverage = (supply / demand * 100) if demand > 0 else 0

            if coverage >= 80:
                cov_status = "GOOD"
            elif coverage >= 50:
                cov_status = "WARNING"
            else:
                cov_status = "LOW"

            output += f"{company_id:<8} "
            output += f"{demand:>15,.0f} "
            output += f"{supply:>15,.0f} "
            output += f"{coverage:>11.1f}% "
            output += f"{cov_status:<10}\n"

        # Summary
        output += "\nSUMMARY\n"
        output += "-" * 80 + "\n"
        output += f"  Active companies (MRP run ≤7 days): {active_count}\n"
        if stale_companies:
            output += f"  Stale companies needing attention: {', '.join(stale_companies)}\n"
            output += "\n  RECOMMENDATION: Run MRP for stale companies\n"
        else:
            output += "  All companies have recent MRP runs.\n"

        return output

    @mcp.tool()
    @audit_tool_call("get_planning_risks")
    async def get_planning_risks(company_id: str) -> str:
        """Identify items with planning risks due to lead time discrepancies.

        Finds items where actual lead times are significantly longer than
        master data, creating stockout risk. Prioritizes by demand volume
        and ABC classification.

        Args:
            company_id: Company identifier (e.g., 'TTM', 'TTML', 'IV').

        Returns:
            Planning risk analysis with prioritized action items.
        """
        db = get_tempo_db()

        # High-risk items: actual LT >> master LT with active demand
        risk_sql = """
        WITH ItemMetrics AS (
            SELECT
                m.stock_code,
                m.avg_lead_time_days,
                m.p95_lead_time_days,
                m.lead_time_variability,
                m.sample_count,
                ROW_NUMBER() OVER (PARTITION BY m.stock_code ORDER BY m.sample_count DESC) as rn
            FROM analytics.LeadTimeMetrics m
            WHERE m.company_id = %s AND m.sample_count >= 3
        ),
        ItemMaster AS (
            SELECT stock_code, lead_time, description_1,
                   ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY stock_code) as rn
            FROM master.Items WHERE company_id = %s
        ),
        ItemDemand AS (
            SELECT stock_code, SUM(quantity) as TotalDemand
            FROM mrp.Demands
            WHERE run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
              AND company_id = %s
            GROUP BY stock_code
        ),
        ItemClass AS (
            SELECT stock_code, abc_class,
                   ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY classification_id DESC) as rn
            FROM analytics.ItemClassification WHERE company_id = %s
        )
        SELECT TOP 25
            m.stock_code,
            i.description_1 as Description,
            i.lead_time as MasterLT,
            m.avg_lead_time_days as ActualLT,
            m.p95_lead_time_days as P95_LT,
            m.avg_lead_time_days - i.lead_time as LTGap,
            CASE WHEN i.lead_time > 0
                 THEN (m.avg_lead_time_days - i.lead_time) * 100.0 / i.lead_time
                 ELSE 0 END as PctLonger,
            d.TotalDemand,
            COALESCE(c.abc_class, '-') as ABCClass,
            m.lead_time_variability as Variability
        FROM ItemMetrics m
        JOIN ItemMaster i ON m.stock_code = i.stock_code AND i.rn = 1
        LEFT JOIN ItemDemand d ON m.stock_code = d.stock_code
        LEFT JOIN ItemClass c ON m.stock_code = c.stock_code AND c.rn = 1
        WHERE m.rn = 1
          AND i.lead_time > 0
          AND m.avg_lead_time_days > i.lead_time * 1.5  -- Actual is 50%+ longer
          AND (d.TotalDemand > 0 OR c.abc_class IN ('A', 'B'))
        ORDER BY
            CASE c.abc_class WHEN 'A' THEN 1 WHEN 'B' THEN 2 ELSE 3 END,
            d.TotalDemand DESC
        """

        # Risk summary by severity
        summary_sql = """
        WITH ItemMetrics AS (
            SELECT
                m.stock_code,
                m.avg_lead_time_days,
                ROW_NUMBER() OVER (PARTITION BY m.stock_code ORDER BY m.sample_count DESC) as rn
            FROM analytics.LeadTimeMetrics m
            WHERE m.company_id = %s AND m.sample_count >= 3
        ),
        ItemMaster AS (
            SELECT stock_code, lead_time,
                   ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY stock_code) as rn
            FROM master.Items WHERE company_id = %s
        )
        SELECT
            CASE
                WHEN m.avg_lead_time_days > i.lead_time * 3 THEN 'CRITICAL (3x+)'
                WHEN m.avg_lead_time_days > i.lead_time * 2 THEN 'HIGH (2-3x)'
                WHEN m.avg_lead_time_days > i.lead_time * 1.5 THEN 'MEDIUM (1.5-2x)'
                ELSE 'LOW (<1.5x)'
            END as RiskLevel,
            COUNT(*) as ItemCount
        FROM ItemMetrics m
        JOIN ItemMaster i ON m.stock_code = i.stock_code AND i.rn = 1
        WHERE m.rn = 1 AND i.lead_time > 0
        GROUP BY
            CASE
                WHEN m.avg_lead_time_days > i.lead_time * 3 THEN 'CRITICAL (3x+)'
                WHEN m.avg_lead_time_days > i.lead_time * 2 THEN 'HIGH (2-3x)'
                WHEN m.avg_lead_time_days > i.lead_time * 1.5 THEN 'MEDIUM (1.5-2x)'
                ELSE 'LOW (<1.5x)'
            END
        ORDER BY
            CASE
                WHEN m.avg_lead_time_days > i.lead_time * 3 THEN 1
                WHEN m.avg_lead_time_days > i.lead_time * 2 THEN 2
                WHEN m.avg_lead_time_days > i.lead_time * 1.5 THEN 3
                ELSE 4
            END
        """

        try:
            risk_result = db.execute_query(
                risk_sql,
                (company_id, company_id, company_id, company_id, company_id),
                max_rows=25,
            )
            summary_result = db.execute_query(
                summary_sql, (company_id, company_id), max_rows=10
            )
        except Exception as e:
            return f"Failed to get planning risks for {company_id}: {e}"

        output = f"\nPLANNING RISK ANALYSIS - {company_id}\n"
        output += "=" * 80 + "\n"

        # Risk summary
        output += "\nRISK SUMMARY (Actual LT vs Master LT)\n"
        output += "-" * 80 + "\n"
        critical_count = 0
        for row in summary_result or []:
            level = row.get("RiskLevel", "Unknown")
            count = int(row.get("ItemCount", 0) or 0)
            marker = " <-- ACTION REQUIRED" if "CRITICAL" in level or "HIGH" in level else ""
            output += f"  {level:<20} {count:>8,} items{marker}\n"
            if "CRITICAL" in level or "HIGH" in level:
                critical_count += count

        # Detailed risk items
        output += "\nHIGH-RISK ITEMS (Prioritized by ABC class and demand)\n"
        output += "-" * 80 + "\n"
        output += f"{'Stock Code':<20} {'ABC':>4} {'Master':>7} {'Actual':>7} {'P95':>7} {'%Longer':>8} {'Demand':>10}\n"
        output += "-" * 80 + "\n"

        for row in risk_result or []:
            abc = row.get("ABCClass", "-")
            pct = float(row.get("PctLonger", 0) or 0)
            demand = float(row.get("TotalDemand", 0) or 0)

            output += f"{str(row.get('stock_code', ''))[:19]:<20} "
            output += f"{abc:>4} "
            output += f"{row.get('MasterLT', 0):>7} "
            output += f"{float(row.get('ActualLT', 0) or 0):>7.0f} "
            output += f"{float(row.get('P95_LT', 0) or 0):>7.0f} "
            output += f"{pct:>7.0f}% "
            output += f"{demand:>10,.0f}\n"

        if not risk_result:
            output += "  No high-risk items found.\n"

        # Recommendations
        output += "\nRECOMMENDATIONS\n"
        output += "-" * 80 + "\n"
        if critical_count > 0:
            output += f"  URGENT: {critical_count} items have lead times 2x+ longer than planned\n"
            output += "  Actions:\n"
            output += "    1. Update master lead times to reflect actual performance\n"
            output += "    2. Increase safety stock for high-variability items\n"
            output += "    3. Use P95 lead times for planning critical items\n"
            output += "    4. Consider alternate suppliers for unreliable items\n"
        else:
            output += "  Lead times are generally aligned with master data.\n"

        return output

    @mcp.tool()
    @audit_tool_call("analyze_abc_distribution")
    async def analyze_abc_distribution(company_id: str) -> str:
        """Analyze ABC classification distribution and inventory strategy.

        Provides insights on:
        - ABC class distribution by item count and revenue
        - A-class items missing safety stock
        - Service level recommendations
        - Inventory investment analysis

        Args:
            company_id: Company identifier (e.g., 'TTM', 'TTML', 'IV').

        Returns:
            ABC classification analysis with recommendations.
        """
        db = get_tempo_db()

        # ABC distribution summary
        dist_sql = """
        SELECT
            abc_class,
            COUNT(DISTINCT stock_code) as ItemCount,
            SUM(total_revenue) as TotalRevenue,
            AVG(revenue_percentage) as AvgRevenuePct,
            SUM(total_transaction_count) as TotalTransactions
        FROM analytics.ItemClassification
        WHERE company_id = %s
        GROUP BY abc_class
        ORDER BY abc_class
        """

        # A-class items detail
        a_class_sql = """
        WITH ClassItems AS (
            SELECT stock_code, abc_class, total_revenue, revenue_percentage,
                   ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY classification_id DESC) as rn
            FROM analytics.ItemClassification
            WHERE company_id = %s AND abc_class = 'A'
        ),
        ItemMaster AS (
            SELECT stock_code, description_1, safety_stock, lead_time,
                   ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY stock_code) as rn
            FROM master.Items WHERE company_id = %s
        ),
        ItemInventory AS (
            SELECT stock_code, SUM(qty_on_hand) as QtyOnHand, SUM(qty_available) as QtyAvailable
            FROM mrp.Inventory
            WHERE run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
              AND company_id = %s
            GROUP BY stock_code
        )
        SELECT TOP 20
            c.stock_code,
            i.description_1 as Description,
            c.total_revenue as Revenue,
            c.revenue_percentage as RevenuePct,
            COALESCE(i.safety_stock, 0) as SafetyStock,
            i.lead_time as LeadTime,
            COALESCE(v.QtyOnHand, 0) as QtyOnHand,
            COALESCE(v.QtyAvailable, 0) as QtyAvailable
        FROM ClassItems c
        JOIN ItemMaster i ON c.stock_code = i.stock_code AND i.rn = 1
        LEFT JOIN ItemInventory v ON c.stock_code = v.stock_code
        WHERE c.rn = 1
        ORDER BY c.total_revenue DESC
        """

        # Items with demand but no ABC classification
        unclassified_sql = """
        WITH DemandItems AS (
            SELECT DISTINCT stock_code
            FROM mrp.Demands
            WHERE run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
              AND company_id = %s
        ),
        ClassifiedItems AS (
            SELECT DISTINCT stock_code
            FROM analytics.ItemClassification
            WHERE company_id = %s
        )
        SELECT COUNT(*) as UnclassifiedCount
        FROM DemandItems d
        WHERE NOT EXISTS (SELECT 1 FROM ClassifiedItems c WHERE c.stock_code = d.stock_code)
        """

        try:
            dist_result = db.execute_query(dist_sql, (company_id,), max_rows=10)
            a_class_result = db.execute_query(
                a_class_sql, (company_id, company_id, company_id, company_id), max_rows=20
            )
            unclass_result = db.execute_query(
                unclassified_sql, (company_id, company_id, company_id), max_rows=1
            )
        except Exception as e:
            return f"Failed to analyze ABC distribution for {company_id}: {e}"

        output = f"\nABC CLASSIFICATION ANALYSIS - {company_id}\n"
        output += "=" * 75 + "\n"

        # Distribution summary
        output += "\nCLASS DISTRIBUTION\n"
        output += "-" * 75 + "\n"
        output += f"{'Class':<8} {'Items':>10} {'Revenue':>15} {'Avg Rev%':>12} {'Transactions':>12}\n"
        output += "-" * 75 + "\n"

        total_items = 0
        total_revenue = 0
        a_count = 0
        for row in dist_result or []:
            abc = row.get("abc_class", "?")
            items = int(row.get("ItemCount", 0) or 0)
            revenue = float(row.get("TotalRevenue", 0) or 0)
            total_items += items
            total_revenue += revenue
            if abc == "A":
                a_count = items

            output += f"{abc:<8} "
            output += f"{items:>10,} "
            output += f"{revenue:>15,.0f} "
            output += f"{float(row.get('AvgRevenuePct', 0) or 0):>11.2f}% "
            output += f"{int(row.get('TotalTransactions', 0) or 0):>12,}\n"

        output += "-" * 75 + "\n"
        output += f"{'TOTAL':<8} {total_items:>10,} {total_revenue:>15,.0f}\n"

        # Pareto check
        if total_items > 0 and a_count > 0:
            a_pct = (a_count / total_items * 100)
            output += f"\nPareto Check: {a_count} A-class items ({a_pct:.1f}%) drive majority of revenue\n"

        # A-class items detail
        output += "\nA-CLASS ITEMS (Top Revenue Drivers)\n"
        output += "-" * 75 + "\n"
        output += f"{'Stock Code':<20} {'Revenue':>12} {'Rev%':>7} {'Safety':>8} {'OnHand':>10} {'Status':<10}\n"
        output += "-" * 75 + "\n"

        a_without_safety = 0
        a_low_stock = 0
        for row in a_class_result or []:
            safety = int(row.get("SafetyStock", 0) or 0)
            on_hand = float(row.get("QtyOnHand", 0) or 0)
            available = float(row.get("QtyAvailable", 0) or 0)

            if safety == 0:
                status = "NO SAFETY"
                a_without_safety += 1
            elif on_hand < safety:
                status = "LOW STOCK"
                a_low_stock += 1
            else:
                status = "OK"

            output += f"{str(row.get('stock_code', ''))[:19]:<20} "
            output += f"{float(row.get('Revenue', 0) or 0):>12,.0f} "
            output += f"{float(row.get('RevenuePct', 0) or 0):>6.2f}% "
            output += f"{safety:>8} "
            output += f"{on_hand:>10,.0f} "
            output += f"{status:<10}\n"

        # Unclassified items
        unclass_count = 0
        if unclass_result:
            unclass_count = int(unclass_result[0].get("UnclassifiedCount", 0) or 0)

        # Summary and recommendations
        output += "\nSUMMARY & RECOMMENDATIONS\n"
        output += "-" * 75 + "\n"

        if a_without_safety > 0:
            output += f"  WARNING: {a_without_safety} A-class items have no safety stock\n"
            output += "    -> Set safety stock for all A-class items (recommend 2-4 weeks)\n"

        if a_low_stock > 0:
            output += f"  ALERT: {a_low_stock} A-class items below safety stock level\n"
            output += "    -> Expedite replenishment for critical items\n"

        if unclass_count > 0:
            output += f"  INFO: {unclass_count} items with demand have no ABC classification\n"
            output += "    -> Run classification to include all active items\n"

        output += "\nService Level Recommendations:\n"
        output += "    A-class: 98-99% service level (critical items)\n"
        output += "    B-class: 95-97% service level (important items)\n"
        output += "    C-class: 90-95% service level (standard items)\n"

        return output
