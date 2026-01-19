"""
Financial reporting tools for Pharos MCP.

Provides dynamic income statement and financial analysis that adapts to
the client's actual GL structure, rather than assuming hardcoded patterns.
"""

from mcp.server.fastmcp import FastMCP

from ..core.audit import audit_tool_call
from ..core.database import get_company_db
from .base import format_table_results


def register_financial_tools(mcp: FastMCP) -> None:
    """Register financial reporting tools with the MCP server."""

    @mcp.tool()
    @audit_tool_call("discover_gl_structure")
    async def discover_gl_structure(year: int | None = None) -> str:
        """Discover the GL group structure used for income statement accounts.

        Analyzes the actual GL groups that have activity to help understand
        how the chart of accounts is structured. Different SYSPRO implementations
        use different GL group numbering schemes.

        Args:
            year: Optional fiscal year to analyze (defaults to most recent).

        Returns:
            GL group structure with descriptions and account types.
        """
        db = get_company_db()

        # First, find the most recent year if not specified
        if year is None:
            year_sql = "SELECT MAX(GlYear) FROM GenHistory WHERE GlYear > 0"
            try:
                max_year = db.execute_scalar(year_sql)
                year = int(max_year) if max_year else 2025
            except Exception:
                year = 2025

        # Query GL groups that have actual P&L activity
        sql = f"""
        SELECT DISTINCT
            m.GlGroup,
            COALESCE(gg.Description, '(No description)') as GroupDescription,
            m.AccountType,
            CASE m.AccountType
                WHEN 'R' THEN 'Revenue'
                WHEN 'E' THEN 'Expense'
                WHEN 'A' THEN 'Asset'
                WHEN 'L' THEN 'Liability'
                WHEN 'C' THEN 'Capital/Equity'
                ELSE 'Other'
            END as AccountTypeDesc,
            COUNT(*) as AccountCount,
            SUM(CASE WHEN h.ClosingBalPer12 <> 0 THEN 1 ELSE 0 END) as ActiveAccounts
        FROM GenHistory h
        INNER JOIN GenMaster m ON h.GlCode = m.GlCode AND h.Company = m.Company
        LEFT JOIN GenGroups gg ON m.GlGroup = gg.GlGroup AND m.Company = gg.Company
        WHERE h.GlYear = {year}
        GROUP BY m.GlGroup, gg.Description, m.AccountType
        HAVING SUM(ABS(h.ClosingBalPer12)) > 0
        ORDER BY m.GlGroup
        """

        try:
            results = db.execute_query(sql, max_rows=100)
        except Exception as e:
            return f"Failed to discover GL structure: {e}"

        if not results:
            return f"No GL activity found for year {year}."

        output = f"GL Group Structure for Year {year}\n"
        output += "=" * 50 + "\n\n"

        # Group by account type
        revenue_groups = []
        expense_groups = []
        other_groups = []

        for row in results:
            gl_group = row.get("GlGroup", "").strip()
            desc = row.get("GroupDescription", "")
            acc_type = row.get("AccountType", "")
            active = row.get("ActiveAccounts", 0)

            entry = f"  {gl_group}: {desc} ({active} active accounts)"

            if acc_type == "R":
                revenue_groups.append(entry)
            elif acc_type == "E":
                expense_groups.append(entry)
            else:
                other_groups.append(f"  {gl_group}: {desc} [{acc_type}]")

        if revenue_groups:
            output += "REVENUE GROUPS (AccountType=R):\n"
            output += "\n".join(revenue_groups) + "\n\n"

        if expense_groups:
            output += "EXPENSE GROUPS (AccountType=E):\n"
            output += "\n".join(expense_groups) + "\n\n"

        if other_groups:
            output += "OTHER GROUPS (Balance Sheet):\n"
            output += "\n".join(other_groups) + "\n\n"

        output += "Note: Use these GL groups when building custom financial reports.\n"
        output += "The generate_income_statement tool will auto-detect this structure."

        return output

    @mcp.tool()
    @audit_tool_call("generate_income_statement")
    async def generate_income_statement(
        year: int | None = None,
        include_quarters: bool = False,
        detailed: bool = False,
    ) -> str:
        """Generate an income statement that adapts to the client's GL structure.

        Automatically detects the GL group patterns used for revenue, cost of sales,
        and expenses rather than assuming a fixed structure.

        Args:
            year: Fiscal year (defaults to most recent with data).
            include_quarters: Include quarterly breakdown if True.
            detailed: Show individual GL groups if True, summary only if False.

        Returns:
            Formatted income statement with calculated totals.
        """
        db = get_company_db()

        # Find the year to use
        if year is None:
            year_sql = "SELECT MAX(GlYear) FROM GenHistory WHERE GlYear > 0"
            try:
                max_year = db.execute_scalar(year_sql)
                year = int(max_year) if max_year else 2025
            except Exception:
                year = 2025

        # First, discover what GL groups exist and categorize them
        # We look for groups with GenGroups descriptions containing key terms
        # OR we categorize by AccountType (R=Revenue, E=Expense)
        category_sql = f"""
        WITH GLActivity AS (
            SELECT
                m.GlGroup,
                COALESCE(gg.Description, '') as GroupDescription,
                m.AccountType,
                SUM(h.ClosingBalPer12) as YTDBalance,
                SUM(h.ClosingBalPer3) as Q1Balance,
                SUM(h.ClosingBalPer6) as Q2Balance,
                SUM(h.ClosingBalPer9) as Q3Balance,
                SUM(h.ClosingBalPer12) as Q4Balance
            FROM GenHistory h
            INNER JOIN GenMaster m ON h.GlCode = m.GlCode AND h.Company = m.Company
            LEFT JOIN GenGroups gg ON m.GlGroup = gg.GlGroup AND m.Company = gg.Company
            WHERE h.GlYear = {year}
              AND m.AccountType IN ('R', 'E')
            GROUP BY m.GlGroup, gg.Description, m.AccountType
            HAVING SUM(ABS(h.ClosingBalPer12)) > 0
        )
        SELECT
            GlGroup,
            GroupDescription,
            AccountType,
            CASE
                WHEN UPPER(GroupDescription) LIKE '%SALES%' AND UPPER(GroupDescription) NOT LIKE '%COST%' THEN 'REVENUE'
                WHEN UPPER(GroupDescription) LIKE '%REVENUE%' THEN 'REVENUE'
                WHEN UPPER(GroupDescription) LIKE '%INCOME%' AND UPPER(GroupDescription) NOT LIKE '%EXPENSE%' THEN 'OTHER_INCOME'
                WHEN UPPER(GroupDescription) LIKE '%COS%' THEN 'COST_OF_SALES'
                WHEN UPPER(GroupDescription) LIKE '%COGS%' THEN 'COST_OF_SALES'
                WHEN UPPER(GroupDescription) LIKE '%COST OF GOODS%' THEN 'COST_OF_SALES'
                WHEN UPPER(GroupDescription) LIKE '%COST OF SALES%' THEN 'COST_OF_SALES'
                WHEN UPPER(GroupDescription) LIKE '%VARIANCE%' THEN 'COST_OF_SALES'
                WHEN UPPER(GroupDescription) LIKE '%OPEX%' THEN 'OPERATING_EXPENSES'
                WHEN UPPER(GroupDescription) LIKE '%EXPENSE%' THEN 'OPERATING_EXPENSES'
                WHEN UPPER(GroupDescription) LIKE '%TAX%' THEN 'TAXATION'
                WHEN AccountType = 'R' THEN 'REVENUE'
                WHEN AccountType = 'E' THEN 'OPERATING_EXPENSES'
                ELSE 'OTHER'
            END as Category,
            YTDBalance,
            Q1Balance,
            Q2Balance - Q1Balance as Q2Movement,
            Q3Balance - Q2Balance as Q3Movement,
            Q4Balance - Q3Balance as Q4Movement
        FROM GLActivity
        ORDER BY Category, GlGroup
        """

        try:
            results = db.execute_query(category_sql, max_rows=200)
        except Exception as e:
            return f"Failed to generate income statement: {e}"

        if not results:
            return f"No income statement data found for year {year}."

        # Aggregate by category
        categories = {
            "REVENUE": {"groups": [], "total": 0, "q1": 0, "q2": 0, "q3": 0, "q4": 0},
            "OTHER_INCOME": {"groups": [], "total": 0, "q1": 0, "q2": 0, "q3": 0, "q4": 0},
            "COST_OF_SALES": {"groups": [], "total": 0, "q1": 0, "q2": 0, "q3": 0, "q4": 0},
            "OPERATING_EXPENSES": {"groups": [], "total": 0, "q1": 0, "q2": 0, "q3": 0, "q4": 0},
            "TAXATION": {"groups": [], "total": 0, "q1": 0, "q2": 0, "q3": 0, "q4": 0},
        }

        for row in results:
            cat = row.get("Category", "OTHER")
            if cat not in categories:
                cat = "OPERATING_EXPENSES"

            ytd = float(row.get("YTDBalance", 0) or 0)
            q1 = float(row.get("Q1Balance", 0) or 0)
            q2 = float(row.get("Q2Movement", 0) or 0)
            q3 = float(row.get("Q3Movement", 0) or 0)
            q4 = float(row.get("Q4Movement", 0) or 0)

            # Revenue/Income accounts typically have credit balances (negative in SYSPRO)
            if cat in ("REVENUE", "OTHER_INCOME"):
                ytd = -ytd
                q1 = -q1
                q2 = -q2
                q3 = -q3
                q4 = -q4

            categories[cat]["groups"].append({
                "group": row.get("GlGroup", ""),
                "description": row.get("GroupDescription", ""),
                "amount": ytd,
                "q1": q1, "q2": q2, "q3": q3, "q4": q4,
            })
            categories[cat]["total"] += ytd
            categories[cat]["q1"] += q1
            categories[cat]["q2"] += q2
            categories[cat]["q3"] += q3
            categories[cat]["q4"] += q4

        # Build output
        output = f"\nINCOME STATEMENT - Year {year}\n"
        output += "=" * 60 + "\n"

        def fmt_num(n):
            """Format number with thousands separator."""
            if n >= 0:
                return f"{n:,.2f}"
            return f"({abs(n):,.2f})"

        def fmt_row(label, amount, q1=None, q2=None, q3=None, q4=None, bold=False):
            """Format a row with optional quarterly columns."""
            prefix = "**" if bold else "  "
            if include_quarters and q1 is not None:
                return f"{prefix}{label:<30} {fmt_num(q1):>14} {fmt_num(q2):>14} {fmt_num(q3):>14} {fmt_num(q4):>14} {fmt_num(amount):>16}"
            return f"{prefix}{label:<40} {fmt_num(amount):>18}"

        if include_quarters:
            output += f"\n{'':32} {'Q1':>14} {'Q2':>14} {'Q3':>14} {'Q4':>14} {'YTD':>16}\n"
            output += "-" * 106 + "\n"
        else:
            output += "\n"

        # Revenue
        rev = categories["REVENUE"]
        if detailed and rev["groups"]:
            output += "\nREVENUE\n"
            for g in rev["groups"]:
                output += fmt_row(f"  {g['description'][:28]}", g["amount"],
                                  g["q1"], g["q2"], g["q3"], g["q4"]) + "\n"
        output += fmt_row("Revenue", rev["total"], rev["q1"], rev["q2"], rev["q3"], rev["q4"], bold=True) + "\n"

        # Cost of Sales
        cos = categories["COST_OF_SALES"]
        if detailed and cos["groups"]:
            output += "\nCOST OF SALES\n"
            for g in cos["groups"]:
                output += fmt_row(f"  {g['description'][:28]}", g["amount"],
                                  g["q1"], g["q2"], g["q3"], g["q4"]) + "\n"
        output += fmt_row("Cost of Sales", cos["total"], cos["q1"], cos["q2"], cos["q3"], cos["q4"]) + "\n"

        # Gross Profit
        gross_profit = rev["total"] - cos["total"]
        gp_q1 = rev["q1"] - cos["q1"]
        gp_q2 = rev["q2"] - cos["q2"]
        gp_q3 = rev["q3"] - cos["q3"]
        gp_q4 = rev["q4"] - cos["q4"]
        output += "-" * (106 if include_quarters else 60) + "\n"
        output += fmt_row("GROSS PROFIT", gross_profit, gp_q1, gp_q2, gp_q3, gp_q4, bold=True) + "\n"

        # Other Income
        other = categories["OTHER_INCOME"]
        if other["total"] != 0:
            if detailed and other["groups"]:
                output += "\nOTHER INCOME\n"
                for g in other["groups"]:
                    output += fmt_row(f"  {g['description'][:28]}", g["amount"],
                                      g["q1"], g["q2"], g["q3"], g["q4"]) + "\n"
            output += fmt_row("Other Income", other["total"], other["q1"], other["q2"], other["q3"], other["q4"]) + "\n"

        # Operating Expenses
        opex = categories["OPERATING_EXPENSES"]
        if detailed and opex["groups"]:
            output += "\nOPERATING EXPENSES\n"
            for g in opex["groups"]:
                output += fmt_row(f"  {g['description'][:28]}", g["amount"],
                                  g["q1"], g["q2"], g["q3"], g["q4"]) + "\n"
        output += fmt_row("Operating Expenses", opex["total"], opex["q1"], opex["q2"], opex["q3"], opex["q4"]) + "\n"

        # Operating Profit
        op_profit = gross_profit + other["total"] - opex["total"]
        op_q1 = gp_q1 + other["q1"] - opex["q1"]
        op_q2 = gp_q2 + other["q2"] - opex["q2"]
        op_q3 = gp_q3 + other["q3"] - opex["q3"]
        op_q4 = gp_q4 + other["q4"] - opex["q4"]
        output += "-" * (106 if include_quarters else 60) + "\n"
        output += fmt_row("OPERATING PROFIT", op_profit, op_q1, op_q2, op_q3, op_q4, bold=True) + "\n"

        # Taxation
        tax = categories["TAXATION"]
        if tax["total"] != 0:
            output += fmt_row("Taxation", tax["total"], tax["q1"], tax["q2"], tax["q3"], tax["q4"]) + "\n"

        # Net Profit
        net_profit = op_profit - tax["total"]
        net_q1 = op_q1 - tax["q1"]
        net_q2 = op_q2 - tax["q2"]
        net_q3 = op_q3 - tax["q3"]
        net_q4 = op_q4 - tax["q4"]
        output += "=" * (106 if include_quarters else 60) + "\n"
        output += fmt_row("NET PROFIT", net_profit, net_q1, net_q2, net_q3, net_q4, bold=True) + "\n"

        # Margin calculations
        if rev["total"] > 0:
            gp_margin = (gross_profit / rev["total"]) * 100
            np_margin = (net_profit / rev["total"]) * 100
            output += "\n"
            output += f"Gross Profit Margin: {gp_margin:.1f}%\n"
            output += f"Net Profit Margin: {np_margin:.1f}%\n"

        return output

    @mcp.tool()
    @audit_tool_call("compare_periods")
    async def compare_periods(
        year1: int,
        year2: int,
    ) -> str:
        """Compare income statement between two fiscal years.

        Shows year-over-year changes in revenue, costs, and profitability.

        Args:
            year1: First year to compare.
            year2: Second year to compare.

        Returns:
            Comparative income statement with variance analysis.
        """
        db = get_company_db()

        sql = f"""
        WITH YearData AS (
            SELECT
                h.GlYear,
                m.AccountType,
                COALESCE(gg.Description, m.GlGroup) as Category,
                SUM(h.ClosingBalPer12) as YTDBalance
            FROM GenHistory h
            INNER JOIN GenMaster m ON h.GlCode = m.GlCode AND h.Company = m.Company
            LEFT JOIN GenGroups gg ON m.GlGroup = gg.GlGroup AND m.Company = gg.Company
            WHERE h.GlYear IN ({year1}, {year2})
              AND m.AccountType IN ('R', 'E')
            GROUP BY h.GlYear, m.AccountType, COALESCE(gg.Description, m.GlGroup)
        )
        SELECT
            Category,
            AccountType,
            SUM(CASE WHEN GlYear = {year1} THEN YTDBalance ELSE 0 END) as Year1Amount,
            SUM(CASE WHEN GlYear = {year2} THEN YTDBalance ELSE 0 END) as Year2Amount
        FROM YearData
        GROUP BY Category, AccountType
        ORDER BY AccountType, Category
        """

        try:
            results = db.execute_query(sql, max_rows=100)
        except Exception as e:
            return f"Failed to compare periods: {e}"

        if not results:
            return f"No data found for years {year1} and/or {year2}."

        output = f"\nCOMPARATIVE INCOME STATEMENT: {year1} vs {year2}\n"
        output += "=" * 80 + "\n\n"
        output += f"{'Category':<35} {year1:>12} {year2:>12} {'Variance':>12} {'%':>8}\n"
        output += "-" * 80 + "\n"

        total_rev_y1 = 0
        total_rev_y2 = 0
        total_exp_y1 = 0
        total_exp_y2 = 0

        for row in results:
            cat = row.get("Category", "")[:33]
            acc_type = row.get("AccountType", "")
            y1 = float(row.get("Year1Amount", 0) or 0)
            y2 = float(row.get("Year2Amount", 0) or 0)

            # Flip sign for revenue (credits are negative in GL)
            if acc_type == "R":
                y1 = -y1
                y2 = -y2
                total_rev_y1 += y1
                total_rev_y2 += y2
            else:
                total_exp_y1 += y1
                total_exp_y2 += y2

            variance = y2 - y1
            pct = ((y2 - y1) / y1 * 100) if y1 != 0 else 0

            output += f"{cat:<35} {y1:>12,.0f} {y2:>12,.0f} {variance:>12,.0f} {pct:>7.1f}%\n"

        output += "-" * 80 + "\n"
        rev_var = total_rev_y2 - total_rev_y1
        rev_pct = ((total_rev_y2 - total_rev_y1) / total_rev_y1 * 100) if total_rev_y1 != 0 else 0
        output += f"{'Total Revenue':<35} {total_rev_y1:>12,.0f} {total_rev_y2:>12,.0f} {rev_var:>12,.0f} {rev_pct:>7.1f}%\n"

        exp_var = total_exp_y2 - total_exp_y1
        exp_pct = ((total_exp_y2 - total_exp_y1) / total_exp_y1 * 100) if total_exp_y1 != 0 else 0
        output += f"{'Total Expenses':<35} {total_exp_y1:>12,.0f} {total_exp_y2:>12,.0f} {exp_var:>12,.0f} {exp_pct:>7.1f}%\n"

        net_y1 = total_rev_y1 - total_exp_y1
        net_y2 = total_rev_y2 - total_exp_y2
        net_var = net_y2 - net_y1
        net_pct = ((net_y2 - net_y1) / net_y1 * 100) if net_y1 != 0 else 0
        output += "=" * 80 + "\n"
        output += f"{'NET PROFIT':<35} {net_y1:>12,.0f} {net_y2:>12,.0f} {net_var:>12,.0f} {net_pct:>7.1f}%\n"

        return output
