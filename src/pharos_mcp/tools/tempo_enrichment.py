"""
Cross-database Tempo-SYSPRO enrichment tools for Pharos MCP.

Combines Tempo MRP data with SYSPRO master data to provide enriched reporting.
Since databases are on different servers, queries each separately and merges
results in Python.
"""

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..core.audit import audit_tool_call
from ..core.database import get_database_registry

logger = logging.getLogger(__name__)


def get_tempo_db():
    """Get the Tempo database connection."""
    return get_database_registry().get_connection("tempo")


def get_syspro_db():
    """Get the SYSPRO company database connection."""
    return get_database_registry().get_connection("syspro_company")


def batch_query(
    db, sql_template: str, keys: list, batch_size: int = 100
) -> list[dict[str, Any]]:
    """Query in batches to avoid SQL IN clause limits.

    Args:
        db: Database connection.
        sql_template: SQL with {placeholders} to replace with parameter markers.
        keys: List of keys to query for.
        batch_size: Maximum keys per batch.

    Returns:
        Combined results from all batches.
    """
    if not keys:
        return []

    results = []
    for i in range(0, len(keys), batch_size):
        batch = keys[i : i + batch_size]
        placeholders = ",".join(["%s"] * len(batch))
        sql = sql_template.replace("{placeholders}", placeholders)
        results.extend(db.execute_query(sql, tuple(batch)))
    return results


def register_tempo_enrichment_tools(mcp: FastMCP) -> None:
    """Register Tempo-SYSPRO enrichment tools with the MCP server."""

    @mcp.tool()
    @audit_tool_call("enrich_tempo_shortages")
    async def enrich_tempo_shortages(company_id: str, horizon_days: int = 30) -> str:
        """Enhance Tempo shortage analysis with SYSPRO supplier data.

        Queries Tempo for items with shortages, then enriches with SYSPRO data:
        - Supplier contact info (name, phone, email)
        - Supplier on-hold status (alerts for items with on-hold suppliers)
        - Alternate suppliers available
        - Last purchase price from supplier history

        Args:
            company_id: Tempo company identifier (e.g., 'TTM', 'TTML', 'IV').
            horizon_days: Days to look ahead for shortages (default 30).

        Returns:
            Enriched shortage report with supplier details and recommendations.
        """
        tempo_db = get_tempo_db()
        syspro_db = get_syspro_db()

        # Step 1: Get shortage items from Tempo
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
            SELECT stock_code, description_1, lead_time,
                   ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY stock_code) as rn
            FROM master.Items
            WHERE company_id = %s
        )
        SELECT TOP 50
            d.stock_code,
            i.description_1 as Description,
            i.lead_time as LeadTime,
            d.TotalDemand,
            COALESCE(s.TotalSupply, 0) as TotalSupply,
            COALESCE(s.TotalSupply, 0) - d.TotalDemand as Shortage
        FROM DemandByItem d
        LEFT JOIN SupplyByItem s ON d.stock_code = s.stock_code
        JOIN ItemInfo i ON d.stock_code = i.stock_code AND i.rn = 1
        WHERE COALESCE(s.TotalSupply, 0) < d.TotalDemand
        ORDER BY (COALESCE(s.TotalSupply, 0) - d.TotalDemand)
        """

        try:
            shortage_result = tempo_db.execute_query(
                shortage_sql,
                (
                    company_id,
                    company_id,
                    horizon_days,
                    company_id,
                    horizon_days,
                    company_id,
                ),
                max_rows=50,
            )
        except Exception as e:
            return f"Failed to get Tempo shortages: {e}"

        if not shortage_result:
            return f"No shortages found for {company_id} in the next {horizon_days} days."

        # Extract unique stock codes
        stock_codes = list(
            set(
                row.get("stock_code", "")
                for row in shortage_result
                if row.get("stock_code")
            )
        )

        # Step 2: Get primary suppliers from SYSPRO InvMaster
        item_suppliers = {}
        if stock_codes:
            inv_sql = """
            SELECT StockCode, Supplier
            FROM InvMaster
            WHERE StockCode IN ({placeholders})
            """
            try:
                inv_rows = batch_query(syspro_db, inv_sql, stock_codes)
                for row in inv_rows:
                    stock = row["StockCode"].strip()
                    item_suppliers[stock] = (row.get("Supplier") or "").strip()
            except Exception as e:
                logger.warning(f"Failed to get SYSPRO item suppliers: {e}")

        # Get unique suppliers
        suppliers = list(set(s for s in item_suppliers.values() if s))

        # Step 3: Get supplier contact info
        supplier_info = {}
        if suppliers:
            supplier_sql = """
            SELECT
                Supplier,
                SupplierName,
                Telephone,
                Email,
                Contact,
                OnHold,
                TermsCode
            FROM ApSupplier
            WHERE Supplier IN ({placeholders})
            """
            try:
                supplier_rows = batch_query(syspro_db, supplier_sql, suppliers)
                for row in supplier_rows:
                    supplier_info[row["Supplier"].strip()] = row
            except Exception as e:
                logger.warning(f"Failed to get SYSPRO supplier data: {e}")

        # Step 4: Get alternate suppliers from SYSPRO
        alt_suppliers = {}
        if stock_codes:
            alt_sql = """
            SELECT
                a.StockCode,
                a.Supplier,
                s.SupplierName
            FROM InvAltSupplier a
            LEFT JOIN ApSupplier s ON a.Supplier = s.Supplier
            WHERE a.StockCode IN ({placeholders})
            """
            try:
                alt_rows = batch_query(syspro_db, alt_sql, stock_codes)
                for row in alt_rows:
                    stock = row["StockCode"].strip()
                    if stock not in alt_suppliers:
                        alt_suppliers[stock] = []
                    alt_suppliers[stock].append(
                        {
                            "supplier": row["Supplier"].strip(),
                            "name": (row.get("SupplierName") or "").strip(),
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to get alternate suppliers: {e}")

        # Step 5: Get last purchase prices from SYSPRO
        last_prices = {}
        if stock_codes:
            price_sql = """
            SELECT
                StockCode,
                Supplier,
                LastPricePaid,
                LastReceiptDate
            FROM PorSupStkInfo
            WHERE StockCode IN ({placeholders})
              AND LastPricePaid > 0
            """
            try:
                price_rows = batch_query(syspro_db, price_sql, stock_codes)
                for row in price_rows:
                    stock = row["StockCode"].strip()
                    if stock not in last_prices:
                        last_prices[stock] = []
                    last_prices[stock].append(
                        {
                            "supplier": row["Supplier"].strip(),
                            "price": float(row.get("LastPricePaid", 0) or 0),
                            "date": row.get("LastReceiptDate"),
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to get last prices: {e}")

        # Build output
        output = f"\nENRICHED SHORTAGE ANALYSIS - {company_id}\n"
        output += f"Horizon: {horizon_days} days\n"
        output += "=" * 85 + "\n"

        # Summary
        on_hold_items = []
        items_with_alts = []

        output += "\nSHORTAGE SUMMARY WITH SUPPLIER CONTACTS\n"
        output += "-" * 85 + "\n"
        output += f"{'Stock Code':<20} {'Shortage':>10} {'Supplier':<15} {'Contact':<20} {'Phone':<15}\n"
        output += "-" * 85 + "\n"

        for row in shortage_result:
            stock = row.get("stock_code", "")
            shortage = float(row.get("Shortage", 0) or 0)
            supplier_code = item_suppliers.get(stock, "")

            # Get supplier info
            sup_info = supplier_info.get(supplier_code, {})
            sup_name = (sup_info.get("SupplierName") or supplier_code or "N/A")[:14]
            contact = (sup_info.get("Contact") or "N/A")[:19]
            phone = (sup_info.get("Telephone") or "N/A")[:14]
            on_hold = sup_info.get("OnHold", "N")

            if on_hold == "Y":
                on_hold_items.append((stock, supplier_code, sup_name))

            if stock in alt_suppliers:
                items_with_alts.append((stock, alt_suppliers[stock]))

            output += f"{stock[:19]:<20} {shortage:>10,.0f} {sup_name:<15} {contact:<20} {phone:<15}\n"

        # On-hold suppliers alert
        if on_hold_items:
            output += "\nALERT: ITEMS WITH ON-HOLD SUPPLIERS\n"
            output += "-" * 85 + "\n"
            for stock, sup_code, sup_name in on_hold_items:
                output += f"  {stock[:30]:<32} Supplier: {sup_code} ({sup_name}) is ON HOLD\n"
            output += "\n  ACTION: Contact alternate suppliers or resolve hold status\n"

        # Items with alternate suppliers
        if items_with_alts:
            output += "\nITEMS WITH ALTERNATE SUPPLIERS AVAILABLE\n"
            output += "-" * 85 + "\n"
            for stock, alts in items_with_alts[:15]:
                alt_list = ", ".join(f"{a['supplier']}" for a in alts[:3])
                output += f"  {stock[:30]:<32} Alternates: {alt_list}\n"
            if len(items_with_alts) > 15:
                output += f"  ... and {len(items_with_alts) - 15} more items with alternates\n"

        # Items with price history
        items_with_prices = [s for s in stock_codes if s in last_prices]
        if items_with_prices:
            output += "\nRECENT PURCHASE PRICES (for reference)\n"
            output += "-" * 85 + "\n"
            output += f"{'Stock Code':<25} {'Supplier':<15} {'Last Price':>12} {'Last Receipt':<12}\n"
            output += "-" * 85 + "\n"
            shown = 0
            for stock in items_with_prices[:10]:
                for price_info in last_prices[stock][:2]:
                    date_str = (
                        str(price_info["date"])[:10] if price_info["date"] else "N/A"
                    )
                    output += f"  {stock[:24]:<25} {price_info['supplier']:<15} {price_info['price']:>12,.2f} {date_str:<12}\n"
                    shown += 1
                    if shown >= 15:
                        break
                if shown >= 15:
                    break

        # Recommendations
        output += "\nRECOMMENDATIONS\n"
        output += "-" * 85 + "\n"
        if on_hold_items:
            output += f"  1. URGENT: {len(on_hold_items)} items have on-hold suppliers - find alternates\n"
        if items_with_alts:
            output += f"  2. {len(items_with_alts)} items have alternate suppliers - consider splitting orders\n"
        output += "  3. Contact suppliers for expedite options on critical shortages\n"
        output += "  4. Review MRP suggestions for planned order recommendations\n"

        return output

    @mcp.tool()
    @audit_tool_call("enrich_tempo_supply")
    async def enrich_tempo_supply(
        company_id: str, stock_code: str | None = None
    ) -> str:
        """Enhance Tempo supply records with full SYSPRO supplier details.

        Shows open supply (POs, jobs, transfers) from Tempo enriched with:
        - Full supplier details from SYSPRO
        - Supplier payment terms
        - Open PO count per supplier

        Args:
            company_id: Tempo company identifier (e.g., 'TTM', 'TTML', 'IV').
            stock_code: Optional stock code to filter (shows all if not specified).

        Returns:
            Enriched supply listing with supplier details.
        """
        tempo_db = get_tempo_db()
        syspro_db = get_syspro_db()

        # Step 1: Get supply records from Tempo
        if stock_code:
            supply_sql = """
            SELECT TOP 50
                s.stock_code,
                s.supply_type,
                s.order_number,
                s.supplier,
                s.due_date,
                s.quantity,
                s.quantity_available,
                i.description_1 as Description
            FROM mrp.Supply s
            LEFT JOIN (
                SELECT stock_code, description_1,
                       ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY stock_code) as rn
                FROM master.Items WHERE company_id = %s
            ) i ON s.stock_code = i.stock_code AND i.rn = 1
            WHERE s.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
              AND s.company_id = %s
              AND s.stock_code = %s
            ORDER BY s.due_date
            """
            params = (company_id, company_id, company_id, stock_code)
        else:
            supply_sql = """
            SELECT TOP 100
                s.stock_code,
                s.supply_type,
                s.order_number,
                s.supplier,
                s.due_date,
                s.quantity,
                s.quantity_available,
                i.description_1 as Description
            FROM mrp.Supply s
            LEFT JOIN (
                SELECT stock_code, description_1,
                       ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY stock_code) as rn
                FROM master.Items WHERE company_id = %s
            ) i ON s.stock_code = i.stock_code AND i.rn = 1
            WHERE s.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
              AND s.company_id = %s
            ORDER BY s.due_date
            """
            params = (company_id, company_id, company_id)

        try:
            supply_result = tempo_db.execute_query(supply_sql, params, max_rows=100)
        except Exception as e:
            return f"Failed to get Tempo supply data: {e}"

        if not supply_result:
            filter_msg = f" for {stock_code}" if stock_code else ""
            return f"No supply records found for {company_id}{filter_msg}."

        # Extract unique suppliers
        suppliers = list(
            set(
                row.get("supplier", "")
                for row in supply_result
                if row.get("supplier")
            )
        )

        # Step 2: Get SYSPRO supplier details
        supplier_info = {}
        if suppliers:
            supplier_sql = """
            SELECT
                Supplier,
                SupplierName,
                Telephone,
                Email,
                Contact,
                OnHold,
                TermsCode,
                Currency
            FROM ApSupplier
            WHERE Supplier IN ({placeholders})
            """
            try:
                supplier_rows = batch_query(syspro_db, supplier_sql, suppliers)
                for row in supplier_rows:
                    supplier_info[row["Supplier"].strip()] = row
            except Exception as e:
                logger.warning(f"Failed to get SYSPRO supplier data: {e}")

        # Step 3: Get open PO counts per supplier
        po_counts = {}
        if suppliers:
            po_sql = """
            SELECT
                Supplier,
                COUNT(*) as OpenPOs
            FROM PorMasterHdr
            WHERE Supplier IN ({placeholders})
              AND OrderStatus IN ('1', '2', '3')
              AND CancelledFlag != 'Y'
            GROUP BY Supplier
            """
            try:
                po_rows = batch_query(syspro_db, po_sql, suppliers)
                for row in po_rows:
                    po_counts[row["Supplier"].strip()] = int(row.get("OpenPOs", 0) or 0)
            except Exception as e:
                logger.warning(f"Failed to get PO counts: {e}")

        # Build output
        title = f"ENRICHED SUPPLY RECORDS - {company_id}"
        if stock_code:
            title += f" ({stock_code})"
        output = f"\n{title}\n"
        output += "=" * 90 + "\n"

        # Group by supplier
        supply_by_supplier: dict[str, list] = {}
        for row in supply_result:
            sup = (row.get("supplier") or "Unknown").strip()
            if sup not in supply_by_supplier:
                supply_by_supplier[sup] = []
            supply_by_supplier[sup].append(row)

        for supplier_code, supply_items in supply_by_supplier.items():
            sup_data = supplier_info.get(supplier_code, {})
            sup_name = (sup_data.get("SupplierName") or "Unknown")[:30]
            phone = sup_data.get("Telephone") or "N/A"
            email = sup_data.get("Email") or "N/A"
            terms = sup_data.get("TermsCode") or "N/A"
            on_hold = "YES" if sup_data.get("OnHold") == "Y" else "No"
            open_pos = po_counts.get(supplier_code, 0)

            output += f"\nSUPPLIER: {supplier_code} - {sup_name}\n"
            output += "-" * 90 + "\n"
            output += f"  Contact: {sup_data.get('Contact') or 'N/A':<30} Phone: {phone}\n"
            output += f"  Email: {email[:50]}\n"
            output += f"  Terms: {terms:<10} On Hold: {on_hold:<5} Open POs in SYSPRO: {open_pos}\n"
            output += "\n"
            output += f"  {'Stock Code':<25} {'Type':<8} {'Order #':<15} {'Due Date':<12} {'Qty':>10} {'Avail':>10}\n"
            output += "  " + "-" * 86 + "\n"

            for item in supply_items:
                stock = (item.get("stock_code") or "")[:24]
                stype = (item.get("supply_type") or "")[:7]
                order = (item.get("order_number") or "")[:14]
                due = str(item.get("due_date", ""))[:10] if item.get("due_date") else "N/A"
                qty = float(item.get("quantity", 0) or 0)
                avail = float(item.get("quantity_available") or item.get("quantity", 0) or 0)

                output += f"  {stock:<25} {stype:<8} {order:<15} {due:<12} {qty:>10,.0f} {avail:>10,.0f}\n"

        # Summary
        output += "\nSUMMARY\n"
        output += "-" * 90 + "\n"
        output += f"  Total Supply Records: {len(supply_result)}\n"
        output += f"  Unique Suppliers: {len(supply_by_supplier)}\n"

        on_hold_suppliers = [
            s for s in suppliers if supplier_info.get(s, {}).get("OnHold") == "Y"
        ]
        if on_hold_suppliers:
            output += f"\n  WARNING: {len(on_hold_suppliers)} supplier(s) are on hold: {', '.join(on_hold_suppliers)}\n"

        return output

    @mcp.tool()
    @audit_tool_call("compare_inventory_sync")
    async def compare_inventory_sync(company_id: str) -> str:
        """Compare Tempo and SYSPRO inventory data for sync issues.

        Data quality tool that identifies:
        - Items in Tempo but not in SYSPRO (orphaned)
        - Items in SYSPRO but not in Tempo (not synced)
        - Lead time discrepancies between systems
        - Safety stock setting differences

        Args:
            company_id: Tempo company identifier (e.g., 'TTM', 'TTML', 'IV').

        Returns:
            Data sync comparison report with discrepancies.
        """
        tempo_db = get_tempo_db()
        syspro_db = get_syspro_db()

        # Step 1: Get Tempo item master data
        tempo_sql = """
        SELECT DISTINCT
            stock_code,
            description_1,
            lead_time,
            safety_stock
        FROM master.Items
        WHERE company_id = %s
        """

        try:
            tempo_items = tempo_db.execute_query(tempo_sql, (company_id,), max_rows=5000)
        except Exception as e:
            return f"Failed to get Tempo items: {e}"

        if not tempo_items:
            return f"No items found in Tempo for company {company_id}."

        tempo_stock_codes = [row["stock_code"].strip() for row in tempo_items]
        tempo_by_code = {row["stock_code"].strip(): row for row in tempo_items}

        # Step 2: Get SYSPRO item master data
        syspro_sql = """
        SELECT
            StockCode,
            Description,
            LeadTime,
            Supplier
        FROM InvMaster
        WHERE StockCode IN ({placeholders})
        """

        syspro_items = {}
        try:
            syspro_rows = batch_query(syspro_db, syspro_sql, tempo_stock_codes)
            for row in syspro_rows:
                syspro_items[row["StockCode"].strip()] = row
        except Exception as e:
            return f"Failed to get SYSPRO items: {e}"

        # Step 3: Get SYSPRO warehouse safety stock
        safety_sql = """
        SELECT
            StockCode,
            SUM(SafetyStockQty) as SafetyStock
        FROM InvWarehouse
        WHERE StockCode IN ({placeholders})
        GROUP BY StockCode
        """

        syspro_safety = {}
        try:
            safety_rows = batch_query(syspro_db, safety_sql, tempo_stock_codes)
            for row in safety_rows:
                syspro_safety[row["StockCode"].strip()] = float(
                    row.get("SafetyStock", 0) or 0
                )
        except Exception as e:
            logger.warning(f"Failed to get SYSPRO safety stock: {e}")

        # Step 4: Analyze discrepancies
        in_tempo_not_syspro = []
        in_syspro_not_tempo = []
        lead_time_mismatches = []
        safety_stock_mismatches = []

        for stock_code in tempo_stock_codes:
            tempo_data = tempo_by_code.get(stock_code, {})
            syspro_data = syspro_items.get(stock_code)

            if not syspro_data:
                in_tempo_not_syspro.append(
                    {
                        "stock_code": stock_code,
                        "description": tempo_data.get("description_1", ""),
                    }
                )
                continue

            # Compare lead times
            tempo_lt = int(tempo_data.get("lead_time", 0) or 0)
            syspro_lt = int(syspro_data.get("LeadTime", 0) or 0)
            if tempo_lt != syspro_lt and (tempo_lt > 0 or syspro_lt > 0):
                lead_time_mismatches.append(
                    {
                        "stock_code": stock_code,
                        "tempo_lt": tempo_lt,
                        "syspro_lt": syspro_lt,
                        "diff": tempo_lt - syspro_lt,
                    }
                )

            # Compare safety stock
            tempo_ss = float(tempo_data.get("safety_stock", 0) or 0)
            syspro_ss = syspro_safety.get(stock_code, 0)
            if abs(tempo_ss - syspro_ss) > 0.01 and (tempo_ss > 0 or syspro_ss > 0):
                safety_stock_mismatches.append(
                    {
                        "stock_code": stock_code,
                        "tempo_ss": tempo_ss,
                        "syspro_ss": syspro_ss,
                    }
                )

        # Build output
        output = f"\nINVENTORY SYNC COMPARISON - {company_id}\n"
        output += "=" * 80 + "\n"

        # Summary
        output += "\nSUMMARY\n"
        output += "-" * 80 + "\n"
        output += f"  Items in Tempo:                {len(tempo_items):,}\n"
        output += f"  Items found in SYSPRO:         {len(syspro_items):,}\n"
        output += f"  Items in Tempo only:           {len(in_tempo_not_syspro):,}\n"
        output += f"  Lead time mismatches:          {len(lead_time_mismatches):,}\n"
        output += f"  Safety stock mismatches:       {len(safety_stock_mismatches):,}\n"

        # Items in Tempo but not SYSPRO
        if in_tempo_not_syspro:
            output += "\nITEMS IN TEMPO BUT NOT SYSPRO (may need master data sync)\n"
            output += "-" * 80 + "\n"
            output += f"{'Stock Code':<30} {'Description':<45}\n"
            output += "-" * 80 + "\n"
            for item in in_tempo_not_syspro[:20]:
                output += f"{item['stock_code'][:29]:<30} {item['description'][:44]:<45}\n"
            if len(in_tempo_not_syspro) > 20:
                output += f"  ... and {len(in_tempo_not_syspro) - 20} more items\n"

        # Lead time mismatches
        if lead_time_mismatches:
            output += "\nLEAD TIME DISCREPANCIES\n"
            output += "-" * 80 + "\n"
            output += f"{'Stock Code':<30} {'Tempo LT':>10} {'SYSPRO LT':>12} {'Diff':>10}\n"
            output += "-" * 80 + "\n"
            # Sort by absolute difference
            lead_time_mismatches.sort(key=lambda x: abs(x["diff"]), reverse=True)
            for item in lead_time_mismatches[:20]:
                output += f"{item['stock_code'][:29]:<30} {item['tempo_lt']:>10} {item['syspro_lt']:>12} {item['diff']:>+10}\n"
            if len(lead_time_mismatches) > 20:
                output += f"  ... and {len(lead_time_mismatches) - 20} more discrepancies\n"

        # Safety stock mismatches
        if safety_stock_mismatches:
            output += "\nSAFETY STOCK DISCREPANCIES\n"
            output += "-" * 80 + "\n"
            output += f"{'Stock Code':<30} {'Tempo SS':>12} {'SYSPRO SS':>12}\n"
            output += "-" * 80 + "\n"
            for item in safety_stock_mismatches[:20]:
                output += f"{item['stock_code'][:29]:<30} {item['tempo_ss']:>12,.0f} {item['syspro_ss']:>12,.0f}\n"
            if len(safety_stock_mismatches) > 20:
                output += f"  ... and {len(safety_stock_mismatches) - 20} more discrepancies\n"

        # Recommendations
        output += "\nRECOMMENDATIONS\n"
        output += "-" * 80 + "\n"
        if in_tempo_not_syspro:
            output += f"  1. Review {len(in_tempo_not_syspro)} items in Tempo that don't exist in SYSPRO\n"
            output += "     - May be obsolete items or sync failures\n"
        if lead_time_mismatches:
            output += f"  2. {len(lead_time_mismatches)} items have lead time differences\n"
            output += "     - Sync master data or update planning parameters\n"
        if safety_stock_mismatches:
            output += f"  3. {len(safety_stock_mismatches)} items have safety stock differences\n"
            output += "     - Determine which system is source of truth\n"
        if not any([in_tempo_not_syspro, lead_time_mismatches, safety_stock_mismatches]):
            output += "  Data is well synchronized between systems.\n"

        return output

    @mcp.tool()
    @audit_tool_call("get_supplier_scorecard")
    async def get_supplier_scorecard(
        company_id: str, supplier: str | None = None
    ) -> str:
        """Generate unified supplier scorecard combining Tempo and SYSPRO data.

        Combines:
        - Tempo: Lead time metrics, supply performance
        - SYSPRO: Master data, open POs, purchase history

        Args:
            company_id: Tempo company identifier (e.g., 'TTM', 'TTML', 'IV').
            supplier: Optional specific supplier code (shows top suppliers if not specified).

        Returns:
            Supplier scorecard with performance metrics.
        """
        tempo_db = get_tempo_db()
        syspro_db = get_syspro_db()

        # Step 1: Get suppliers with supply from Tempo
        if supplier:
            supply_sql = """
            SELECT
                supplier,
                COUNT(*) as SupplyCount,
                SUM(quantity) as TotalQty,
                COUNT(DISTINCT stock_code) as UniqueItems
            FROM mrp.Supply
            WHERE run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
              AND company_id = %s
              AND supplier = %s
            GROUP BY supplier
            """
            params = (company_id, company_id, supplier)
        else:
            supply_sql = """
            SELECT TOP 20
                supplier,
                COUNT(*) as SupplyCount,
                SUM(quantity) as TotalQty,
                COUNT(DISTINCT stock_code) as UniqueItems
            FROM mrp.Supply
            WHERE run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
              AND company_id = %s
              AND supplier IS NOT NULL
              AND supplier != ''
            GROUP BY supplier
            ORDER BY COUNT(*) DESC
            """
            params = (company_id, company_id)

        try:
            supply_result = tempo_db.execute_query(supply_sql, params, max_rows=20)
        except Exception as e:
            return f"Failed to get Tempo supply data: {e}"

        if not supply_result:
            filter_msg = f" for supplier {supplier}" if supplier else ""
            return f"No supply records found in Tempo for {company_id}{filter_msg}."

        supplier_codes = [
            row.get("supplier", "").strip()
            for row in supply_result
            if row.get("supplier")
        ]

        # Step 2: Get lead time metrics from Tempo LeadTimeDetail (if available)
        lt_metrics = {}
        if supplier_codes:
            # Aggregate from LeadTimeDetail which has supplier_code
            lt_sql = """
            SELECT
                d.supplier_code as supplier,
                AVG(CAST(d.calculated_lead_time_days AS FLOAT)) as AvgLT,
                STDEV(CAST(d.calculated_lead_time_days AS FLOAT)) /
                    NULLIF(AVG(CAST(d.calculated_lead_time_days AS FLOAT)), 0) * 100 as AvgVariability,
                COUNT(*) as TotalSamples
            FROM analytics.LeadTimeDetail d
            JOIN analytics.LeadTimeMetrics m ON d.lead_time_id = m.lead_time_id
            WHERE m.company_id = %s
              AND d.supplier_code IN ({placeholders})
              AND d.is_outlier = 0
            GROUP BY d.supplier_code
            """
            try:
                # Build query with proper placeholders
                placeholders = ",".join(["%s"] * len(supplier_codes))
                lt_query = lt_sql.replace("{placeholders}", placeholders)
                lt_params = (company_id,) + tuple(supplier_codes)
                lt_rows = tempo_db.execute_query(lt_query, lt_params, max_rows=50)
                for row in lt_rows:
                    sup = (row.get("supplier") or "").strip()
                    lt_metrics[sup] = row
            except Exception as e:
                logger.warning(f"Failed to get lead time metrics: {e}")

        # Step 3: Get SYSPRO supplier master data
        supplier_info = {}
        if supplier_codes:
            sup_sql = """
            SELECT
                Supplier,
                SupplierName,
                Telephone,
                Email,
                Contact,
                OnHold,
                TermsCode,
                Currency,
                CurrentBalance,
                LastPurchDate
            FROM ApSupplier
            WHERE Supplier IN ({placeholders})
            """
            try:
                sup_rows = batch_query(syspro_db, sup_sql, supplier_codes)
                for row in sup_rows:
                    supplier_info[row["Supplier"].strip()] = row
            except Exception as e:
                logger.warning(f"Failed to get SYSPRO supplier data: {e}")

        # Step 4: Get open PO count and value from SYSPRO
        po_stats = {}
        if supplier_codes:
            po_sql = """
            SELECT
                h.Supplier,
                COUNT(*) as OpenPOs,
                SUM(d.MOrderQty * d.MPrice) as POValue
            FROM PorMasterHdr h
            LEFT JOIN PorMasterDetail d ON h.PurchaseOrder = d.PurchaseOrder
            WHERE h.Supplier IN ({placeholders})
              AND h.OrderStatus IN ('1', '2', '3')
              AND h.CancelledFlag != 'Y'
            GROUP BY h.Supplier
            """
            try:
                po_rows = batch_query(syspro_db, po_sql, supplier_codes)
                for row in po_rows:
                    po_stats[row["Supplier"].strip()] = {
                        "open_pos": int(row.get("OpenPOs", 0) or 0),
                        "po_value": float(row.get("POValue", 0) or 0),
                    }
            except Exception as e:
                logger.warning(f"Failed to get PO stats: {e}")

        # Build output
        title = "SUPPLIER SCORECARD"
        if supplier:
            title += f" - {supplier}"
        output = f"\n{title} ({company_id})\n"
        output += "=" * 90 + "\n"

        for supply_row in supply_result:
            sup_code = (supply_row.get("supplier") or "").strip()
            if not sup_code:
                continue

            sup_data = supplier_info.get(sup_code, {})
            lt_data = lt_metrics.get(sup_code, {})
            po_data = po_stats.get(sup_code, {})

            sup_name = (sup_data.get("SupplierName") or "Unknown")[:35]
            on_hold = "YES" if sup_data.get("OnHold") == "Y" else "No"

            output += f"\n{'─' * 90}\n"
            output += f"SUPPLIER: {sup_code} - {sup_name}\n"
            output += f"{'─' * 90}\n"

            # Contact Info
            output += "\nCONTACT INFORMATION\n"
            output += f"  Contact:    {sup_data.get('Contact') or 'N/A'}\n"
            output += f"  Phone:      {sup_data.get('Telephone') or 'N/A'}\n"
            output += f"  Email:      {sup_data.get('Email') or 'N/A'}\n"
            output += f"  Currency:   {sup_data.get('Currency') or 'N/A'}\n"
            output += f"  Terms:      {sup_data.get('TermsCode') or 'N/A'}\n"
            output += f"  On Hold:    {on_hold}\n"

            # Activity from Tempo
            output += "\nCURRENT ACTIVITY (from Tempo MRP)\n"
            output += f"  Open Supply Lines:   {int(supply_row.get('SupplyCount', 0) or 0):,}\n"
            output += f"  Total Quantity:      {float(supply_row.get('TotalQty', 0) or 0):,.0f}\n"
            output += f"  Unique Items:        {int(supply_row.get('UniqueItems', 0) or 0):,}\n"

            # Lead Time Performance from Tempo
            if lt_data:
                output += "\nLEAD TIME PERFORMANCE (from Tempo)\n"
                avg_lt = float(lt_data.get("AvgLT", 0) or 0)
                variability = float(lt_data.get("AvgVariability", 0) or 0)
                samples = int(lt_data.get("TotalSamples", 0) or 0)
                output += f"  Avg Lead Time:       {avg_lt:.1f} days\n"
                output += f"  Variability:         {variability:.1f}%\n"
                output += f"  Sample Count:        {samples:,}\n"

                if variability > 50:
                    output += "  STATUS: HIGH VARIABILITY - Consider safety stock buffers\n"
                elif variability > 25:
                    output += "  STATUS: MODERATE VARIABILITY\n"
                else:
                    output += "  STATUS: RELIABLE\n"

            # SYSPRO Activity
            output += "\nSYSPRO ACTIVITY\n"
            output += f"  Open POs:            {po_data.get('open_pos', 0):,}\n"
            output += f"  Open PO Value:       {po_data.get('po_value', 0):,.2f}\n"
            output += f"  Current Balance:     {float(sup_data.get('CurrentBalance', 0) or 0):,.2f}\n"
            last_purch = sup_data.get("LastPurchDate")
            output += f"  Last Purchase:       {str(last_purch)[:10] if last_purch else 'N/A'}\n"

            # Status flags
            if sup_data.get("OnHold") == "Y":
                output += "\n  WARNING: Supplier is ON HOLD in SYSPRO\n"

        # Overall summary
        output += f"\n{'=' * 90}\n"
        output += "SUMMARY\n"
        output += f"  Suppliers analyzed: {len(supply_result)}\n"

        on_hold_count = sum(
            1
            for s in supplier_codes
            if supplier_info.get(s, {}).get("OnHold") == "Y"
        )
        if on_hold_count:
            output += f"  Suppliers on hold: {on_hold_count}\n"

        high_var_count = sum(
            1
            for s in supplier_codes
            if float(lt_metrics.get(s, {}).get("AvgVariability", 0) or 0) > 50
        )
        if high_var_count:
            output += f"  High variability suppliers: {high_var_count}\n"

        return output

    @mcp.tool()
    @audit_tool_call("analyze_forecast_vs_sales")
    async def analyze_forecast_vs_sales(
        company_id: str, months: int = 12, product_class: str | None = None
    ) -> str:
        """Compare Tempo forecasts against actual SYSPRO sales history.

        Cross-database analysis that:
        - Gets Tempo forecast data by item and period
        - Gets actual sales from SYSPRO SorDetail for the same periods
        - Calculates forecast accuracy metrics (MAPE, bias)
        - Identifies worst performers by variance

        Args:
            company_id: Tempo company identifier (e.g., 'TTM', 'TTML', 'IV').
            months: Number of months of history to analyze (default 12).
            product_class: Optional product class filter.

        Returns:
            Forecast accuracy analysis comparing Tempo to SYSPRO actuals.
        """
        tempo_db = get_tempo_db()
        syspro_db = get_syspro_db()

        # Step 1: Get Tempo forecast results with history
        # ForecastResults uses item_code, not stock_code
        forecast_sql = """
        SELECT
            f.item_code as stock_code,
            i.description_1 as Description,
            i.part_category as ProductClass,
            YEAR(f.period_date) as Year,
            MONTH(f.period_date) as Month,
            SUM(f.forecast_value) as ForecastQty
        FROM forecast.ForecastResults f
        JOIN master.Items i ON f.company_id = i.company_id AND f.item_code = i.stock_code
        WHERE f.company_id = %s
          AND f.period_date >= DATEADD(month, -%s, GETDATE())
          AND f.period_date < GETDATE()
        """ + (" AND i.part_category = %s" if product_class else "") + """
        GROUP BY f.item_code, i.description_1, i.part_category,
                 YEAR(f.period_date), MONTH(f.period_date)
        ORDER BY f.item_code, YEAR(f.period_date), MONTH(f.period_date)
        """

        try:
            forecast_params = (company_id, months)
            if product_class:
                forecast_params += (product_class,)
            forecast_result = tempo_db.execute_query(
                forecast_sql, forecast_params, max_rows=5000
            )
        except Exception as e:
            return f"Failed to get Tempo forecasts: {e}"

        if not forecast_result:
            return f"No forecast data found for {company_id} in the last {months} months."

        # Get unique stock codes
        stock_codes = list(set(row.get("stock_code", "") for row in forecast_result))

        # Step 2: Get SYSPRO actual sales for the same period and items
        # Sales are from SorDetail, aggregated by month
        sales_sql = """
        SELECT
            d.MStockCode as StockCode,
            YEAR(h.OrderDate) as Year,
            MONTH(h.OrderDate) as Month,
            SUM(d.MOrderQty) as ActualQty,
            SUM(d.MShipQty) as ShippedQty
        FROM SorDetail d
        JOIN SorMaster h ON d.SalesOrder = h.SalesOrder
        WHERE d.MStockCode IN ({placeholders})
          AND h.OrderDate >= DATEADD(month, -%s, GETDATE())
          AND h.OrderDate < GETDATE()
          AND h.OrderStatus NOT IN ('/', '\\')
        GROUP BY d.MStockCode, YEAR(h.OrderDate), MONTH(h.OrderDate)
        """

        sales_by_key: dict[tuple, dict] = {}
        try:
            # Build query with proper placeholders
            if stock_codes:
                placeholders = ",".join(["%s"] * len(stock_codes))
                sales_query = sales_sql.replace("{placeholders}", placeholders)
                sales_params = tuple(stock_codes) + (months,)
                sales_rows = syspro_db.execute_query(sales_query, sales_params, max_rows=10000)
                for row in sales_rows:
                    key = (
                        row.get("StockCode", "").strip(),
                        int(row.get("Year", 0) or 0),
                        int(row.get("Month", 0) or 0),
                    )
                    sales_by_key[key] = {
                        "actual": float(row.get("ActualQty", 0) or 0),
                        "shipped": float(row.get("ShippedQty", 0) or 0),
                    }
        except Exception as e:
            logger.warning(f"Failed to get SYSPRO sales: {e}")

        # Step 3: Calculate accuracy metrics
        item_metrics: dict[str, dict] = {}
        period_metrics: dict[tuple, dict] = {}

        for row in forecast_result:
            stock_code = row.get("stock_code", "").strip()
            year = int(row.get("Year", 0) or 0)
            month = int(row.get("Month", 0) or 0)
            forecast = float(row.get("ForecastQty", 0) or 0)

            key = (stock_code, year, month)
            actual_data = sales_by_key.get(key, {})
            actual = actual_data.get("actual", 0)

            # Calculate variance
            variance = actual - forecast
            abs_error = abs(variance)
            pct_error = (abs_error / forecast * 100) if forecast > 0 else (100 if actual > 0 else 0)

            # Accumulate by item
            if stock_code not in item_metrics:
                item_metrics[stock_code] = {
                    "description": row.get("Description", ""),
                    "product_class": row.get("ProductClass", ""),
                    "total_forecast": 0,
                    "total_actual": 0,
                    "total_abs_error": 0,
                    "periods": 0,
                }
            item_metrics[stock_code]["total_forecast"] += forecast
            item_metrics[stock_code]["total_actual"] += actual
            item_metrics[stock_code]["total_abs_error"] += abs_error
            item_metrics[stock_code]["periods"] += 1

            # Accumulate by period
            period_key = (year, month)
            if period_key not in period_metrics:
                period_metrics[period_key] = {
                    "total_forecast": 0,
                    "total_actual": 0,
                    "total_abs_error": 0,
                    "items": 0,
                }
            period_metrics[period_key]["total_forecast"] += forecast
            period_metrics[period_key]["total_actual"] += actual
            period_metrics[period_key]["total_abs_error"] += abs_error
            period_metrics[period_key]["items"] += 1

        # Calculate MAPE for each item
        for stock_code, metrics in item_metrics.items():
            if metrics["total_forecast"] > 0:
                metrics["mape"] = (
                    metrics["total_abs_error"] / metrics["total_forecast"] * 100
                )
            else:
                metrics["mape"] = 100 if metrics["total_actual"] > 0 else 0
            metrics["bias"] = metrics["total_actual"] - metrics["total_forecast"]
            metrics["bias_pct"] = (
                (metrics["bias"] / metrics["total_forecast"] * 100)
                if metrics["total_forecast"] > 0
                else 0
            )

        # Build output
        output = f"\nFORECAST VS ACTUAL SALES ANALYSIS - {company_id}\n"
        output += f"Period: Last {months} months\n"
        if product_class:
            output += f"Product Class: {product_class}\n"
        output += "=" * 90 + "\n"

        # Overall summary
        total_forecast = sum(m["total_forecast"] for m in item_metrics.values())
        total_actual = sum(m["total_actual"] for m in item_metrics.values())
        total_abs_error = sum(m["total_abs_error"] for m in item_metrics.values())
        overall_mape = (total_abs_error / total_forecast * 100) if total_forecast > 0 else 0
        overall_bias = total_actual - total_forecast
        overall_bias_pct = (overall_bias / total_forecast * 100) if total_forecast > 0 else 0

        output += "\nOVERALL SUMMARY\n"
        output += "-" * 90 + "\n"
        output += f"  Items with forecasts:      {len(item_metrics):,}\n"
        output += f"  Items with SYSPRO sales:   {len(set(k[0] for k in sales_by_key)):,}\n"
        output += f"  Total Forecast Qty:        {total_forecast:,.0f}\n"
        output += f"  Total Actual Sales:        {total_actual:,.0f}\n"
        output += f"  Overall MAPE:              {overall_mape:.1f}%\n"
        output += f"  Overall Bias:              {overall_bias:+,.0f} ({overall_bias_pct:+.1f}%)\n"

        if overall_bias > 0:
            output += "\n  INSIGHT: Actual sales exceeded forecast (under-forecasting)\n"
        elif overall_bias < 0:
            output += "\n  INSIGHT: Forecast exceeded actual sales (over-forecasting)\n"

        # Accuracy by period
        output += "\nACCURACY BY MONTH\n"
        output += "-" * 90 + "\n"
        output += f"{'Period':<10} {'Forecast':>12} {'Actual':>12} {'Variance':>12} {'MAPE':>8}\n"
        output += "-" * 90 + "\n"

        sorted_periods = sorted(period_metrics.keys())
        for period_key in sorted_periods:
            pm = period_metrics[period_key]
            period_str = f"{period_key[0]}-{period_key[1]:02d}"
            variance = pm["total_actual"] - pm["total_forecast"]
            mape = (pm["total_abs_error"] / pm["total_forecast"] * 100) if pm["total_forecast"] > 0 else 0
            output += f"{period_str:<10} {pm['total_forecast']:>12,.0f} {pm['total_actual']:>12,.0f} {variance:>+12,.0f} {mape:>7.1f}%\n"

        # Worst performers (highest MAPE)
        output += "\nWORST PERFORMERS (Highest MAPE)\n"
        output += "-" * 90 + "\n"
        output += f"{'Stock Code':<22} {'MAPE':>8} {'Forecast':>12} {'Actual':>12} {'Bias':>12}\n"
        output += "-" * 90 + "\n"

        worst_items = sorted(
            item_metrics.items(),
            key=lambda x: x[1]["mape"],
            reverse=True
        )[:20]

        for stock_code, metrics in worst_items:
            if metrics["total_forecast"] == 0 and metrics["total_actual"] == 0:
                continue
            output += f"{stock_code[:21]:<22} {metrics['mape']:>7.1f}% {metrics['total_forecast']:>12,.0f} {metrics['total_actual']:>12,.0f} {metrics['bias']:>+12,.0f}\n"

        # Best performers (lowest MAPE with significant volume)
        output += "\nBEST PERFORMERS (Lowest MAPE, min 100 units forecast)\n"
        output += "-" * 90 + "\n"
        output += f"{'Stock Code':<22} {'MAPE':>8} {'Forecast':>12} {'Actual':>12} {'Bias':>12}\n"
        output += "-" * 90 + "\n"

        best_items = sorted(
            [(k, v) for k, v in item_metrics.items() if v["total_forecast"] >= 100],
            key=lambda x: x[1]["mape"]
        )[:10]

        for stock_code, metrics in best_items:
            output += f"{stock_code[:21]:<22} {metrics['mape']:>7.1f}% {metrics['total_forecast']:>12,.0f} {metrics['total_actual']:>12,.0f} {metrics['bias']:>+12,.0f}\n"

        # Recommendations
        output += "\nRECOMMENDATIONS\n"
        output += "-" * 90 + "\n"

        high_mape_count = sum(1 for m in item_metrics.values() if m["mape"] > 50)
        if high_mape_count > 0:
            output += f"  1. {high_mape_count} items have MAPE > 50% - review forecast methods\n"

        if overall_bias_pct > 10:
            output += f"  2. Systematic under-forecasting ({overall_bias_pct:.0f}% bias) - consider adjusting\n"
        elif overall_bias_pct < -10:
            output += f"  2. Systematic over-forecasting ({abs(overall_bias_pct):.0f}% bias) - consider adjusting\n"

        no_sales_items = [k for k, v in item_metrics.items() if v["total_actual"] == 0 and v["total_forecast"] > 0]
        if no_sales_items:
            output += f"  3. {len(no_sales_items)} items have forecasts but no SYSPRO sales - verify data sync\n"

        return output

    @mcp.tool()
    @audit_tool_call("get_job_demand_comparison")
    async def get_job_demand_comparison(
        company_id: str, warehouse: str | None = None
    ) -> str:
        """Compare SYSPRO job material requirements with Tempo MRP demands.

        Cross-database analysis showing:
        - Open SYSPRO jobs and their material requirements (WipJobAllMat)
        - Corresponding demands in Tempo for the same items
        - Items where job demand differs from or is missing in Tempo
        - Helps identify sync issues between systems

        Args:
            company_id: Tempo company identifier (e.g., 'TTM', 'TTML', 'IV').
            warehouse: Optional warehouse filter.

        Returns:
            Comparison of SYSPRO job demands vs Tempo MRP demands.
        """
        tempo_db = get_tempo_db()
        syspro_db = get_syspro_db()

        # Step 1: Get open jobs from SYSPRO
        jobs_sql = """
        SELECT
            j.Job,
            j.JobDescription,
            j.StockCode as ParentItem,
            j.QtyToMake,
            j.QtyManufactured,
            j.JobStartDate,
            j.Complete,
            j.Warehouse
        FROM WipMaster j
        WHERE j.Complete != 'Y'
          AND j.QtyToMake > j.QtyManufactured
        """ + (" AND j.Warehouse = %s" if warehouse else "") + """
        ORDER BY j.JobStartDate
        """

        try:
            job_params = (warehouse,) if warehouse else ()
            jobs_result = syspro_db.execute_query(jobs_sql, job_params, max_rows=200)
        except Exception as e:
            return f"Failed to get SYSPRO jobs: {e}"

        if not jobs_result:
            wh_msg = f" in warehouse {warehouse}" if warehouse else ""
            return f"No open jobs found in SYSPRO{wh_msg}."

        job_numbers = [row.get("Job", "").strip() for row in jobs_result]

        # Step 2: Get job material requirements from SYSPRO
        mat_sql = """
        SELECT
            m.Job,
            m.StockCode,
            m.Warehouse,
            m.UnitQtyReqd,
            m.QtyIssued,
            (j.QtyToMake - j.QtyManufactured) * m.UnitQtyReqd as OutstandingQty,
            j.JobStartDate,
            i.Description as ItemDescription
        FROM WipJobAllMat m
        JOIN WipMaster j ON m.Job = j.Job
        LEFT JOIN InvMaster i ON m.StockCode = i.StockCode
        WHERE m.Job IN ({placeholders})
          AND m.AllocCompleted != 'Y'
        ORDER BY m.Job, m.StockCode
        """

        job_materials: dict[str, list] = {}
        all_material_codes: set[str] = set()
        try:
            placeholders = ",".join(["%s"] * len(job_numbers))
            mat_query = mat_sql.replace("{placeholders}", placeholders)
            mat_rows = syspro_db.execute_query(mat_query, tuple(job_numbers), max_rows=2000)
            for row in mat_rows:
                job = row.get("Job", "").strip()
                stock = row.get("StockCode", "").strip()
                all_material_codes.add(stock)
                if job not in job_materials:
                    job_materials[job] = []
                job_materials[job].append(row)
        except Exception as e:
            logger.warning(f"Failed to get job materials: {e}")

        # Step 3: Get Tempo demands for these material items
        tempo_demands: dict[str, dict] = {}
        if all_material_codes:
            demand_sql = """
            SELECT
                d.stock_code,
                d.warehouse,
                d.demand_type,
                SUM(d.quantity) as TotalDemand,
                COUNT(*) as DemandCount,
                MIN(d.required_date) as EarliestDate
            FROM mrp.Demands d
            WHERE d.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
              AND d.company_id = %s
              AND d.stock_code IN ({placeholders})
            """ + (" AND d.warehouse = %s" if warehouse else "") + """
            GROUP BY d.stock_code, d.warehouse, d.demand_type
            """

            try:
                placeholders = ",".join(["%s"] * len(all_material_codes))
                demand_query = demand_sql.replace("{placeholders}", placeholders)
                demand_params = (company_id, company_id) + tuple(all_material_codes)
                if warehouse:
                    demand_params += (warehouse,)
                demand_rows = tempo_db.execute_query(demand_query, demand_params, max_rows=2000)
                for row in demand_rows:
                    stock = row.get("stock_code", "").strip()
                    dtype = row.get("demand_type", "")
                    key = f"{stock}|{dtype}"
                    if stock not in tempo_demands:
                        tempo_demands[stock] = {}
                    tempo_demands[stock][dtype] = {
                        "total": float(row.get("TotalDemand", 0) or 0),
                        "count": int(row.get("DemandCount", 0) or 0),
                        "earliest": row.get("EarliestDate"),
                    }
            except Exception as e:
                logger.warning(f"Failed to get Tempo demands: {e}")

        # Step 4: Compare and analyze
        material_comparison: list[dict] = []
        for stock_code in all_material_codes:
            # Sum SYSPRO job demand for this item
            syspro_qty = 0
            syspro_jobs = 0
            for job, materials in job_materials.items():
                for mat in materials:
                    if mat.get("StockCode", "").strip() == stock_code:
                        syspro_qty += float(mat.get("OutstandingQty", 0) or 0)
                        syspro_jobs += 1

            # Sum Tempo demand for this item (job-type demands)
            tempo_job_demand = 0
            tempo_all_demand = 0
            if stock_code in tempo_demands:
                for dtype, data in tempo_demands[stock_code].items():
                    tempo_all_demand += data["total"]
                    if "JOB" in dtype.upper() or "WORK" in dtype.upper():
                        tempo_job_demand += data["total"]

            material_comparison.append({
                "stock_code": stock_code,
                "syspro_qty": syspro_qty,
                "syspro_jobs": syspro_jobs,
                "tempo_job_demand": tempo_job_demand,
                "tempo_all_demand": tempo_all_demand,
                "variance": tempo_job_demand - syspro_qty,
            })

        # Build output
        output = f"\nJOB DEMAND COMPARISON - {company_id}\n"
        if warehouse:
            output += f"Warehouse: {warehouse}\n"
        output += "=" * 95 + "\n"

        # Jobs summary
        output += "\nOPEN SYSPRO JOBS\n"
        output += "-" * 95 + "\n"
        output += f"{'Job':<15} {'Description':<30} {'Parent Item':<20} {'Qty To Make':>12}\n"
        output += "-" * 95 + "\n"

        for job in jobs_result[:20]:
            job_num = (job.get("Job") or "")[:14]
            desc = (job.get("JobDescription") or "")[:29]
            parent = (job.get("ParentItem") or "")[:19]
            qty = float(job.get("QtyToMake", 0) or 0) - float(job.get("QtyManufactured", 0) or 0)
            output += f"{job_num:<15} {desc:<30} {parent:<20} {qty:>12,.0f}\n"

        if len(jobs_result) > 20:
            output += f"... and {len(jobs_result) - 20} more jobs\n"

        output += f"\n  Total Open Jobs: {len(jobs_result)}\n"
        output += f"  Total Material Lines: {sum(len(m) for m in job_materials.values())}\n"
        output += f"  Unique Materials: {len(all_material_codes)}\n"

        # Material demand comparison
        output += "\n" + "─" * 95 + "\n"
        output += "MATERIAL DEMAND COMPARISON (SYSPRO Jobs vs Tempo)\n"
        output += "─" * 95 + "\n"
        output += f"{'Stock Code':<25} {'SYSPRO Job Qty':>15} {'Tempo Job Qty':>15} {'Tempo All Qty':>15} {'Variance':>12}\n"
        output += "-" * 95 + "\n"

        # Sort by variance (absolute)
        material_comparison.sort(key=lambda x: abs(x["variance"]), reverse=True)

        missing_in_tempo = []
        mismatched = []

        for mat in material_comparison[:30]:
            stock = mat["stock_code"][:24]
            syspro = mat["syspro_qty"]
            tempo_job = mat["tempo_job_demand"]
            tempo_all = mat["tempo_all_demand"]
            var = mat["variance"]

            status = ""
            if syspro > 0 and tempo_all == 0:
                missing_in_tempo.append(mat)
                status = " MISSING"
            elif abs(var) > syspro * 0.1 and syspro > 0:  # >10% variance
                mismatched.append(mat)
                status = " MISMATCH"

            output += f"{stock:<25} {syspro:>15,.0f} {tempo_job:>15,.0f} {tempo_all:>15,.0f} {var:>+12,.0f}{status}\n"

        if len(material_comparison) > 30:
            output += f"... and {len(material_comparison) - 30} more materials\n"

        # Issues summary
        output += "\n" + "─" * 95 + "\n"
        output += "ISSUES IDENTIFIED\n"
        output += "─" * 95 + "\n"

        if missing_in_tempo:
            output += f"\nMATERIALS IN SYSPRO JOBS BUT MISSING FROM TEMPO ({len(missing_in_tempo)} items)\n"
            output += "-" * 95 + "\n"
            for mat in missing_in_tempo[:10]:
                output += f"  {mat['stock_code']:<30} SYSPRO Qty: {mat['syspro_qty']:,.0f}\n"
            if len(missing_in_tempo) > 10:
                output += f"  ... and {len(missing_in_tempo) - 10} more\n"

        if mismatched:
            output += f"\nMATERIALS WITH QUANTITY MISMATCHES ({len(mismatched)} items)\n"
            output += "-" * 95 + "\n"
            for mat in mismatched[:10]:
                output += f"  {mat['stock_code']:<30} SYSPRO: {mat['syspro_qty']:,.0f} | Tempo: {mat['tempo_all_demand']:,.0f}\n"
            if len(mismatched) > 10:
                output += f"  ... and {len(mismatched) - 10} more\n"

        # Recommendations
        output += "\nRECOMMENDATIONS\n"
        output += "-" * 95 + "\n"

        if missing_in_tempo:
            output += f"  1. {len(missing_in_tempo)} materials from SYSPRO jobs are missing in Tempo\n"
            output += "     - Check if MRP data sync is running\n"
            output += "     - Verify job-to-demand mapping in Tempo configuration\n"

        if mismatched:
            output += f"  2. {len(mismatched)} materials have quantity differences > 10%\n"
            output += "     - May indicate timing differences between extracts\n"
            output += "     - Review job quantities in both systems\n"

        if not missing_in_tempo and not mismatched:
            output += "  Job demands appear to be well synchronized between systems.\n"

        return output
