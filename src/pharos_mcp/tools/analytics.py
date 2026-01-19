"""
Business analytics tools for Pharos MCP.

Provides KPIs, health metrics, and business intelligence that address
common questions discovered through real-world usage patterns.
"""

from mcp.server.fastmcp import FastMCP

from ..core.audit import audit_tool_call
from ..core.database import get_company_db


def register_analytics_tools(mcp: FastMCP) -> None:
    """Register business analytics tools with the MCP server."""

    @mcp.tool()
    @audit_tool_call("get_kpi_dashboard")
    async def get_kpi_dashboard() -> str:
        """Get key performance indicators for the business.

        Returns a dashboard of critical business metrics including:
        - Cash conversion cycle (DSO, DIO, DPO)
        - AR and AP balances
        - Inventory value
        - Sales performance

        Returns:
            Formatted KPI dashboard with current metrics.
        """
        db = get_company_db()

        sql = """
        WITH Metrics AS (
            SELECT
                (SELECT SUM(b.ValCurrentInv + b.Val30daysInv + b.Val60daysInv +
                            b.Val90daysInv + b.Val120daysInv) FROM ArCustomerBal b) as TotalAR,
                (SELECT SUM(s.CurrentBalance) FROM ApSupplier s WHERE s.CurrentBalance > 0) as TotalAP,
                (SELECT SUM(w.QtyOnHand * w.UnitCost) FROM InvWarehouse w WHERE w.QtyOnHand > 0) as TotalInventory,
                (SELECT COUNT(DISTINCT w.StockCode) FROM InvWarehouse w WHERE w.QtyOnHand > 0) as ActiveSKUs,
                (SELECT SUM(d.MOrderQty * d.MPrice)
                 FROM SorMaster m JOIN SorDetail d ON m.SalesOrder = d.SalesOrder
                 WHERE m.OrderDate >= DATEADD(year, -1, GETDATE())) as AnnualSales,
                (SELECT SUM(d.MOrderQty * d.MPrice)
                 FROM PorMasterHdr p JOIN PorMasterDetail d ON p.PurchaseOrder = d.PurchaseOrder
                 WHERE p.OrderEntryDate >= DATEADD(year, -1, GETDATE())) as AnnualPurchases,
                (SELECT SUM(ABS(TrnValue)) FROM InvMovements
                 WHERE TrnType IN ('I', 'S') AND EntryDate >= DATEADD(year, -1, GETDATE())) as AnnualCOGS,
                (SELECT COUNT(DISTINCT m.SalesOrder) FROM SorMaster m
                 WHERE m.OrderDate >= DATEADD(month, -1, GETDATE())) as OrdersLast30Days,
                (SELECT COUNT(DISTINCT m.Customer) FROM SorMaster m
                 WHERE m.OrderDate >= DATEADD(month, -1, GETDATE())) as ActiveCustomers30Days
        )
        SELECT
            TotalAR,
            TotalAP,
            TotalInventory,
            ActiveSKUs,
            AnnualSales,
            AnnualPurchases,
            AnnualCOGS,
            OrdersLast30Days,
            ActiveCustomers30Days,
            CASE WHEN AnnualSales > 0 THEN (TotalAR / (AnnualSales / 365)) ELSE 0 END as DSO,
            CASE WHEN AnnualCOGS > 0 THEN (TotalInventory / (AnnualCOGS / 365)) ELSE 0 END as DIO,
            CASE WHEN AnnualPurchases > 0 THEN (TotalAP / (AnnualPurchases / 365)) ELSE 0 END as DPO
        FROM Metrics
        """

        try:
            results = db.execute_query(sql, max_rows=1)
        except Exception as e:
            return f"Failed to get KPI dashboard: {e}"

        if not results:
            return "No data available for KPI dashboard."

        row = results[0]

        def fmt(n):
            if n is None:
                return "N/A"
            return f"{float(n):,.0f}"

        def fmt_dec(n, decimals=1):
            if n is None:
                return "N/A"
            return f"{float(n):,.{decimals}f}"

        ar = float(row.get("TotalAR", 0) or 0)
        ap = float(row.get("TotalAP", 0) or 0)
        inv = float(row.get("TotalInventory", 0) or 0)
        sales = float(row.get("AnnualSales", 0) or 0)
        dso = float(row.get("DSO", 0) or 0)
        dio = float(row.get("DIO", 0) or 0)
        dpo = float(row.get("DPO", 0) or 0)
        ccc = dso + dio - dpo

        output = """
KPI DASHBOARD
=============

CASH FLOW METRICS
-----------------
  Accounts Receivable:     {ar:>15}
  Accounts Payable:        {ap:>15}
  Net Working Capital:     {nwc:>15}

CASH CONVERSION CYCLE
---------------------
  DSO (Days Sales Out):    {dso:>12} days  (target: <30)
  DIO (Days Inventory):    {dio:>12} days  (target: <60)
  DPO (Days Payable):      {dpo:>12} days
  Cash Conversion Cycle:   {ccc:>12} days  (lower is better)

INVENTORY
---------
  Total Inventory Value:   {inv:>15}
  Active SKUs:             {skus:>15}

SALES PERFORMANCE (12 months)
-----------------------------
  Annual Sales:            {sales:>15}
  Orders (last 30 days):   {orders:>15}
  Active Customers:        {custs:>15}

HEALTH INDICATORS
-----------------
  DSO:  {dso_status}
  DIO:  {dio_status}
  CCC:  {ccc_status}
""".format(
            ar=fmt(ar),
            ap=fmt(ap),
            nwc=fmt(ar - ap + inv),
            dso=fmt_dec(dso),
            dio=fmt_dec(dio),
            dpo=fmt_dec(dpo),
            ccc=fmt_dec(ccc),
            inv=fmt(inv),
            skus=fmt(row.get("ActiveSKUs", 0)),
            sales=fmt(sales),
            orders=fmt(row.get("OrdersLast30Days", 0)),
            custs=fmt(row.get("ActiveCustomers30Days", 0)),
            dso_status="GOOD" if dso < 30 else ("WARNING" if dso < 45 else "ALERT"),
            dio_status="GOOD" if dio < 60 else ("WARNING" if dio < 90 else "ALERT"),
            ccc_status="GOOD" if ccc < 60 else ("WARNING" if ccc < 90 else "ALERT"),
        )

        return output

    @mcp.tool()
    @audit_tool_call("analyze_customer_health")
    async def analyze_customer_health() -> str:
        """Analyze customer health including churn risk and payment behavior.

        Identifies:
        - Customers at risk of churning (no orders in 90+ days)
        - Late payers with overdue balances
        - Top customers by revenue
        - Customer concentration risk

        Returns:
            Customer health analysis report.
        """
        db = get_company_db()

        churn_sql = """
        SELECT TOP 10
            c.Customer,
            c.Name,
            DATEDIFF(day, c.DateLastSale, GETDATE()) as DaysSinceOrder,
            (SELECT SUM(d.MOrderQty * d.MPrice)
             FROM SorMaster m JOIN SorDetail d ON m.SalesOrder = d.SalesOrder
             WHERE m.Customer = c.Customer
             AND m.OrderDate >= DATEADD(year, -2, c.DateLastSale)) as HistoricalRevenue
        FROM ArCustomer c
        WHERE c.DateLastSale < DATEADD(day, -90, GETDATE())
          AND c.DateLastSale IS NOT NULL
          AND c.CustomerOnHold <> 'Y'
        ORDER BY HistoricalRevenue DESC
        """

        late_sql = """
        SELECT TOP 10
            c.Customer,
            c.Name,
            b.Val90daysInv + b.Val120daysInv as OverdueAmount,
            b.ValCurrentInv + b.Val30daysInv + b.Val60daysInv +
            b.Val90daysInv + b.Val120daysInv as TotalOwing
        FROM ArCustomer c
        JOIN ArCustomerBal b ON c.Customer = b.Customer
        WHERE (b.Val90daysInv + b.Val120daysInv) > 0
        ORDER BY OverdueAmount DESC
        """

        top_sql = """
        SELECT TOP 10
            m.Customer,
            c.Name,
            SUM(d.MOrderQty * d.MPrice) as Revenue
        FROM SorMaster m
        JOIN SorDetail d ON m.SalesOrder = d.SalesOrder
        JOIN ArCustomer c ON m.Customer = c.Customer
        WHERE m.OrderDate >= DATEADD(year, -1, GETDATE())
        GROUP BY m.Customer, c.Name
        ORDER BY Revenue DESC
        """

        try:
            churn_results = db.execute_query(churn_sql, max_rows=10)
            late_results = db.execute_query(late_sql, max_rows=10)
            top_results = db.execute_query(top_sql, max_rows=10)
        except Exception as e:
            return f"Failed to analyze customer health: {e}"

        output = "\nCUSTOMER HEALTH ANALYSIS\n"
        output += "=" * 60 + "\n"

        # Churn risk
        output += "\nCHURN RISK (No orders in 90+ days)\n"
        output += "-" * 60 + "\n"
        if churn_results:
            for row in churn_results:
                hist_rev = float(row.get("HistoricalRevenue", 0) or 0)
                if hist_rev > 0:
                    output += f"  {row['Customer']}: {row['Name'][:30]}\n"
                    output += f"    Days since order: {row['DaysSinceOrder']}, "
                    output += f"Historical revenue: {hist_rev:,.0f}\n"
        else:
            output += "  No customers at churn risk.\n"

        # Late payers
        output += "\nLATE PAYERS (90+ days overdue)\n"
        output += "-" * 60 + "\n"
        if late_results:
            for row in late_results:
                output += f"  {row['Customer']}: {row['Name'][:30]}\n"
                output += f"    Overdue: {float(row['OverdueAmount']):,.0f}, "
                output += f"Total owing: {float(row['TotalOwing']):,.0f}\n"
        else:
            output += "  No late payers.\n"

        # Top customers and concentration
        output += "\nTOP CUSTOMERS (12 months) & CONCENTRATION RISK\n"
        output += "-" * 60 + "\n"
        if top_results:
            total_rev = sum(float(r.get("Revenue", 0) or 0) for r in top_results)
            top_rev = float(top_results[0].get("Revenue", 0) or 0) if top_results else 0
            concentration = (top_rev / total_rev * 100) if total_rev > 0 else 0

            for i, row in enumerate(top_results[:5], 1):
                rev = float(row.get("Revenue", 0) or 0)
                pct = (rev / total_rev * 100) if total_rev > 0 else 0
                output += f"  {i}. {row['Customer']}: {row['Name'][:25]}\n"
                output += f"     Revenue: {rev:,.0f} ({pct:.1f}%)\n"

            output += f"\n  Top customer concentration: {concentration:.1f}%\n"
            if concentration > 50:
                output += "  WARNING: High customer concentration risk!\n"

        return output

    @mcp.tool()
    @audit_tool_call("analyze_inventory_health")
    async def analyze_inventory_health() -> str:
        """Analyze inventory health including turnover, aging, and problem areas.

        Identifies:
        - Slow-moving inventory (low turnover)
        - Overstocked items (high days of supply)
        - Obsolete stock concerns
        - Product class performance

        Returns:
            Inventory health analysis report.
        """
        db = get_company_db()

        turnover_sql = """
        SELECT
            i.ProductClass,
            COUNT(DISTINCT w.StockCode) as ItemCount,
            SUM(w.QtyOnHand * w.UnitCost) as InventoryValue,
            (SELECT COALESCE(SUM(ABS(m.TrnValue)), 0)
             FROM InvMovements m
             JOIN InvMaster im ON m.StockCode = im.StockCode
             WHERE im.ProductClass = i.ProductClass
             AND m.TrnType IN ('I', 'S')
             AND m.EntryDate >= DATEADD(year, -1, GETDATE())) as AnnualCOGS
        FROM InvMaster i
        JOIN InvWarehouse w ON i.StockCode = w.StockCode
        WHERE w.QtyOnHand > 0
        GROUP BY i.ProductClass
        HAVING SUM(w.QtyOnHand * w.UnitCost) > 10000
        ORDER BY SUM(w.QtyOnHand * w.UnitCost) DESC
        """

        aging_sql = """
        SELECT TOP 15
            w.StockCode,
            i.Description,
            i.ProductClass,
            w.QtyOnHand,
            w.UnitCost,
            w.QtyOnHand * w.UnitCost as StockValue,
            w.DateLastSale,
            DATEDIFF(day, w.DateLastSale, GETDATE()) as DaysSinceLastSale
        FROM InvWarehouse w
        JOIN InvMaster i ON w.StockCode = i.StockCode
        WHERE w.QtyOnHand > 0
          AND w.DateLastSale < DATEADD(month, -6, GETDATE())
          AND w.UnitCost > 0
        ORDER BY w.QtyOnHand * w.UnitCost DESC
        """

        try:
            turnover_results = db.execute_query(turnover_sql, max_rows=20)
            aging_results = db.execute_query(aging_sql, max_rows=15)
        except Exception as e:
            return f"Failed to analyze inventory health: {e}"

        output = "\nINVENTORY HEALTH ANALYSIS\n"
        output += "=" * 70 + "\n"

        # Turnover by product class
        output += "\nTURNOVER BY PRODUCT CLASS\n"
        output += "-" * 70 + "\n"
        output += f"{'Class':<15} {'Items':>6} {'Value':>14} {'Turnover':>10} {'Days Supply':>12}\n"
        output += "-" * 70 + "\n"

        problem_classes = []
        for row in turnover_results or []:
            inv_val = float(row.get("InventoryValue", 0) or 0)
            cogs = float(row.get("AnnualCOGS", 0) or 0)
            turnover = cogs / inv_val if inv_val > 0 else 0
            days = (inv_val / cogs * 365) if cogs > 0 else 999

            status = ""
            if days > 180:
                status = " <-- SLOW"
                problem_classes.append(row.get("ProductClass", ""))

            output += f"{row.get('ProductClass', '')[:14]:<15} "
            output += f"{row.get('ItemCount', 0):>6} "
            output += f"{inv_val:>14,.0f} "
            output += f"{turnover:>10.1f}x "
            output += f"{days:>10.0f}d{status}\n"

        # Aging stock
        output += "\nSLOW-MOVING ITEMS (No sale in 6+ months)\n"
        output += "-" * 70 + "\n"
        total_aging_value = 0
        for row in aging_results or []:
            val = float(row.get("StockValue", 0) or 0)
            total_aging_value += val
            days = row.get("DaysSinceLastSale", 0)
            output += f"  {row.get('StockCode', '')[:25]:<25} "
            output += f"{val:>12,.0f}  "
            output += f"{days:>4}d  "
            output += f"{row.get('ProductClass', '')}\n"

        output += f"\n  Total slow-moving value: {total_aging_value:,.0f}\n"

        # Recommendations
        output += "\nRECOMMENDATIONS\n"
        output += "-" * 70 + "\n"
        if problem_classes:
            output += f"  Review stocking levels for: {', '.join(problem_classes[:5])}\n"
        if total_aging_value > 100000:
            output += f"  Consider write-down or clearance for {total_aging_value:,.0f} in aging stock\n"

        return output

    @mcp.tool()
    @audit_tool_call("analyze_product_profitability")
    async def analyze_product_profitability(months: int = 12) -> str:
        """Analyze product profitability by class using inventory costs.

        Since sales order line costs are often not populated, this uses
        inventory warehouse costs to estimate margins.

        Args:
            months: Number of months to analyze (default 12).

        Returns:
            Product profitability analysis by product class.
        """
        db = get_company_db()

        sql = f"""
        SELECT
            i.ProductClass,
            COUNT(DISTINCT d.SalesOrder) as OrderCount,
            SUM(d.MOrderQty) as QtySold,
            SUM(d.MOrderQty * d.MPrice) as Revenue,
            SUM(d.MOrderQty * COALESCE(w.UnitCost, 0)) as EstimatedCost,
            SUM(d.MOrderQty * d.MPrice) - SUM(d.MOrderQty * COALESCE(w.UnitCost, 0)) as GrossProfit
        FROM SorDetail d
        JOIN SorMaster m ON d.SalesOrder = m.SalesOrder
        JOIN InvMaster i ON d.MStockCode = i.StockCode
        LEFT JOIN InvWarehouse w ON d.MStockCode = w.StockCode AND d.MWarehouse = w.Warehouse
        WHERE m.OrderDate >= DATEADD(month, -{months}, GETDATE())
        GROUP BY i.ProductClass
        HAVING SUM(d.MOrderQty * d.MPrice) > 10000
        ORDER BY SUM(d.MOrderQty * d.MPrice) DESC
        """

        try:
            results = db.execute_query(sql, max_rows=25)
        except Exception as e:
            return f"Failed to analyze profitability: {e}"

        if not results:
            return "No sales data available for profitability analysis."

        output = f"\nPRODUCT PROFITABILITY ANALYSIS ({months} months)\n"
        output += "=" * 80 + "\n"
        output += "(Using inventory costs - SO line costs not reliably populated)\n\n"

        output += f"{'Product Class':<15} {'Orders':>7} {'Revenue':>14} {'Est.Cost':>14} {'Margin':>10} {'%':>8}\n"
        output += "-" * 80 + "\n"

        total_rev = 0
        total_cost = 0
        concerns = []

        for row in results:
            rev = float(row.get("Revenue", 0) or 0)
            cost = float(row.get("EstimatedCost", 0) or 0)
            profit = float(row.get("GrossProfit", 0) or 0)
            margin_pct = (profit / rev * 100) if rev > 0 else 0

            total_rev += rev
            total_cost += cost

            status = ""
            if margin_pct < 20:
                status = " LOW"
                concerns.append(row.get("ProductClass", ""))
            elif margin_pct < 0:
                status = " LOSS"

            output += f"{row.get('ProductClass', '')[:14]:<15} "
            output += f"{row.get('OrderCount', 0):>7} "
            output += f"{rev:>14,.0f} "
            output += f"{cost:>14,.0f} "
            output += f"{profit:>10,.0f} "
            output += f"{margin_pct:>7.1f}%{status}\n"

        output += "-" * 80 + "\n"
        total_profit = total_rev - total_cost
        total_margin = (total_profit / total_rev * 100) if total_rev > 0 else 0
        output += f"{'TOTAL':<15} {'':<7} {total_rev:>14,.0f} {total_cost:>14,.0f} {total_profit:>10,.0f} {total_margin:>7.1f}%\n"

        if concerns:
            output += f"\nMARGIN CONCERNS: {', '.join(concerns[:5])}\n"
            output += "Review pricing strategy for low-margin product classes.\n"

        return output

    @mcp.tool()
    @audit_tool_call("get_data_quality_report")
    async def get_data_quality_report() -> str:
        """Generate a data quality report for the SYSPRO database.

        Identifies common data quality issues that can affect reporting:
        - Missing costs on sales orders
        - Stale open POs
        - Job cost variances
        - Missing master data

        Returns:
            Data quality assessment report.
        """
        db = get_company_db()

        issues = []

        # Check SO cost population
        so_sql = """
        SELECT
            COUNT(*) as TotalLines,
            SUM(CASE WHEN MUnitCost > 0 THEN 1 ELSE 0 END) as LinesWithCost
        FROM SorDetail d
        JOIN SorMaster m ON d.SalesOrder = m.SalesOrder
        WHERE m.OrderDate >= DATEADD(year, -1, GETDATE())
        """

        # Check stale POs
        po_sql = """
        SELECT
            COUNT(DISTINCT PurchaseOrder) as StalePOs,
            MIN(OrderEntryDate) as OldestPO
        FROM PorMasterHdr
        WHERE OrderStatus NOT IN ('9', '/')
          AND OrderEntryDate < DATEADD(month, -6, GETDATE())
        """

        # Check job variances
        job_sql = """
        SELECT
            COUNT(*) as JobsWithVariance,
            AVG(ABS((ExpMaterial + ExpLabour) -
                    (MatCostToDate1 + MatCostToDate2 + MatCostToDate3 +
                     LabCostToDate1 + LabCostToDate2 + LabCostToDate3))) as AvgVariance
        FROM WipMaster
        WHERE Complete = 'Y'
          AND JobStartDate >= DATEADD(year, -1, GETDATE())
          AND (ExpMaterial + ExpLabour) > 0
          AND ABS((ExpMaterial + ExpLabour) -
                  (MatCostToDate1 + MatCostToDate2 + MatCostToDate3 +
                   LabCostToDate1 + LabCostToDate2 + LabCostToDate3)) >
              (ExpMaterial + ExpLabour) * 0.2
        """

        try:
            so_result = db.execute_query(so_sql, max_rows=1)
            po_result = db.execute_query(po_sql, max_rows=1)
            job_result = db.execute_query(job_sql, max_rows=1)
        except Exception as e:
            return f"Failed to generate data quality report: {e}"

        output = "\nDATA QUALITY REPORT\n"
        output += "=" * 60 + "\n\n"

        # SO costs
        if so_result:
            total = int(so_result[0].get("TotalLines", 0) or 0)
            with_cost = int(so_result[0].get("LinesWithCost", 0) or 0)
            pct = (with_cost / total * 100) if total > 0 else 0

            output += "SALES ORDER LINE COSTS\n"
            output += "-" * 60 + "\n"
            output += f"  Total lines (12mo):    {total:,}\n"
            output += f"  Lines with cost:       {with_cost:,} ({pct:.1f}%)\n"
            output += f"  Lines missing cost:    {total - with_cost:,}\n"

            if pct < 50:
                output += "  STATUS: CRITICAL - Most SO lines missing cost data\n"
                output += "  IMPACT: Cannot calculate accurate margins from sales orders\n"
                output += "  RECOMMENDATION: Use inventory costs for margin analysis\n"
            output += "\n"

        # Stale POs
        if po_result:
            stale = int(po_result[0].get("StalePOs", 0) or 0)
            oldest = po_result[0].get("OldestPO", "N/A")

            output += "STALE PURCHASE ORDERS\n"
            output += "-" * 60 + "\n"
            output += f"  Open POs older than 6 months: {stale:,}\n"
            output += f"  Oldest open PO:               {oldest}\n"

            if stale > 100:
                output += "  STATUS: WARNING - Many stale POs need cleanup\n"
                output += "  RECOMMENDATION: Review and close or cancel old POs\n"
            output += "\n"

        # Job variances
        if job_result:
            jobs = int(job_result[0].get("JobsWithVariance", 0) or 0)
            avg_var = float(job_result[0].get("AvgVariance", 0) or 0)

            output += "JOB COST VARIANCES (>20% variance)\n"
            output += "-" * 60 + "\n"
            output += f"  Jobs with significant variance: {jobs:,}\n"
            output += f"  Average variance amount:        {avg_var:,.0f}\n"

            if jobs > 50:
                output += "  STATUS: WARNING - Many jobs with cost overruns\n"
                output += "  RECOMMENDATION: Review job estimation accuracy\n"
            output += "\n"

        output += "OVERALL ASSESSMENT\n"
        output += "-" * 60 + "\n"
        output += "  Use inventory costs (not SO line costs) for margin analysis\n"
        output += "  Run periodic PO cleanup to close stale orders\n"
        output += "  Review job costing standards vs actuals\n"

        return output
