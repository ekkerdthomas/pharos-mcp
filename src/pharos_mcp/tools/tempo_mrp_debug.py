"""
Tempo MRP debugging tools for Pharos MCP.

Provides tools to understand MRP logic, trace suggestions back to their
source demands, and compare changes between MRP runs.
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


def register_tempo_mrp_debug_tools(mcp: FastMCP) -> None:
    """Register Tempo MRP debugging tools with the MCP server."""

    @mcp.tool()
    @audit_tool_call("explain_mrp_suggestion")
    async def explain_mrp_suggestion(
        company_id: str, stock_code: str, warehouse: str | None = None
    ) -> str:
        """Explain why MRP generated suggestions for an item.

        Traces the full logic chain to answer "Why did MRP suggest this?":
        - Shows all open suggestions for the item
        - Traces back to the demands driving the need
        - Shows available supply (what's covering demand)
        - Shows pegging relationships (which supply covers which demand)
        - Calculates the shortage/surplus that triggered suggestions
        - Explains timing based on lead times

        Args:
            company_id: Tempo company identifier (e.g., 'TTM', 'TTML', 'IV').
            stock_code: Stock code to analyze.
            warehouse: Optional warehouse filter.

        Returns:
            Detailed explanation of MRP suggestion logic.
        """
        db = get_tempo_db()

        # Get latest run info
        run_sql = """
        SELECT TOP 1
            run_id,
            run_name,
            created_date,
            planning_horizon_days
        FROM mrp.Runs
        WHERE company_id = %s
        ORDER BY created_date DESC
        """

        # Get item master info
        item_sql = """
        SELECT TOP 1
            stock_code,
            description_1,
            lead_time,
            safety_stock,
            buying_rule,
            lot_sizing_rule,
            minimum_order_qty,
            maximum_qty,
            multiple_of
        FROM master.Items
        WHERE company_id = %s AND stock_code = %s
        """

        # Get suggestions for this item
        suggestion_sql = """
        SELECT
            suggestion_id,
            stock_code,
            warehouse,
            order_type,
            planned_quantity,
            required_date,
            start_date,
            due_date,
            lead_time,
            action_message,
            exception_type,
            critical_flag,
            order_status,
            order_number
        FROM mrp.Suggestions
        WHERE run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
          AND company_id = %s
          AND stock_code = %s
        """ + (" AND warehouse = %s" if warehouse else "") + """
        ORDER BY required_date
        """

        # Get demands for this item
        demand_sql = """
        SELECT
            demand_id,
            stock_code,
            warehouse,
            demand_type,
            source_type,
            required_date,
            quantity,
            order_number,
            line_number,
            customer,
            processing_status,
            allocation_status,
            within_time_fence
        FROM mrp.Demands
        WHERE run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
          AND company_id = %s
          AND stock_code = %s
        """ + (" AND warehouse = %s" if warehouse else "") + """
        ORDER BY required_date
        """

        # Get supply for this item
        supply_sql = """
        SELECT
            supply_id,
            stock_code,
            warehouse,
            supply_type,
            source_type,
            due_date,
            quantity,
            quantity_allocated,
            quantity_available,
            order_number,
            supplier,
            supply_status,
            allocation_status
        FROM mrp.Supply
        WHERE run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
          AND company_id = %s
          AND stock_code = %s
        """ + (" AND warehouse = %s" if warehouse else "") + """
        ORDER BY due_date
        """

        # Get current inventory
        inventory_sql = """
        SELECT
            warehouse,
            qty_on_hand,
            qty_available,
            qty_allocated,
            safety_stock
        FROM mrp.Inventory
        WHERE run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
          AND company_id = %s
          AND stock_code = %s
        """ + (" AND warehouse = %s" if warehouse else "")

        # Get pegging relationships
        pegging_sql = """
        SELECT
            p.pegging_id,
            p.demand_id,
            p.supply_id,
            p.pegged_quantity,
            p.demand_date,
            p.demand_quantity as demand_qty,
            p.supply_date,
            p.supply_quantity as supply_qty,
            p.pegging_type,
            d.demand_type,
            d.order_number as demand_order,
            s.supply_type,
            s.order_number as supply_order
        FROM mrp.Pegging p
        LEFT JOIN mrp.Demands d ON p.demand_id = d.demand_id AND p.run_id = d.run_id
        LEFT JOIN mrp.Supply s ON p.supply_id = s.supply_id AND p.run_id = s.run_id
        WHERE p.run_id = (SELECT MAX(run_id) FROM mrp.Runs WHERE company_id = %s)
          AND p.company_id = %s
          AND (p.supply_stock_code = %s OR p.demand_stock_code = %s)
        ORDER BY p.demand_date
        """

        try:
            run_result = db.execute_query(run_sql, (company_id,), max_rows=1)

            item_result = db.execute_query(
                item_sql, (company_id, stock_code), max_rows=1
            )

            suggestion_params = (company_id, company_id, stock_code)
            if warehouse:
                suggestion_params += (warehouse,)
            suggestion_result = db.execute_query(
                suggestion_sql, suggestion_params, max_rows=50
            )

            demand_params = (company_id, company_id, stock_code)
            if warehouse:
                demand_params += (warehouse,)
            demand_result = db.execute_query(demand_sql, demand_params, max_rows=100)

            supply_params = (company_id, company_id, stock_code)
            if warehouse:
                supply_params += (warehouse,)
            supply_result = db.execute_query(supply_sql, supply_params, max_rows=100)

            inventory_params = (company_id, company_id, stock_code)
            if warehouse:
                inventory_params += (warehouse,)
            inventory_result = db.execute_query(
                inventory_sql, inventory_params, max_rows=10
            )

            pegging_params = (company_id, company_id, stock_code, stock_code)
            pegging_result = db.execute_query(pegging_sql, pegging_params, max_rows=200)

        except Exception as e:
            return f"Failed to analyze MRP suggestion: {e}"

        # Build output
        output = f"\nMRP SUGGESTION EXPLANATION - {stock_code}\n"
        output += f"Company: {company_id}"
        if warehouse:
            output += f" | Warehouse: {warehouse}"
        output += "\n"
        output += "=" * 85 + "\n"

        # Run info
        if run_result:
            run = run_result[0]
            output += f"\nMRP Run: {run.get('run_name', 'N/A')} (ID: {run.get('run_id')})\n"
            output += f"Run Date: {run.get('created_date', 'N/A')}\n"
            output += f"Planning Horizon: {run.get('planning_horizon_days', 'N/A')} days\n"

        # Item master info
        output += "\n" + "─" * 85 + "\n"
        output += "ITEM MASTER DATA\n"
        output += "─" * 85 + "\n"
        if item_result:
            item = item_result[0]
            output += f"  Description:      {item.get('description_1', 'N/A')}\n"
            output += f"  Lead Time:        {item.get('lead_time', 0)} days\n"
            output += f"  Safety Stock:     {item.get('safety_stock', 0)}\n"
            output += f"  Buying Rule:      {item.get('buying_rule', 'N/A')}\n"
            output += f"  Lot Sizing:       {item.get('lot_sizing_rule', 'N/A')}\n"
            min_qty = item.get('minimum_order_qty', 0) or 0
            max_qty = item.get('maximum_qty', 0) or 0
            mult = item.get('multiple_of', 0) or 0
            if min_qty or max_qty or mult:
                output += f"  Order Constraints: Min={min_qty}, Max={max_qty}, Multiple={mult}\n"
        else:
            output += "  Item not found in master data!\n"

        # Current inventory
        output += "\n" + "─" * 85 + "\n"
        output += "CURRENT INVENTORY POSITION\n"
        output += "─" * 85 + "\n"
        total_on_hand = 0
        total_available = 0
        total_safety = 0
        if inventory_result:
            output += f"  {'Warehouse':<12} {'On Hand':>12} {'Available':>12} {'Allocated':>12} {'Safety':>10}\n"
            output += "  " + "-" * 58 + "\n"
            for inv in inventory_result:
                wh = inv.get('warehouse', '')[:11]
                on_hand = float(inv.get('qty_on_hand', 0) or 0)
                avail = float(inv.get('qty_available', 0) or 0)
                alloc = float(inv.get('qty_allocated', 0) or 0)
                safety = float(inv.get('safety_stock', 0) or 0)
                total_on_hand += on_hand
                total_available += avail
                total_safety += safety
                output += f"  {wh:<12} {on_hand:>12,.0f} {avail:>12,.0f} {alloc:>12,.0f} {safety:>10,.0f}\n"
            output += "  " + "-" * 58 + "\n"
            output += f"  {'TOTAL':<12} {total_on_hand:>12,.0f} {total_available:>12,.0f}\n"
        else:
            output += "  No inventory records found.\n"

        # Demands driving the need
        output += "\n" + "─" * 85 + "\n"
        output += "DEMANDS (What's driving the need)\n"
        output += "─" * 85 + "\n"
        total_demand = 0
        if demand_result:
            output += f"  {'Type':<12} {'Source':<10} {'Date':<12} {'Qty':>10} {'Order#':<15} {'Customer':<12}\n"
            output += "  " + "-" * 75 + "\n"
            for d in demand_result[:20]:
                dtype = (d.get('demand_type') or '')[:11]
                source = (d.get('source_type') or '')[:9]
                date = str(d.get('required_date', ''))[:10]
                qty = float(d.get('quantity', 0) or 0)
                total_demand += qty
                order = (d.get('order_number') or '')[:14]
                cust = (d.get('customer') or '')[:11]
                output += f"  {dtype:<12} {source:<10} {date:<12} {qty:>10,.0f} {order:<15} {cust:<12}\n"
            if len(demand_result) > 20:
                output += f"  ... and {len(demand_result) - 20} more demands\n"
            output += "  " + "-" * 75 + "\n"
            output += f"  TOTAL DEMAND: {total_demand:,.0f}\n"
        else:
            output += "  No demands found.\n"

        # Supply covering the demand
        output += "\n" + "─" * 85 + "\n"
        output += "SUPPLY (What's covering the demand)\n"
        output += "─" * 85 + "\n"
        total_supply = 0
        total_available_supply = 0
        if supply_result:
            output += f"  {'Type':<12} {'Source':<10} {'Due Date':<12} {'Qty':>10} {'Available':>10} {'Order#':<15}\n"
            output += "  " + "-" * 75 + "\n"
            for s in supply_result[:20]:
                stype = (s.get('supply_type') or '')[:11]
                source = (s.get('source_type') or '')[:9]
                date = str(s.get('due_date', ''))[:10]
                qty = float(s.get('quantity', 0) or 0)
                avail = float(s.get('quantity_available') or s.get('quantity', 0) or 0)
                total_supply += qty
                total_available_supply += avail
                order = (s.get('order_number') or '')[:14]
                output += f"  {stype:<12} {source:<10} {date:<12} {qty:>10,.0f} {avail:>10,.0f} {order:<15}\n"
            if len(supply_result) > 20:
                output += f"  ... and {len(supply_result) - 20} more supply records\n"
            output += "  " + "-" * 75 + "\n"
            output += f"  TOTAL SUPPLY: {total_supply:,.0f} (Available: {total_available_supply:,.0f})\n"
        else:
            output += "  No supply found.\n"

        # Net position calculation
        output += "\n" + "─" * 85 + "\n"
        output += "NET POSITION ANALYSIS\n"
        output += "─" * 85 + "\n"
        net_position = total_available + total_available_supply - total_demand
        output += f"  Starting Available:     {total_available:>15,.0f}\n"
        output += f"  + Incoming Supply:      {total_available_supply:>15,.0f}\n"
        output += f"  - Total Demand:         {total_demand:>15,.0f}\n"
        output += f"  = Net Position:         {net_position:>15,.0f}\n"
        if total_safety > 0:
            output += f"  - Safety Stock:         {total_safety:>15,.0f}\n"
            net_after_safety = net_position - total_safety
            output += f"  = Net After Safety:     {net_after_safety:>15,.0f}\n"
            if net_after_safety < 0:
                output += f"\n  SHORTAGE: {abs(net_after_safety):,.0f} units below safety stock level\n"
        elif net_position < 0:
            output += f"\n  SHORTAGE: {abs(net_position):,.0f} units\n"

        # Pegging details
        output += "\n" + "─" * 85 + "\n"
        output += "PEGGING (How supply is allocated to demand)\n"
        output += "─" * 85 + "\n"
        if pegging_result:
            output += f"  {'Demand Type':<12} {'Demand Date':<12} {'Supply Type':<12} {'Supply Date':<12} {'Pegged Qty':>10}\n"
            output += "  " + "-" * 62 + "\n"
            for p in pegging_result[:15]:
                dtype = (p.get('demand_type') or '')[:11]
                ddate = str(p.get('demand_date', ''))[:10]
                stype = (p.get('supply_type') or '')[:11]
                sdate = str(p.get('supply_date', ''))[:10]
                pqty = float(p.get('pegged_quantity', 0) or 0)
                output += f"  {dtype:<12} {ddate:<12} {stype:<12} {sdate:<12} {pqty:>10,.0f}\n"
            if len(pegging_result) > 15:
                output += f"  ... and {len(pegging_result) - 15} more pegging records\n"
        else:
            output += "  No pegging records found (demand may be unallocated).\n"

        # MRP Suggestions
        output += "\n" + "─" * 85 + "\n"
        output += "MRP SUGGESTIONS GENERATED\n"
        output += "─" * 85 + "\n"
        if suggestion_result:
            for s in suggestion_result:
                output += f"\n  Suggestion #{s.get('suggestion_id', 'N/A')}\n"
                output += f"  Order Type:       {s.get('order_type', 'N/A')}\n"
                output += f"  Quantity:         {float(s.get('planned_quantity', 0) or 0):,.0f}\n"
                output += f"  Required Date:    {s.get('required_date', 'N/A')}\n"
                output += f"  Start Date:       {s.get('start_date', 'N/A')}\n"
                output += f"  Due Date:         {s.get('due_date', 'N/A')}\n"
                output += f"  Lead Time Used:   {s.get('lead_time', 0)} days\n"
                output += f"  Status:           {s.get('order_status', 'N/A')}\n"
                if s.get('critical_flag'):
                    output += f"  CRITICAL:         YES\n"
                if s.get('action_message'):
                    output += f"  Action:           {s.get('action_message')}\n"
                if s.get('exception_type'):
                    output += f"  Exception:        {s.get('exception_type')}\n"
                if s.get('order_number'):
                    output += f"  Order Number:     {s.get('order_number')}\n"
        else:
            output += "  No suggestions generated for this item.\n"
            output += "\n  Reason: Supply covers demand OR item is not planned by MRP.\n"

        # Summary explanation
        output += "\n" + "─" * 85 + "\n"
        output += "EXPLANATION SUMMARY\n"
        output += "─" * 85 + "\n"
        if suggestion_result:
            shortage = max(0, total_demand - total_available - total_available_supply)
            output += f"  MRP generated {len(suggestion_result)} suggestion(s) because:\n"
            if shortage > 0:
                output += f"  - Net shortage of {shortage:,.0f} units exists\n"
            if total_safety > 0 and net_position < total_safety:
                output += f"  - Inventory would fall below safety stock ({total_safety:,.0f})\n"
            if demand_result:
                earliest = min(d.get('required_date') for d in demand_result if d.get('required_date'))
                output += f"  - Earliest demand: {str(earliest)[:10]}\n"
            if item_result:
                lt = item_result[0].get('lead_time', 0) or 0
                output += f"  - Lead time of {lt} days requires action now\n"
        else:
            output += "  No suggestions needed because supply covers all demand.\n"

        return output

    @mcp.tool()
    @audit_tool_call("compare_mrp_runs")
    async def compare_mrp_runs(
        company_id: str, run_id_1: int | None = None, run_id_2: int | None = None
    ) -> str:
        """Compare two MRP runs to see what changed.

        Shows differences between runs:
        - New suggestions (in run 2 but not run 1)
        - Removed suggestions (in run 1 but not run 2)
        - Changed suggestions (quantity, date, or status changes)
        - Summary statistics

        If run IDs not specified, compares the two most recent runs.

        Args:
            company_id: Tempo company identifier (e.g., 'TTM', 'TTML', 'IV').
            run_id_1: First (older) run ID. If None, uses second-most-recent.
            run_id_2: Second (newer) run ID. If None, uses most recent.

        Returns:
            Comparison report showing changes between MRP runs.
        """
        db = get_tempo_db()

        # Get run IDs if not specified
        if run_id_1 is None or run_id_2 is None:
            runs_sql = """
            SELECT TOP 2
                run_id,
                run_name,
                created_date,
                items_processed,
                planning_orders_created
            FROM mrp.Runs
            WHERE company_id = %s
            ORDER BY created_date DESC
            """
            try:
                runs = db.execute_query(runs_sql, (company_id,), max_rows=2)
            except Exception as e:
                return f"Failed to get MRP runs: {e}"

            if len(runs) < 2:
                return f"Need at least 2 MRP runs to compare. Found {len(runs)} for {company_id}."

            run_id_2 = runs[0].get('run_id')  # Most recent
            run_id_1 = runs[1].get('run_id')  # Previous
            run_info = runs
        else:
            # Get info for specified runs
            runs_sql = """
            SELECT
                run_id,
                run_name,
                created_date,
                items_processed,
                planning_orders_created
            FROM mrp.Runs
            WHERE company_id = %s
              AND run_id IN (%s, %s)
            ORDER BY created_date
            """
            try:
                run_info = db.execute_query(
                    runs_sql, (company_id, run_id_1, run_id_2), max_rows=2
                )
            except Exception as e:
                return f"Failed to get run info: {e}"

        # Get suggestions from run 1
        sug1_sql = """
        SELECT
            stock_code,
            warehouse,
            order_type,
            planned_quantity,
            required_date,
            due_date,
            order_status,
            critical_flag,
            action_message,
            exception_type
        FROM mrp.Suggestions
        WHERE run_id = %s AND company_id = %s
        """

        # Get suggestions from run 2
        sug2_sql = """
        SELECT
            stock_code,
            warehouse,
            order_type,
            planned_quantity,
            required_date,
            due_date,
            order_status,
            critical_flag,
            action_message,
            exception_type
        FROM mrp.Suggestions
        WHERE run_id = %s AND company_id = %s
        """

        try:
            sug1_result = db.execute_query(sug1_sql, (run_id_1, company_id), max_rows=5000)
            sug2_result = db.execute_query(sug2_sql, (run_id_2, company_id), max_rows=5000)
        except Exception as e:
            return f"Failed to get suggestions: {e}"

        # Create lookup dictionaries keyed by (stock_code, warehouse, order_type)
        def make_key(s: dict) -> tuple:
            return (
                s.get('stock_code', ''),
                s.get('warehouse', ''),
                s.get('order_type', ''),
            )

        sug1_by_key: dict[tuple, list[dict]] = {}
        for s in sug1_result:
            key = make_key(s)
            if key not in sug1_by_key:
                sug1_by_key[key] = []
            sug1_by_key[key].append(s)

        sug2_by_key: dict[tuple, list[dict]] = {}
        for s in sug2_result:
            key = make_key(s)
            if key not in sug2_by_key:
                sug2_by_key[key] = []
            sug2_by_key[key].append(s)

        # Find differences
        all_keys = set(sug1_by_key.keys()) | set(sug2_by_key.keys())

        new_suggestions = []  # In run 2 but not run 1
        removed_suggestions = []  # In run 1 but not run 2
        changed_suggestions = []  # In both but different

        for key in all_keys:
            in_run1 = key in sug1_by_key
            in_run2 = key in sug2_by_key

            if in_run2 and not in_run1:
                # New in run 2
                for s in sug2_by_key[key]:
                    new_suggestions.append(s)
            elif in_run1 and not in_run2:
                # Removed (was in run 1)
                for s in sug1_by_key[key]:
                    removed_suggestions.append(s)
            else:
                # Both exist - compare quantities and dates
                list1 = sug1_by_key[key]
                list2 = sug2_by_key[key]

                # Simple comparison: sum quantities
                qty1 = sum(float(s.get('planned_quantity', 0) or 0) for s in list1)
                qty2 = sum(float(s.get('planned_quantity', 0) or 0) for s in list2)

                # Get earliest dates
                dates1 = [s.get('required_date') for s in list1 if s.get('required_date')]
                dates2 = [s.get('required_date') for s in list2 if s.get('required_date')]
                date1 = min(dates1) if dates1 else None
                date2 = min(dates2) if dates2 else None

                # Check for changes
                qty_changed = abs(qty2 - qty1) > 0.01
                date_changed = date1 != date2
                count_changed = len(list1) != len(list2)

                if qty_changed or date_changed or count_changed:
                    changed_suggestions.append({
                        'stock_code': key[0],
                        'warehouse': key[1],
                        'order_type': key[2],
                        'old_qty': qty1,
                        'new_qty': qty2,
                        'qty_change': qty2 - qty1,
                        'old_date': date1,
                        'new_date': date2,
                        'old_count': len(list1),
                        'new_count': len(list2),
                    })

        # Build output
        output = f"\nMRP RUN COMPARISON - {company_id}\n"
        output += "=" * 90 + "\n"

        # Run info
        output += "\nRUN DETAILS\n"
        output += "-" * 90 + "\n"
        for i, run in enumerate(run_info):
            label = "OLD" if run.get('run_id') == run_id_1 else "NEW"
            output += f"  {label} Run #{run.get('run_id')}: {run.get('run_name', 'N/A')}\n"
            output += f"      Date: {run.get('created_date', 'N/A')}\n"
            output += f"      Items: {run.get('items_processed', 0):,} | Suggestions: {run.get('planning_orders_created', 0):,}\n"

        # Summary statistics
        output += "\nSUMMARY\n"
        output += "-" * 90 + "\n"
        output += f"  Suggestions in old run:  {len(sug1_result):,}\n"
        output += f"  Suggestions in new run:  {len(sug2_result):,}\n"
        output += f"  Net change:              {len(sug2_result) - len(sug1_result):+,}\n"
        output += "\n"
        output += f"  NEW suggestions:         {len(new_suggestions):,}\n"
        output += f"  REMOVED suggestions:     {len(removed_suggestions):,}\n"
        output += f"  CHANGED suggestions:     {len(changed_suggestions):,}\n"

        # New suggestions
        output += "\n" + "─" * 90 + "\n"
        output += f"NEW SUGGESTIONS (in new run only) - {len(new_suggestions)} items\n"
        output += "─" * 90 + "\n"
        if new_suggestions:
            output += f"{'Stock Code':<22} {'WH':<8} {'Type':<10} {'Qty':>12} {'Required':>12} {'Critical':<8}\n"
            output += "-" * 90 + "\n"
            # Sort by critical first, then quantity
            new_suggestions.sort(
                key=lambda x: (
                    0 if x.get('critical_flag') else 1,
                    -float(x.get('planned_quantity', 0) or 0),
                )
            )
            for s in new_suggestions[:25]:
                stock = (s.get('stock_code') or '')[:21]
                wh = (s.get('warehouse') or '')[:7]
                otype = (s.get('order_type') or '')[:9]
                qty = float(s.get('planned_quantity', 0) or 0)
                date = str(s.get('required_date', ''))[:10]
                crit = "YES" if s.get('critical_flag') else ""
                output += f"{stock:<22} {wh:<8} {otype:<10} {qty:>12,.0f} {date:>12} {crit:<8}\n"
            if len(new_suggestions) > 25:
                output += f"... and {len(new_suggestions) - 25} more new suggestions\n"
        else:
            output += "  No new suggestions.\n"

        # Removed suggestions
        output += "\n" + "─" * 90 + "\n"
        output += f"REMOVED SUGGESTIONS (were in old run) - {len(removed_suggestions)} items\n"
        output += "─" * 90 + "\n"
        if removed_suggestions:
            output += f"{'Stock Code':<22} {'WH':<8} {'Type':<10} {'Qty':>12} {'Required':>12}\n"
            output += "-" * 90 + "\n"
            removed_suggestions.sort(
                key=lambda x: -float(x.get('planned_quantity', 0) or 0)
            )
            for s in removed_suggestions[:25]:
                stock = (s.get('stock_code') or '')[:21]
                wh = (s.get('warehouse') or '')[:7]
                otype = (s.get('order_type') or '')[:9]
                qty = float(s.get('planned_quantity', 0) or 0)
                date = str(s.get('required_date', ''))[:10]
                output += f"{stock:<22} {wh:<8} {otype:<10} {qty:>12,.0f} {date:>12}\n"
            if len(removed_suggestions) > 25:
                output += f"... and {len(removed_suggestions) - 25} more removed suggestions\n"
        else:
            output += "  No removed suggestions.\n"

        # Changed suggestions
        output += "\n" + "─" * 90 + "\n"
        output += f"CHANGED SUGGESTIONS (quantity or date changes) - {len(changed_suggestions)} items\n"
        output += "─" * 90 + "\n"
        if changed_suggestions:
            output += f"{'Stock Code':<22} {'Type':<10} {'Old Qty':>10} {'New Qty':>10} {'Change':>10} {'Date Chg':<10}\n"
            output += "-" * 90 + "\n"
            # Sort by absolute change
            changed_suggestions.sort(
                key=lambda x: -abs(x.get('qty_change', 0))
            )
            for c in changed_suggestions[:25]:
                stock = c['stock_code'][:21]
                otype = c['order_type'][:9]
                old_qty = c['old_qty']
                new_qty = c['new_qty']
                change = c['qty_change']
                date_chg = "YES" if c['old_date'] != c['new_date'] else ""
                output += f"{stock:<22} {otype:<10} {old_qty:>10,.0f} {new_qty:>10,.0f} {change:>+10,.0f} {date_chg:<10}\n"
            if len(changed_suggestions) > 25:
                output += f"... and {len(changed_suggestions) - 25} more changed suggestions\n"
        else:
            output += "  No changed suggestions.\n"

        # Analysis
        output += "\n" + "─" * 90 + "\n"
        output += "ANALYSIS\n"
        output += "─" * 90 + "\n"

        # Count criticals
        new_critical = sum(1 for s in new_suggestions if s.get('critical_flag'))
        if new_critical:
            output += f"  WARNING: {new_critical} new CRITICAL suggestions require attention\n"

        # Large quantity changes
        large_changes = [c for c in changed_suggestions if abs(c['qty_change']) > 1000]
        if large_changes:
            output += f"  NOTE: {len(large_changes)} items have quantity changes > 1,000 units\n"

        # Net quantity change
        total_new_qty = sum(float(s.get('planned_quantity', 0) or 0) for s in new_suggestions)
        total_removed_qty = sum(float(s.get('planned_quantity', 0) or 0) for s in removed_suggestions)
        total_change_qty = sum(c['qty_change'] for c in changed_suggestions)
        net_qty_change = total_new_qty - total_removed_qty + total_change_qty
        output += f"  Net planned quantity change: {net_qty_change:+,.0f}\n"

        return output

    @mcp.tool()
    @audit_tool_call("list_mrp_runs")
    async def list_mrp_runs(company_id: str, limit: int = 10) -> str:
        """List recent MRP runs for a company.

        Shows run history to help select runs for comparison or analysis.

        Args:
            company_id: Tempo company identifier (e.g., 'TTM', 'TTML', 'IV').
            limit: Number of runs to show (default 10).

        Returns:
            List of recent MRP runs with IDs and statistics.
        """
        db = get_tempo_db()

        runs_sql = """
        SELECT TOP %s
            run_id,
            run_name,
            created_date,
            status,
            items_processed,
            planning_orders_created,
            planning_horizon_days,
            accuracy_percentage
        FROM mrp.Runs
        WHERE company_id = %s
        ORDER BY created_date DESC
        """

        try:
            runs = db.execute_query(runs_sql, (limit, company_id), max_rows=limit)
        except Exception as e:
            return f"Failed to get MRP runs: {e}"

        if not runs:
            return f"No MRP runs found for company {company_id}."

        output = f"\nMRP RUN HISTORY - {company_id}\n"
        output += "=" * 95 + "\n"
        output += f"{'Run ID':>8} {'Run Name':<25} {'Date':<20} {'Status':<10} {'Items':>8} {'Suggest':>8}\n"
        output += "-" * 95 + "\n"

        for run in runs:
            run_id = run.get('run_id', '')
            name = (run.get('run_name') or '')[:24]
            date = str(run.get('created_date', ''))[:19]
            status = (run.get('status') or '')[:9]
            items = int(run.get('items_processed', 0) or 0)
            suggestions = int(run.get('planning_orders_created', 0) or 0)
            output += f"{run_id:>8} {name:<25} {date:<20} {status:<10} {items:>8,} {suggestions:>8,}\n"

        output += "\nUse compare_mrp_runs(company_id, run_id_1, run_id_2) to compare any two runs.\n"

        return output
