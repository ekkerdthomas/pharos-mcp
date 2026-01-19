"""
Schema exploration tools for Pharos MCP.

These tools use SQL Server INFORMATION_SCHEMA views to provide
metadata about the SYSPRO database schema, with SYSPRO-specific
domain knowledge built in.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..core.audit import audit_tool_call
from ..core.database import get_company_db


# SYSPRO domain knowledge: maps business concepts to table prefixes
SYSPRO_DOMAIN_MAP = {
    # Customer/AR related
    "customer": ["Ar", "ArCustomer", "CusSor"],
    "customers": ["Ar", "ArCustomer", "CusSor"],
    "debtor": ["Ar"],
    "debtors": ["Ar"],
    "receivable": ["Ar"],
    "receivables": ["Ar"],
    "ar": ["Ar"],
    "accounts receivable": ["Ar"],

    # Supplier/AP related
    "supplier": ["Ap", "ApSupplier", "Por"],
    "suppliers": ["Ap", "ApSupplier", "Por"],
    "vendor": ["Ap", "ApSupplier"],
    "vendors": ["Ap", "ApSupplier"],
    "creditor": ["Ap"],
    "creditors": ["Ap"],
    "payable": ["Ap"],
    "payables": ["Ap"],
    "ap": ["Ap"],
    "accounts payable": ["Ap"],

    # Inventory related
    "inventory": ["Inv", "InvMaster", "InvWarehouse"],
    "stock": ["Inv", "InvMaster", "InvWarehouse"],
    "item": ["Inv", "InvMaster", "Bom"],
    "items": ["Inv", "InvMaster", "Bom"],
    "product": ["Inv", "InvMaster", "Bom"],
    "products": ["Inv", "InvMaster", "Bom"],
    "warehouse": ["Inv", "InvWarehouse", "InvWhControl"],
    "bin": ["Inv", "InvBin"],
    "lot": ["Lot", "Inv"],
    "serial": ["Inv", "InvSerial"],

    # Sales related
    "sales": ["Sor", "SorMaster", "SorDetail", "Sal"],
    "order": ["Sor", "Por", "SorMaster", "PorMaster"],
    "orders": ["Sor", "Por", "SorMaster", "PorMaster"],
    "sales order": ["Sor", "SorMaster", "SorDetail"],
    "so": ["Sor", "SorMaster"],
    "quote": ["Sor", "Qot", "SorQuote"],
    "quotation": ["Qot", "Sor"],
    "invoice": ["Ar", "ArInvoice", "Sor"],
    "invoices": ["Ar", "ArInvoice", "Sor"],
    "dispatch": ["Sor", "Whm"],
    "shipping": ["Sor", "Whm", "TblShip"],
    "delivery": ["Sor", "Whm"],
    "salesperson": ["Sal", "SalSalesperson"],
    "commission": ["Sal", "SalCommission"],

    # Purchasing related
    "purchase": ["Por", "PorMaster", "Ap"],
    "purchasing": ["Por", "PorMaster", "Ap"],
    "purchase order": ["Por", "PorMaster"],
    "po": ["Por", "PorMaster"],
    "grn": ["Por", "Grn"],
    "goods received": ["Grn"],
    "requisition": ["Req", "Por"],
    "buyer": ["Por"],

    # Manufacturing related
    "job": ["Wip", "WipMaster"],
    "jobs": ["Wip", "WipMaster"],
    "work in progress": ["Wip"],
    "wip": ["Wip", "WipMaster"],
    "work order": ["Wip", "WipMaster"],
    "manufacturing": ["Wip", "Bom"],
    "production": ["Wip", "Bom"],
    "bom": ["Bom", "BomStructure"],
    "bill of materials": ["Bom", "BomStructure"],
    "routing": ["Bom", "BomRoute"],
    "operation": ["Bom", "Wip"],
    "workcenter": ["Bom", "Wip"],
    "labor": ["Wip", "Bom"],
    "scrap": ["Wip", "Inv"],

    # Financial related
    "gl": ["Gen", "GenMaster"],
    "general ledger": ["Gen", "GenMaster"],
    "ledger": ["Gen", "GenMaster"],
    "account": ["Gen", "GenMaster", "Ar", "Ap"],
    "accounts": ["Gen", "GenMaster", "Ar", "Ap"],
    "journal": ["Gen", "Ar", "Ap"],
    "cashbook": ["Cb", "Csh"],
    "cash": ["Cb", "Csh", "Ar"],
    "bank": ["Cb", "Ap", "ApBank"],
    "payment": ["Ap", "Ar", "Cb", "Csh"],
    "payments": ["Ap", "Ar", "Cb", "Csh"],
    "receipt": ["Ar", "Csh"],
    "budget": ["Gen", "Sal"],
    "cost": ["Inv", "Wip", "Gen"],
    "costing": ["Inv", "Wip"],

    # Pricing
    "price": ["Inv", "InvPrice", "Sor", "SorPrice"],
    "pricing": ["Inv", "InvPrice", "Sor", "SorPrice"],
    "discount": ["Inv", "Sor", "TblSoDiscount"],
    "price list": ["Sor", "SorPriceList"],

    # Configuration/Lookup tables
    "lookup": ["Tbl"],
    "setup": ["Tbl", "Adm", "Control"],
    "configuration": ["Adm", "Control"],
    "control": ["Control"],
    "terms": ["Tbl", "TblArTerms", "TblApTerms"],

    # Other
    "address": ["Ar", "Ap", "ArMultAddress", "ApMultAddress"],
    "contact": ["Ar", "Ap", "Cms", "Crm"],
    "branch": ["Ar", "Ap", "Adm", "SalBranch"],
    "tax": ["Tax", "Adm"],
    "currency": ["Adm", "Trs", "TblCurrency"],
    "history": ["Arc", "Hist", "SalHistory"],
    "archive": ["Arc"],
    "audit": ["Audit", "Adm"],
    "user": ["Adm", "Usr"],
    "operator": ["Adm"],
    "document": ["Adm", "Document"],
    "report": ["Adm", "Rpt"],
    "mrp": ["Mrp"],
    "planning": ["Mrp"],
    "forecast": ["Mrp", "MrpForecast"],
    "crm": ["Crm"],
    "asset": ["Asset", "Ass"],
    "fixed asset": ["Asset", "Ass"],
    "quality": ["Sqm"],
    "inspection": ["Sqm", "Inv"],
    "rma": ["Rma"],
    "returns": ["Rma", "Rts"],
    "point of sale": ["Pos"],
    "pos": ["Pos"],
    "eft": ["Eft"],
    "electronic": ["Eft", "Ecc"],
    "ecommerce": ["Ecc"],
    "e-commerce": ["Ecc"],
    "blanket": ["Bso", "Bpo"],
    "project": ["Prj"],
    "projects": ["Prj"],
    "configurator": ["Cfg"],
    "service": ["Srq"],
    "intercompany": ["Iop"],
    "transit": ["Gtr"],
    "transfer": ["Gtr"],

    # Financial terms
    "balance": ["Ar", "Ap", "Gen", "ArCustomerBal", "Inv"],
    "balances": ["Ar", "Ap", "Gen", "ArCustomerBal"],
    "aging": ["Ar", "Ap", "ArCustomerBal"],
    "ageing": ["Ar", "Ap", "ArCustomerBal"],
    "outstanding": ["Ar", "Ap", "Sor"],
    "overdue": ["Ar", "Ap"],
    "credit": ["Ar", "ArCustomer"],
    "debit": ["Ar", "Ap"],

    # Transaction terms
    "transaction": ["Ar", "Ap", "Gen", "Inv", "Lot"],
    "transactions": ["Ar", "Ap", "Gen", "Inv", "Lot"],
    "movement": ["Inv", "InvMovements"],
    "movements": ["Inv", "InvMovements"],
    "journal": ["Gen", "Ar", "Ap", "Inv"],
    "posting": ["Gen", "Ar", "Ap"],

    # Document terms
    "delivery": ["Sor", "Whm", "Grn"],
    "shipment": ["Sor", "Whm"],
    "picking": ["Whm", "Sor"],
    "packing": ["Whm", "Sor"],

    # Master data
    "master": ["Inv", "Ar", "Ap", "Gen", "Sor", "Por", "Wip"],
    "detail": ["Sor", "Por", "Wip", "Inv"],
    "header": ["Sor", "Por", "Wip"],
    "line": ["Sor", "Por", "Wip"],
}

# Module descriptions - comprehensive list of SYSPRO table prefixes
SYSPRO_MODULES = {
    # Core Financials
    "Adm": "Administration",
    "Ap": "Accounts Payable",
    "Ar": "Accounts Receivable",
    "Gen": "General Ledger",
    "Cb": "Cash Book",
    "Csh": "Cash Book",
    "Tax": "Tax",
    "Trs": "Treasury",
    "Eft": "Electronic Funds Transfer",

    # Inventory & Warehouse
    "Inv": "Inventory",
    "Lot": "Lot Tracking",
    "Whm": "Warehouse Management",
    "Wms": "Warehouse Management System",
    "Gtr": "Goods in Transit",
    "Lct": "Location Tracking",

    # Sales & Distribution
    "Sor": "Sales Orders",
    "Qot": "Quotations",
    "Sal": "Sales Analysis",
    "Bso": "Blanket Sales Orders",
    "Pos": "Point of Sale",

    # Purchasing
    "Por": "Purchase Orders",
    "Req": "Requisitions",
    "Grn": "Goods Received Notes",
    "Bpo": "Blanket Purchase Orders",
    "Rma": "Return Material Authorization",
    "Rts": "Return to Supplier",

    # Manufacturing
    "Wip": "Work in Progress",
    "Bom": "Bill of Materials",
    "Mrp": "Material Requirements Planning",
    "Iop": "Intercompany Operations",

    # Quality & Service
    "Sqm": "Quality Management",
    "Srq": "Service Requests",
    "Cfg": "Product Configurator",

    # CRM & Contacts
    "Crm": "Customer Relationship Management",
    "Cms": "Contact Management",

    # Projects & Assets
    "Prj": "Projects",
    "Ass": "Asset Management",
    "Asset": "Asset Management",
    "Eam": "Enterprise Asset Management",

    # E-Commerce & Integration
    "Ecc": "E-Commerce",
    "Int": "Integration",

    # Trade & Promotions
    "Tpm": "Trade Promotions",
    "Mdn": "Merchandise Distribution",

    # Configuration/Setup
    "Tbl": "Lookup Tables",
    "Arc": "Archive Tables",

    # Other
    "Sws": "SYSPRO Web Services",
}

# Common lookup tables mapping: code_type -> (table_name, code_column, description_column)
SYSPRO_LOOKUP_TABLES = {
    # Payment/Terms
    "terms": ("TblArTerms", "TermsCode", "Description"),
    "ar_terms": ("TblArTerms", "TermsCode", "Description"),
    "ap_terms": ("TblApTerms", "TermsCode", "Description"),

    # Classification
    "customer_class": ("TblCustomerClass", "Class", "Description"),
    "supplier_class": ("TblSupplierClass", "Class", "Description"),
    "stock_class": ("TblStockClass", "Class", "Description"),
    "product_class": ("TblProductClass", "ProductClass", "Description"),
    "job_class": ("WipJobClass", "JobClassification", "Description"),

    # Currency
    "currency": ("TblCurrency", "Currency", "Description"),

    # Sales
    "order_type": ("TblSoTypes", "OrderType", "Description"),
    "buying_group": ("TblSoBuyingGroup", "BuyingGroup", "Description"),
    "shipping_instructions": ("TblSoShipInst", "ShipInstructions", "Description"),
    "so_reason": ("TblSoReason", "ReasonCode", "Description"),
    "delivery_terms": ("TblSaDelTerms", "DeliveryTerms", "Description"),
    "shipping_location": ("TblShipLocation", "ShippingLocation", "Description"),
    "salesperson": ("SalSalesperson", "Salesperson", "Name"),

    # Purchasing
    "po_comment": ("TblPoComment", "CommentCode", "Description"),
    "buyer": ("InvBuyer", "Buyer", "Name"),

    # Branch/Area
    "branch": ("SalBranch", "Branch", "Description"),
    "area": ("SalArea", "Area", "Description"),

    # Warehouse
    "warehouse": ("InvWhControl", "Warehouse", "Description"),

    # Inventory
    "unit_of_measure": ("TblUnitOfMeasure", "UnitOfMeasure", "Description"),
    "uom": ("TblUnitOfMeasure", "UnitOfMeasure", "Description"),
    "price_code": ("TblPriceCode", "PriceCode", "Description"),

    # Tax
    "tax_code": ("AdmTax", "TaxCode", "Description"),

    # Geography
    "country": ("TblCountry", "Country", "CountryDesc"),
    "nationality": ("TblNationality", "Nationality", "Description"),

    # GL/Accounting
    "gl_group": ("GenGlGroup", "GlGroup", "Description"),

    # Manufacturing
    "route": ("BomRoute", "Route", "Description"),
    "workcenter": ("BomWorkCentre", "WorkCentre", "Description"),
    "work_center": ("BomWorkCentre", "WorkCentre", "Description"),

    # Operators/Users
    "operator": ("AdmOperator", "Operator", "Name"),
}

# Static code definitions for status fields (not in lookup tables)
SYSPRO_STATUS_CODES = {
    "order_status": {
        "1": "Order entered",
        "2": "Open/Released to warehouse",
        "3": "In warehouse",
        "4": "Part shipped",
        "5": "Reserved",
        "6": "Forward order",
        "7": "Scheduled order",
        "8": "Ready to invoice",
        "9": "Complete",
        "S": "Suspended",
        "/": "Cancelled",
        "\\": "Cancelled",
        "*": "In progress",
        " ": "New",
    },
    "active_flag": {
        "Y": "Active",
        "N": "Inactive",
        " ": "Active (default)",
    },
    "cancelled_flag": {
        "Y": "Cancelled",
        "N": "Not cancelled",
        " ": "Not cancelled (default)",
    },
    "document_type": {
        "O": "Order",
        "Q": "Quote",
        "B": "Blanket order",
        "S": "Standing order",
        "C": "Credit note",
        "D": "Debit note",
        "I": "Invoice",
    },
    "credit_status": {
        "0": "Not checked / OK",
        "1": "OK - Passed credit check",
        "2": "Warning - Exceeded limit",
        "3": "Must stop - Credit hold",
        "4": "Referral required",
        "5": "Cash only",
        "6": "Special terms",
        " ": "Not set",
    },
    "customer_on_hold": {
        "Y": "On hold",
        "N": "Not on hold",
        " ": "Not on hold (default)",
    },
    "tax_status": {
        "E": "Exempt",
        "N": "Non-taxable",
        "T": "Taxable",
        " ": "Default (usually Taxable)",
    },
    "job_status": {
        "0": "Planned",
        "1": "Firm planned",
        "2": "Released",
        "3": "In progress",
        "4": "Complete",
        "5": "On hold",
        "9": "Cancelled",
        "F": "Finished",
        "S": "Suspended",
    },
    "job_complete": {
        "Y": "Complete",
        "N": "Not complete / Active",
    },
    "job_hold_flag": {
        "Y": "On hold",
        "N": "Not on hold",
    },
    "po_status": {
        "1": "Order entered",
        "2": "Printed",
        "3": "Part received",
        "4": "Change pending",
        "8": "Ready for GRN",
        "9": "Complete",
        "/": "Cancelled",
        "S": "Suspended",
    },
    "invoice_status": {
        "0": "Open",
        "1": "Partially paid",
        "9": "Paid in full",
        "D": "Disputed",
    },
    "grn_status": {
        "1": "Received",
        "2": "Inspected",
        "3": "In stock",
        "9": "Complete",
        "R": "Rejected",
    },
    "stock_type": {
        "B": "Buy-in item",
        "M": "Manufactured",
        "N": "Non-stocked",
        "P": "Phantom",
        "S": "Stocked",
        "T": "Subcontract",
    },
    "abc_class": {
        "A": "High value/volume",
        "B": "Medium value/volume",
        "C": "Low value/volume",
        "D": "Dead stock",
    },
    "lot_traceable": {
        "Y": "Lot traceable",
        "N": "Not lot traceable",
        "S": "Serial traceable",
        " ": "Not traceable",
    },
    "bom_type": {
        "S": "Standard BOM",
        "P": "Phantom BOM",
        "C": "Co-product BOM",
        "F": "Formula BOM",
    },
    "confirmed_flag": {
        "Y": "Confirmed",
        "N": "Not confirmed / Soft allocated",
        " ": "Not confirmed",
    },
    "supplier_on_hold": {
        "Y": "On hold",
        "N": "Not on hold",
        " ": "Not on hold (default)",
    },
    "mul_div": {
        "M": "Multiply",
        "D": "Divide",
        " ": "Not applicable",
    },
    "payment_type": {
        "C": "Cash",
        "H": "Cheque",
        "E": "EFT",
        "D": "Direct debit",
        " ": "Default",
    },
    "yes_no": {
        "Y": "Yes",
        "N": "No",
        " ": "Not set (default No)",
    },
    "gl_account_type": {
        "A": "Asset",
        "L": "Liability",
        "C": "Capital/Equity",
        "R": "Revenue",
        "E": "Expense",
    },
    "movement_type": {
        "I": "Inventory movement",
        "S": "Sales/dispatch",
    },
    "trn_type": {
        "A": "Adjustment (stock take/manual)",
        "B": "Beginning balance/opening stock",
        "C": "Cost adjustment (BOM to WH cost)",
        "I": "Issue to WIP job",
        "R": "Receipt from GRN/PO",
        "T": "Transfer between warehouses",
        "W": "WIP receipt (production completion)",
        "P": "Physical count",
    },
    "ap_invoice_status": {
        " ": "Open",
        "0": "Open",
        "1": "Partially paid",
        "9": "Paid in full",
        "D": "Disputed",
        "H": "On hold",
    },
    "cb_trn_type": {
        "D": "Deposit/Receipt",
        "W": "Withdrawal/Payment",
        "T": "Transfer",
        "J": "Journal entry",
    },
    "reconciled_flag": {
        "Y": "Reconciled",
        "N": "Not reconciled",
        " ": "Not reconciled",
    },
    "serial_detail_type": {
        "SALES": "Sale to customer",
        "DISP": "Dispatch/Shipment",
        "RECV": "Receipt from purchase",
        "ISSUE": "Issue to WIP job",
        "ADJST": "Adjustment",
        "TRANS": "Transfer between warehouses",
        "WIPRC": "WIP receipt (production)",
        "CRJNL": "Credit journal",
        "RMA": "Return material authorization",
    },
    "ar_payment_doc_type": {
        "P": "Payment",
        "R": "Receipt",
        "J": "Journal",
        "C": "Credit note",
        "D": "Debit note",
    },
}


def get_module_for_table(table_name: str) -> str:
    """Get the SYSPRO module for a table based on its prefix."""
    for prefix, description in SYSPRO_MODULES.items():
        if table_name.startswith(prefix):
            return f"{prefix} ({description})"
    return ""


def register_schema_tools(mcp: FastMCP) -> None:
    """Register schema exploration tools with the MCP server."""

    @mcp.tool()
    @audit_tool_call("search_tables")
    async def search_tables(
        search_term: str,
        limit: int = 50,
    ) -> str:
        """Search for SYSPRO tables by name or business concept.

        Understands SYSPRO naming conventions - searches like 'customer' will
        find ArCustomer tables, 'inventory' will find Inv tables, etc.

        Args:
            search_term: Business term or table name to search for.
            limit: Maximum results to return (default 50).

        Returns:
            Formatted list of matching tables with module info.
        """
        db = get_company_db()
        search_lower = search_term.lower().strip()

        # Build list of search patterns
        patterns = [f"%{search_term}%"]  # Always search the literal term

        # Add SYSPRO-specific patterns based on domain knowledge
        if search_lower in SYSPRO_DOMAIN_MAP:
            for prefix in SYSPRO_DOMAIN_MAP[search_lower]:
                patterns.append(f"{prefix}%")

        # Remove duplicates while preserving order
        seen = set()
        unique_patterns = []
        for p in patterns:
            if p.lower() not in seen:
                seen.add(p.lower())
                unique_patterns.append(p)

        # Build query with multiple OR conditions
        conditions = " OR ".join(["t.TABLE_NAME LIKE %s"] * len(unique_patterns))
        sql = f"""
            SELECT DISTINCT TOP %s
                t.TABLE_NAME,
                (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS c
                 WHERE c.TABLE_NAME = t.TABLE_NAME) as ColumnCount
            FROM INFORMATION_SCHEMA.TABLES t
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            AND ({conditions})
            ORDER BY t.TABLE_NAME
        """
        params = tuple([limit] + unique_patterns)

        results = db.execute_query(sql, params)

        if not results:
            # Provide helpful suggestions
            suggestions = []
            if search_lower in ["customer", "customers"]:
                suggestions.append("Try: list_tables with prefix='Ar'")
            elif search_lower in ["inventory", "stock"]:
                suggestions.append("Try: list_tables with prefix='Inv'")
            elif search_lower in ["sales", "order", "orders"]:
                suggestions.append("Try: list_tables with prefix='Sor'")

            msg = f"No tables found matching '{search_term}'."
            if suggestions:
                msg += "\n" + "\n".join(suggestions)
            return msg

        # Group results by module
        lines = [f"Found {len(results)} table(s) for '{search_term}':\n"]

        current_module = None
        for row in results:
            table_name = row.get("TABLE_NAME", "")
            col_count = row.get("ColumnCount", 0)
            module = get_module_for_table(table_name)

            if module != current_module:
                if current_module is not None:
                    lines.append("")
                if module:
                    lines.append(f"[{module}]")
                current_module = module

            lines.append(f"  - {table_name} ({col_count} columns)")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("get_table_schema")
    async def get_table_schema(table_name: str) -> str:
        """Get complete schema details for a table.

        Args:
            table_name: Name of the table to describe.

        Returns:
            Formatted table schema including columns and keys.
        """
        db = get_company_db()

        # Check table exists
        check_sql = """
            SELECT TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = %s
        """
        table_info = db.execute_query(check_sql, (table_name,))

        if not table_info:
            return f"Table '{table_name}' not found."

        # Get columns
        columns_sql = """
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """
        columns = db.execute_query(columns_sql, (table_name,))

        # Get primary key columns
        pk_sql = """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            WHERE tc.TABLE_NAME = %s AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ORDER BY kcu.ORDINAL_POSITION
        """
        pk_cols = db.execute_query(pk_sql, (table_name,))
        pk_names = [r["COLUMN_NAME"] for r in pk_cols]

        # Get foreign keys
        fk_sql = """
            SELECT
                kcu.COLUMN_NAME,
                ccu.TABLE_NAME as REFERENCED_TABLE,
                ccu.COLUMN_NAME as REFERENCED_COLUMN
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE kcu.TABLE_NAME = %s
        """
        fk_info = db.execute_query(fk_sql, (table_name,))

        # Format output
        module = get_module_for_table(table_name)
        lines = [
            f"Table: {table_name}",
        ]
        if module:
            lines.append(f"Module: {module}")
        lines.extend([
            f"Primary Key: {', '.join(pk_names) if pk_names else 'None'}",
            f"Columns: {len(columns)}",
            "",
            "Column Details:",
            "-" * 70,
        ])

        for col in columns:
            col_name = col.get("COLUMN_NAME", "")
            data_type = col.get("DATA_TYPE", "")
            max_len = col.get("CHARACTER_MAXIMUM_LENGTH")
            precision = col.get("NUMERIC_PRECISION")
            scale = col.get("NUMERIC_SCALE")
            nullable = col.get("IS_NULLABLE", "YES")
            default = col.get("COLUMN_DEFAULT")

            # Build type string
            if max_len and max_len > 0:
                if max_len == -1:
                    type_str = f"{data_type}(max)"
                else:
                    type_str = f"{data_type}({max_len})"
            elif precision is not None and scale is not None:
                type_str = f"{data_type}({precision},{scale})"
            elif precision is not None:
                type_str = f"{data_type}({precision})"
            else:
                type_str = data_type

            null_str = "NULL" if nullable == "YES" else "NOT NULL"
            pk_marker = " [PK]" if col_name in pk_names else ""

            lines.append(f"  {col_name}: {type_str} {null_str}{pk_marker}")
            if default:
                lines.append(f"    Default: {default}")

        if fk_info:
            lines.extend(["", "Foreign Keys:", "-" * 70])
            for fk in fk_info:
                col = fk.get("COLUMN_NAME", "")
                ref_table = fk.get("REFERENCED_TABLE", "")
                ref_col = fk.get("REFERENCED_COLUMN", "")
                lines.append(f"  {col} -> {ref_table}.{ref_col}")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("get_table_columns")
    async def get_table_columns(table_name: str) -> str:
        """Get column definitions for a table.

        Args:
            table_name: Name of the table.

        Returns:
            Formatted column definitions.
        """
        db = get_company_db()

        sql = """
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                IS_NULLABLE,
                COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """
        columns = db.execute_query(sql, (table_name,))

        if not columns:
            return f"No columns found for table '{table_name}'."

        lines = [f"Columns for {table_name}:\n"]

        for col in columns:
            col_name = col.get("COLUMN_NAME", "")
            data_type = col.get("DATA_TYPE", "")
            max_len = col.get("CHARACTER_MAXIMUM_LENGTH")
            precision = col.get("NUMERIC_PRECISION")
            scale = col.get("NUMERIC_SCALE")
            nullable = col.get("IS_NULLABLE", "YES")
            default = col.get("COLUMN_DEFAULT")

            # Build type string
            if max_len and max_len > 0:
                type_str = f"{data_type}({max_len})"
            elif precision is not None and scale is not None and scale > 0:
                type_str = f"{data_type}({precision},{scale})"
            elif precision is not None:
                type_str = f"{data_type}({precision})"
            else:
                type_str = data_type

            null_str = "NULL" if nullable == "YES" else "NOT NULL"

            lines.append(f"{col_name}")
            lines.append(f"  Type: {type_str} {null_str}")
            if default:
                lines.append(f"  Default: {default}")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("find_related_tables")
    async def find_related_tables(table_name: str) -> str:
        """Find tables related via foreign keys.

        Shows which tables this table references and which tables reference it,
        grouped by table name to reduce redundancy from composite keys.

        Args:
            table_name: Name of the table to find relationships for.

        Returns:
            Formatted list of related tables.
        """
        db = get_company_db()

        # Get outgoing FKs grouped by constraint to handle composite keys properly
        outgoing_sql = """
            SELECT DISTINCT
                rc.CONSTRAINT_NAME,
                kcu.COLUMN_NAME,
                ccu.TABLE_NAME as REFERENCED_TABLE,
                ccu.COLUMN_NAME as REFERENCED_COLUMN
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE kcu.TABLE_NAME = %s
            ORDER BY ccu.TABLE_NAME, kcu.COLUMN_NAME
        """
        outgoing = db.execute_query(outgoing_sql, (table_name,))

        # Get incoming FKs
        incoming_sql = """
            SELECT DISTINCT
                kcu.TABLE_NAME as REFERENCING_TABLE,
                kcu.COLUMN_NAME as REFERENCING_COLUMN
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE ccu.TABLE_NAME = %s
            ORDER BY kcu.TABLE_NAME
        """
        incoming = db.execute_query(incoming_sql, (table_name,))

        lines = [f"Relationships for {table_name}:\n"]

        if outgoing:
            lines.append("References (this table -> other tables):")
            # Group by referenced table, collect columns
            refs_by_table: dict[str, list[str]] = {}
            for rel in outgoing:
                col = rel.get("COLUMN_NAME", "")
                ref_table = rel.get("REFERENCED_TABLE", "")
                if ref_table not in refs_by_table:
                    refs_by_table[ref_table] = []
                if col not in refs_by_table[ref_table]:
                    refs_by_table[ref_table].append(col)

            for ref_table in sorted(refs_by_table.keys()):
                cols = refs_by_table[ref_table]
                module = get_module_for_table(ref_table)
                module_str = f" [{module}]" if module else ""
                if len(cols) == 1:
                    lines.append(f"  {cols[0]} -> {ref_table}{module_str}")
                else:
                    lines.append(f"  ({', '.join(cols)}) -> {ref_table}{module_str}")
        else:
            lines.append("References: None")

        lines.append("")

        if incoming:
            lines.append(f"Referenced by ({len(set(r.get('REFERENCING_TABLE', '') for r in incoming))} tables):")
            # Group by referencing table
            refs_by_table = {}
            for rel in incoming:
                ref_table = rel.get("REFERENCING_TABLE", "")
                ref_col = rel.get("REFERENCING_COLUMN", "")
                if ref_table not in refs_by_table:
                    refs_by_table[ref_table] = []
                if ref_col not in refs_by_table[ref_table]:
                    refs_by_table[ref_table].append(ref_col)

            for ref_table in sorted(refs_by_table.keys()):
                cols = refs_by_table[ref_table]
                module = get_module_for_table(ref_table)
                module_str = f" [{module}]" if module else ""
                lines.append(f"  {ref_table}{module_str}")
        else:
            lines.append("Referenced by: None")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("search_columns")
    async def search_columns(
        search_term: str,
        table_pattern: str | None = None,
        limit: int = 50,
    ) -> str:
        """Search for columns across all tables by name.

        Args:
            search_term: Text to search for in column names.
            table_pattern: Optional table name pattern to filter.
            limit: Maximum results to return (default 50).

        Returns:
            Formatted list of matching columns.
        """
        db = get_company_db()

        sql = """
            SELECT TOP %s
                c.TABLE_NAME,
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS c
            JOIN INFORMATION_SCHEMA.TABLES t ON c.TABLE_NAME = t.TABLE_NAME
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            AND c.COLUMN_NAME LIKE %s
        """
        params: list[Any] = [limit, f"%{search_term}%"]

        if table_pattern:
            sql += " AND c.TABLE_NAME LIKE %s"
            params.append(f"%{table_pattern}%")

        sql += " ORDER BY c.TABLE_NAME, c.COLUMN_NAME"

        results = db.execute_query(sql, tuple(params))

        if not results:
            return f"No columns found matching '{search_term}'."

        lines = [f"Found {len(results)} column(s) matching '{search_term}':\n"]

        current_table = None
        for row in results:
            table = row.get("TABLE_NAME", "")
            if table != current_table:
                if current_table is not None:
                    lines.append("")
                module = get_module_for_table(table)
                module_str = f" [{module}]" if module else ""
                lines.append(f"{table}{module_str}")
                current_table = table

            col_name = row.get("COLUMN_NAME", "")
            data_type = row.get("DATA_TYPE", "")
            lines.append(f"  - {col_name} ({data_type})")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("list_tables")
    async def list_tables(
        prefix: str | None = None,
        module: str | None = None,
        limit: int = 100,
    ) -> str:
        """List tables in the database.

        Args:
            prefix: Table name prefix filter (e.g., 'Ar', 'Inv', 'Sor').
            module: Module name filter (e.g., 'Accounts Receivable', 'Inventory').
            limit: Maximum results to return (default 100).

        Returns:
            Formatted list of tables.
        """
        db = get_company_db()

        # If module name given, convert to prefix
        if module and not prefix:
            module_lower = module.lower()
            for code, name in SYSPRO_MODULES.items():
                if module_lower in name.lower() or module_lower == code.lower():
                    prefix = code
                    break

        sql = """
            SELECT TOP %s
                t.TABLE_NAME,
                (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS c
                 WHERE c.TABLE_NAME = t.TABLE_NAME) as ColumnCount
            FROM INFORMATION_SCHEMA.TABLES t
            WHERE t.TABLE_TYPE = 'BASE TABLE'
        """
        params: list[Any] = [limit]

        if prefix:
            sql += " AND t.TABLE_NAME LIKE %s"
            params.append(f"{prefix}%")

        sql += " ORDER BY t.TABLE_NAME"

        results = db.execute_query(sql, tuple(params))

        if not results:
            msg = "No tables found"
            if prefix:
                msg += f" with prefix '{prefix}'"
            return msg + "."

        lines = []
        if prefix:
            module_desc = SYSPRO_MODULES.get(prefix, "")
            if module_desc:
                lines.append(f"Tables in {module_desc} ({prefix}):\n")
            else:
                lines.append(f"Tables starting with '{prefix}':\n")
        else:
            lines.append(f"Tables ({len(results)} shown):\n")

        for row in results:
            table_name = row.get("TABLE_NAME", "")
            col_count = row.get("ColumnCount", 0)
            lines.append(f"  {table_name} ({col_count} cols)")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("list_modules")
    async def list_modules() -> str:
        """List SYSPRO modules with table counts.

        Returns:
            List of SYSPRO modules and their table counts.
        """
        db = get_company_db()

        lines = ["SYSPRO Modules:\n"]

        for prefix, description in sorted(SYSPRO_MODULES.items()):
            sql = """
                SELECT COUNT(*) as cnt
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                AND TABLE_NAME LIKE %s
            """
            result = db.execute_scalar(sql, (f"{prefix}%",))
            count = int(result) if result else 0

            if count > 0:
                lines.append(f"  {prefix} - {description}: {count} tables")

        lines.append("\nUse list_tables(prefix='XX') to see tables in a module.")
        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("get_lookup_value")
    async def get_lookup_value(
        lookup_type: str,
        code: str | None = None,
    ) -> str:
        """Look up the meaning of a SYSPRO code.

        Gets the description for a code value, or lists all values for a lookup type.
        Common lookup types: terms, currency, order_type, customer_class, branch,
        area, warehouse, order_status, document_type, credit_status.

        Args:
            lookup_type: Type of lookup (e.g., 'terms', 'currency', 'order_status').
            code: Optional specific code to look up. If not provided, lists all values.

        Returns:
            Description of the code, or list of all codes and descriptions.
        """
        lookup_lower = lookup_type.lower().strip()

        # Check static status codes first
        if lookup_lower in SYSPRO_STATUS_CODES:
            codes = SYSPRO_STATUS_CODES[lookup_lower]
            if code is not None:
                desc = codes.get(code, codes.get(code.upper(), codes.get(code.strip())))
                if desc:
                    return f"{lookup_type} '{code}' = {desc}"
                return f"Unknown {lookup_type} code: '{code}'. Valid codes: {', '.join(codes.keys())}"
            else:
                lines = [f"{lookup_type} codes:\n"]
                for k, v in codes.items():
                    display_key = repr(k) if k == " " else k
                    lines.append(f"  {display_key}: {v}")
                return "\n".join(lines)

        # Check database lookup tables
        if lookup_lower not in SYSPRO_LOOKUP_TABLES:
            available = sorted(set(list(SYSPRO_LOOKUP_TABLES.keys()) + list(SYSPRO_STATUS_CODES.keys())))
            return f"Unknown lookup type: '{lookup_type}'.\n\nAvailable types:\n  " + "\n  ".join(available)

        table_name, code_col, desc_col = SYSPRO_LOOKUP_TABLES[lookup_lower]
        db = get_company_db()

        if code is not None:
            # Look up specific code
            sql = f"SELECT {desc_col} FROM {table_name} WHERE {code_col} = %s"
            result = db.execute_scalar(sql, (code,))
            if result:
                return f"{lookup_type} '{code}' = {result}"
            return f"Code '{code}' not found in {lookup_type} lookup."
        else:
            # List all codes
            sql = f"SELECT {code_col}, {desc_col} FROM {table_name} ORDER BY {code_col}"
            results = db.execute_query(sql, max_rows=100)

            if not results:
                return f"No values found in {lookup_type} lookup table."

            lines = [f"{lookup_type} codes ({table_name}):\n"]
            for row in results:
                code_val = row.get(code_col, "")
                desc_val = row.get(desc_col, "")
                lines.append(f"  {code_val}: {desc_val}")

            return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("explain_column")
    async def explain_column(
        table_name: str,
        column_name: str,
    ) -> str:
        """Get detailed information about a column, including sample values.

        Provides the column definition, data type, and sample distinct values
        to help understand what data the column contains.

        Args:
            table_name: Name of the table containing the column.
            column_name: Name of the column to explain.

        Returns:
            Column details with sample values.
        """
        db = get_company_db()

        # Get column info
        col_sql = """
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                IS_NULLABLE,
                COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s AND COLUMN_NAME = %s
        """
        col_info = db.execute_query(col_sql, (table_name, column_name))

        if not col_info:
            return f"Column '{column_name}' not found in table '{table_name}'."

        col = col_info[0]
        data_type = col.get("DATA_TYPE", "")
        max_len = col.get("CHARACTER_MAXIMUM_LENGTH")
        precision = col.get("NUMERIC_PRECISION")
        scale = col.get("NUMERIC_SCALE")
        nullable = col.get("IS_NULLABLE", "YES")

        # Build type string
        if max_len and max_len > 0:
            type_str = f"{data_type}({max_len})"
        elif precision is not None and scale is not None and scale > 0:
            type_str = f"{data_type}({precision},{scale})"
        elif precision is not None:
            type_str = f"{data_type}({precision})"
        else:
            type_str = data_type

        # Check if it's a primary key
        pk_sql = """
            SELECT 1
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            WHERE tc.TABLE_NAME = %s AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            AND kcu.COLUMN_NAME = %s
        """
        is_pk = bool(db.execute_query(pk_sql, (table_name, column_name)))

        # Get sample distinct values
        sample_sql = f"""
            SELECT TOP 15 [{column_name}] as val, COUNT(*) as cnt
            FROM [{table_name}]
            WHERE [{column_name}] IS NOT NULL AND [{column_name}] <> ''
            GROUP BY [{column_name}]
            ORDER BY COUNT(*) DESC
        """
        try:
            samples = db.execute_query(sample_sql, max_rows=15)
        except Exception:
            samples = []

        # Get total count
        total_sql = f"SELECT COUNT(*) FROM [{table_name}]"
        total = db.execute_scalar(total_sql) or 0

        # Get null count
        null_sql = f"SELECT COUNT(*) FROM [{table_name}] WHERE [{column_name}] IS NULL"
        null_count = db.execute_scalar(null_sql) or 0

        # Build output
        lines = [
            f"Column: {table_name}.{column_name}",
            f"Type: {type_str} {'NULL' if nullable == 'YES' else 'NOT NULL'}",
        ]
        if is_pk:
            lines.append("Role: PRIMARY KEY")

        lines.extend([
            "",
            f"Statistics:",
            f"  Total rows: {total:,}",
            f"  Null values: {null_count:,} ({100*null_count/total:.1f}%)" if total > 0 else f"  Null values: {null_count}",
        ])

        if samples:
            lines.extend(["", "Sample values (top 15 by frequency):"])
            for s in samples:
                val = s.get("val", "")
                cnt = s.get("cnt", 0)
                # Truncate long values
                display_val = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                lines.append(f"  '{display_val}': {cnt:,} occurrences")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("get_table_summary")
    async def get_table_summary(table_name: str) -> str:
        """Get a concise summary of a table showing only key columns.

        Shows primary keys, foreign keys, important business columns (names,
        codes, dates, status fields) without overwhelming detail. Useful for
        quickly understanding a table's purpose.

        Args:
            table_name: Name of the table to summarize.

        Returns:
            Condensed table summary with key columns only.
        """
        db = get_company_db()

        # Check table exists and get row count
        check_sql = """
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = %s AND TABLE_TYPE = 'BASE TABLE'
        """
        if not db.execute_query(check_sql, (table_name,)):
            return f"Table '{table_name}' not found."

        # Get row count
        count_sql = f"SELECT COUNT(*) FROM [{table_name}]"
        try:
            row_count = db.execute_scalar(count_sql) or 0
        except Exception:
            row_count = "unknown"

        # Get all columns
        columns_sql = """
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
                   NUMERIC_PRECISION, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """
        all_columns = db.execute_query(columns_sql, (table_name,))

        # Get primary key columns
        pk_sql = """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            WHERE tc.TABLE_NAME = %s AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ORDER BY kcu.ORDINAL_POSITION
        """
        pk_cols = [r["COLUMN_NAME"] for r in db.execute_query(pk_sql, (table_name,))]

        # Get foreign key columns
        fk_sql = """
            SELECT DISTINCT kcu.COLUMN_NAME, ccu.TABLE_NAME as REF_TABLE
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE kcu.TABLE_NAME = %s
        """
        fk_info = {r["COLUMN_NAME"]: r["REF_TABLE"] for r in db.execute_query(fk_sql, (table_name,))}

        # Categorize columns by importance
        # Key patterns for important columns
        important_patterns = [
            "Name", "Description", "Desc", "Code", "Number", "No",
            "Status", "Type", "Flag", "Date", "Amount", "Amt",
            "Qty", "Quantity", "Price", "Cost", "Value", "Total",
            "Email", "Phone", "Telephone", "Address", "Currency"
        ]

        key_columns = []
        other_columns = []

        for col in all_columns:
            col_name = col["COLUMN_NAME"]
            data_type = col["DATA_TYPE"]
            max_len = col.get("CHARACTER_MAXIMUM_LENGTH")

            # Build type string
            if max_len and max_len > 0:
                type_str = f"{data_type}({max_len})"
            else:
                type_str = data_type

            col_info = {"name": col_name, "type": type_str}

            # Determine if this is a key column
            is_key = False
            if col_name in pk_cols:
                col_info["role"] = "PK"
                is_key = True
            elif col_name in fk_info:
                col_info["role"] = f"FK->{fk_info[col_name]}"
                is_key = True
            elif any(pattern.lower() in col_name.lower() for pattern in important_patterns):
                is_key = True

            if is_key:
                key_columns.append(col_info)
            else:
                other_columns.append(col_info)

        # Build output
        module = get_module_for_table(table_name)
        lines = [
            f"Table: {table_name}",
        ]
        if module:
            lines.append(f"Module: {module}")
        lines.extend([
            f"Records: {row_count:,}" if isinstance(row_count, int) else f"Records: {row_count}",
            f"Total columns: {len(all_columns)} ({len(key_columns)} key, {len(other_columns)} other)",
            "",
            "Key Columns:",
            "-" * 60,
        ])

        for col in key_columns:
            role = f" [{col['role']}]" if "role" in col else ""
            lines.append(f"  {col['name']}: {col['type']}{role}")

        if other_columns:
            lines.extend([
                "",
                f"Other columns ({len(other_columns)}): " +
                ", ".join(c["name"] for c in other_columns[:10]) +
                ("..." if len(other_columns) > 10 else "")
            ])

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("search_data")
    async def search_data(
        search_value: str,
        table_pattern: str | None = None,
        column_pattern: str | None = None,
        limit: int = 10,
    ) -> str:
        """Search for a specific value across tables and columns.

        Finds which tables contain a specific value. Useful for tracing
        data relationships or finding where a customer/order/item is used.

        Args:
            search_value: The value to search for (exact match).
            table_pattern: Optional pattern to filter tables (e.g., 'Ar%', 'Sor%').
            column_pattern: Optional pattern to filter columns (e.g., 'Customer%').
            limit: Maximum tables to search (default 10).

        Returns:
            List of tables and columns containing the value.
        """
        db = get_company_db()

        # Find candidate columns (varchar/char types that might contain the value)
        col_sql = """
            SELECT TOP 50 c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS c
            JOIN INFORMATION_SCHEMA.TABLES t ON c.TABLE_NAME = t.TABLE_NAME
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            AND c.DATA_TYPE IN ('varchar', 'char', 'nvarchar', 'nchar')
        """
        params: list = []

        if table_pattern:
            col_sql += " AND c.TABLE_NAME LIKE %s"
            params.append(table_pattern)

        if column_pattern:
            col_sql += " AND c.COLUMN_NAME LIKE %s"
            params.append(column_pattern)

        col_sql += " ORDER BY c.TABLE_NAME, c.COLUMN_NAME"

        candidates = db.execute_query(col_sql, tuple(params) if params else None, max_rows=50)

        if not candidates:
            return "No candidate columns found matching the criteria."

        # Search each candidate
        found = []
        searched = 0

        for cand in candidates:
            if searched >= limit:
                break

            table = cand["TABLE_NAME"]
            column = cand["COLUMN_NAME"]

            # Check if value exists in this column
            search_sql = f"""
                SELECT TOP 1 1 FROM [{table}]
                WHERE [{column}] = %s
            """
            try:
                result = db.execute_query(search_sql, (search_value,), max_rows=1)
                if result:
                    # Get count
                    count_sql = f"SELECT COUNT(*) FROM [{table}] WHERE [{column}] = %s"
                    count = db.execute_scalar(count_sql, (search_value,)) or 0
                    found.append({
                        "table": table,
                        "column": column,
                        "count": count,
                    })
            except Exception:
                pass  # Skip tables/columns that can't be queried

            searched += 1

        if not found:
            return f"Value '{search_value}' not found in searched tables."

        lines = [f"Found '{search_value}' in {len(found)} location(s):\n"]
        for f in found:
            module = get_module_for_table(f["table"])
            module_str = f" [{module}]" if module else ""
            lines.append(f"  {f['table']}.{f['column']}: {f['count']} row(s){module_str}")

        if searched >= limit:
            lines.append(f"\n(Searched {searched} tables, limit reached)")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("suggest_join")
    async def suggest_join(
        table1: str,
        table2: str,
    ) -> str:
        """Suggest how to join two tables based on foreign key relationships.

        Analyzes the relationship between two tables and suggests the
        appropriate JOIN conditions.

        Args:
            table1: First table name.
            table2: Second table name.

        Returns:
            Suggested JOIN syntax and explanation.
        """
        db = get_company_db()

        # Check both tables exist
        for t in [table1, table2]:
            check_sql = "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = %s"
            if not db.execute_query(check_sql, (t,)):
                return f"Table '{t}' not found."

        # Check for direct FK from table1 to table2
        fk_sql = """
            SELECT kcu.COLUMN_NAME as FK_COL, ccu.COLUMN_NAME as PK_COL
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE kcu.TABLE_NAME = %s AND ccu.TABLE_NAME = %s
        """

        # Check table1 -> table2
        fk_1_to_2 = db.execute_query(fk_sql, (table1, table2))

        # Check table2 -> table1
        fk_2_to_1 = db.execute_query(fk_sql, (table2, table1))

        lines = [f"Join analysis: {table1} <-> {table2}\n"]

        if fk_1_to_2:
            lines.append(f"Direct relationship: {table1} references {table2}")
            join_conditions = []
            for fk in fk_1_to_2:
                join_conditions.append(f"{table1}.{fk['FK_COL']} = {table2}.{fk['PK_COL']}")

            lines.extend([
                "",
                "Suggested JOIN:",
                f"  SELECT *",
                f"  FROM {table1}",
                f"  INNER JOIN {table2}",
                f"    ON " + "\n    AND ".join(join_conditions),
            ])

        elif fk_2_to_1:
            lines.append(f"Direct relationship: {table2} references {table1}")
            join_conditions = []
            for fk in fk_2_to_1:
                join_conditions.append(f"{table2}.{fk['FK_COL']} = {table1}.{fk['PK_COL']}")

            lines.extend([
                "",
                "Suggested JOIN:",
                f"  SELECT *",
                f"  FROM {table1}",
                f"  INNER JOIN {table2}",
                f"    ON " + "\n    AND ".join(join_conditions),
            ])

        else:
            # Look for common columns (might be implicit relationship)
            common_sql = """
                SELECT c1.COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS c1
                JOIN INFORMATION_SCHEMA.COLUMNS c2
                    ON c1.COLUMN_NAME = c2.COLUMN_NAME
                    AND c1.DATA_TYPE = c2.DATA_TYPE
                WHERE c1.TABLE_NAME = %s AND c2.TABLE_NAME = %s
                AND c1.COLUMN_NAME NOT IN ('TimeStamp')
            """
            common_cols = db.execute_query(common_sql, (table1, table2))

            if common_cols:
                lines.append("No direct FK relationship found.")
                lines.append("")
                lines.append("Common columns (possible join candidates):")
                for col in common_cols:
                    lines.append(f"  - {col['COLUMN_NAME']}")

                # Suggest based on common columns
                if common_cols:
                    col = common_cols[0]["COLUMN_NAME"]
                    lines.extend([
                        "",
                        "Possible JOIN (verify relationship):",
                        f"  SELECT *",
                        f"  FROM {table1}",
                        f"  INNER JOIN {table2}",
                        f"    ON {table1}.{col} = {table2}.{col}",
                    ])
            else:
                lines.append("No direct relationship or common columns found.")
                lines.append("These tables may need an intermediate table to join.")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("get_query_template")
    async def get_query_template(query_type: str) -> str:
        """Get a template SQL query for common SYSPRO reporting needs.

        Provides ready-to-use query templates for common business questions
        like customer lists, order summaries, inventory levels, etc.

        Args:
            query_type: Type of query needed. Options:
                - customers: Customer master list
                - customer_balances: Customer balances and aging
                - sales_orders: Open sales orders
                - order_details: Sales order with line items
                - inventory: Stock levels by warehouse
                - invoices: Invoice listing
                - suppliers: Supplier master list
                - purchase_orders: Open purchase orders
                - jobs: Work in progress jobs
                - list: Show all available templates

        Returns:
            SQL query template with explanatory comments.
        """
        templates = {
            "customers": '''-- Customer Master List
SELECT
    c.Customer,
    c.Name,
    c.ShortName,
    c.CustomerClass,
    c.Salesperson,
    c.Currency,
    c.TermsCode,
    c.CreditLimit,
    c.CreditStatus,
    c.CustomerOnHold,
    c.Telephone,
    c.Email,
    c.SoldToAddr1,
    c.SoldToAddr2,
    c.SoldPostalCode,
    c.DateLastSale,
    c.DateCustAdded
FROM ArCustomer c
WHERE c.CustomerOnHold <> 'Y'
ORDER BY c.Name''',

            "customer_balances": '''-- Customer Balances and Aging
SELECT
    c.Customer,
    c.Name,
    c.CreditLimit,
    b.ValCurrentInv as CurrentBal,
    b.Val30daysInv as Over30,
    b.Val60daysInv as Over60,
    b.Val90daysInv as Over90,
    b.Val120daysInv as Over120,
    (b.ValCurrentInv + b.Val30daysInv + b.Val60daysInv +
     b.Val90daysInv + b.Val120daysInv) as TotalBalance
FROM ArCustomer c
JOIN ArCustomerBal b ON c.Customer = b.Customer
WHERE (b.ValCurrentInv + b.Val30daysInv + b.Val60daysInv +
       b.Val90daysInv + b.Val120daysInv) <> 0
ORDER BY TotalBalance DESC''',

            "sales_orders": '''-- Open Sales Orders Summary
SELECT
    m.SalesOrder,
    m.Customer,
    c.Name as CustomerName,
    m.OrderDate,
    m.ReqShipDate,
    m.OrderStatus,
    m.Warehouse,
    m.Salesperson,
    m.CustomerPoNumber,
    m.Currency
FROM SorMaster m
JOIN ArCustomer c ON m.Customer = c.Customer
WHERE m.OrderStatus NOT IN ('9', '/')
  AND m.ActiveFlag <> 'N'
ORDER BY m.OrderDate DESC''',

            "order_details": '''-- Sales Order with Line Items
SELECT
    m.SalesOrder,
    m.Customer,
    m.OrderDate,
    m.OrderStatus,
    d.SalesOrderLine,
    d.MStockCode,
    d.MStockDes,
    d.MOrderQty,
    d.MShipQty,
    d.MBackOrderQty,
    d.MPrice,
    d.MOrderQty * d.MPrice as LineTotal
FROM SorMaster m
JOIN SorDetail d ON m.SalesOrder = d.SalesOrder
WHERE m.SalesOrder = '<SALES_ORDER>'
ORDER BY d.SalesOrderLine''',

            "inventory": '''-- Inventory Levels by Warehouse
SELECT
    i.StockCode,
    i.Description,
    w.Warehouse,
    w.QtyOnHand,
    w.QtyAllocated,
    w.QtyOnHand - w.QtyAllocated as Available,
    w.QtyOnOrder,
    w.QtyInTransit,
    i.StockUom,
    i.ProductClass
FROM InvMaster i
JOIN InvWarehouse w ON i.StockCode = w.StockCode
WHERE w.QtyOnHand <> 0 OR w.QtyAllocated <> 0
ORDER BY i.StockCode, w.Warehouse''',

            "invoices": '''-- Invoice Listing (Open Invoices)
SELECT
    i.Invoice,
    i.Customer,
    c.Name as CustomerName,
    i.DocumentType,
    i.InvoiceDate,
    i.CurrencyValue,
    i.InvoiceBal1 as Balance,
    i.SalesOrder,
    i.Salesperson,
    i.TermsCode
FROM ArInvoice i
JOIN ArCustomer c ON i.Customer = c.Customer
WHERE i.InvoiceBal1 <> 0
ORDER BY i.InvoiceDate DESC''',

            "suppliers": '''-- Supplier Master List
SELECT
    s.Supplier,
    s.SupplierName,
    s.SupShortName,
    s.SupplierClass,
    s.Currency,
    s.TermsCode,
    s.Telephone,
    s.Email,
    s.Contact,
    s.CurrentBalance,
    s.OnHold,
    s.TaxRegnNum
FROM ApSupplier s
WHERE s.OnHold <> 'Y'
ORDER BY s.SupplierName''',

            "purchase_orders": '''-- Open Purchase Orders
SELECT
    p.PurchaseOrder,
    p.Supplier,
    s.SupplierName,
    p.OrderEntryDate,
    p.OrderDueDate,
    p.OrderStatus,
    p.Warehouse,
    p.Buyer,
    p.Currency
FROM PorMasterHdr p
JOIN ApSupplier s ON p.Supplier = s.Supplier
WHERE p.OrderStatus NOT IN ('9', '/')
ORDER BY p.OrderEntryDate DESC''',

            "jobs": '''-- Work in Progress Jobs
SELECT
    j.Job,
    j.StockCode,
    j.StockDescription,
    j.JobDescription,
    j.QtyToMake,
    j.QtyManufactured,
    j.JobStartDate,
    j.JobDeliveryDate,
    j.Complete,
    j.HoldFlag,
    j.Customer,
    j.SalesOrder
FROM WipMaster j
WHERE j.Complete <> 'Y'
ORDER BY j.JobDeliveryDate''',

            "stock_movements": '''-- Inventory Movements/Transactions
SELECT TOP 100
    m.StockCode,
    m.Warehouse,
    m.EntryDate,
    m.MovementType,
    m.TrnType,
    m.TrnQty,
    m.TrnValue,
    m.Reference,
    m.Job,
    m.SalesOrder,
    m.Customer
FROM InvMovements m
WHERE m.EntryDate >= DATEADD(day, -30, GETDATE())
ORDER BY m.EntryDate DESC, m.StockCode''',

            "bom_structure": '''-- Bill of Materials Structure
SELECT
    b.ParentPart,
    p.Description as ParentDescription,
    b.Component,
    c.Description as ComponentDescription,
    b.QtyPer,
    b.ScrapQuantity,
    b.ScrapPercentage,
    b.SequenceNum,
    b.Route,
    b.Warehouse
FROM BomStructure b
JOIN InvMaster p ON b.ParentPart = p.StockCode
JOIN InvMaster c ON b.Component = c.StockCode
WHERE b.ParentPart = '<STOCK_CODE>'
ORDER BY b.SequenceNum''',

            "customer_history": '''-- Customer Order History
SELECT
    c.Customer,
    c.Name,
    COUNT(DISTINCT m.SalesOrder) as OrderCount,
    SUM(d.MOrderQty * d.MPrice) as TotalSales,
    MAX(m.OrderDate) as LastOrderDate
FROM ArCustomer c
LEFT JOIN SorMaster m ON c.Customer = m.Customer
LEFT JOIN SorDetail d ON m.SalesOrder = d.SalesOrder
GROUP BY c.Customer, c.Name
HAVING COUNT(DISTINCT m.SalesOrder) > 0
ORDER BY TotalSales DESC''',

            "supplier_payables": '''-- Supplier Balances (Accounts Payable Aging)
SELECT
    s.Supplier,
    s.SupplierName,
    s.CurrentBalance,
    s.TermsCode,
    s.Currency,
    s.OnHold
FROM ApSupplier s
WHERE s.CurrentBalance <> 0
ORDER BY s.CurrentBalance DESC''',

            "low_stock": '''-- Low Stock Items (Below Minimum Quantity)
SELECT
    w.StockCode,
    i.Description,
    w.Warehouse,
    w.QtyOnHand,
    w.QtyAllocated,
    (w.QtyOnHand - w.QtyAllocated) as Available,
    w.MinimumQty,
    w.SafetyStockQty,
    w.ReOrderQty,
    w.QtyOnOrder
FROM InvWarehouse w
JOIN InvMaster i ON w.StockCode = i.StockCode
WHERE (w.QtyOnHand - w.QtyAllocated) < w.MinimumQty
  AND w.MinimumQty > 0
ORDER BY (w.QtyOnHand - w.QtyAllocated) - w.MinimumQty''',

            "sales_by_salesperson": '''-- Sales Summary by Salesperson
SELECT
    m.Salesperson,
    sp.Name as SalespersonName,
    COUNT(DISTINCT m.SalesOrder) as OrderCount,
    COUNT(DISTINCT m.Customer) as CustomerCount,
    SUM(d.MOrderQty * d.MPrice) as TotalSales
FROM SorMaster m
JOIN SorDetail d ON m.SalesOrder = d.SalesOrder
LEFT JOIN SalSalesperson sp ON m.Salesperson = sp.Salesperson
WHERE m.OrderDate >= DATEADD(month, -12, GETDATE())
GROUP BY m.Salesperson, sp.Name
ORDER BY TotalSales DESC''',

            "backorders": '''-- Backorder Report
SELECT
    d.SalesOrder,
    m.Customer,
    c.Name as CustomerName,
    d.MStockCode,
    d.MStockDes,
    d.MBackOrderQty,
    d.MPrice,
    d.MBackOrderQty * d.MPrice as BackorderValue,
    m.ReqShipDate
FROM SorDetail d
JOIN SorMaster m ON d.SalesOrder = m.SalesOrder
JOIN ArCustomer c ON m.Customer = c.Customer
WHERE d.MBackOrderQty > 0
  AND m.OrderStatus NOT IN ('9', '/')
ORDER BY m.ReqShipDate, d.SalesOrder''',

            "inventory_valuation": '''-- Inventory Valuation by Product Class
SELECT
    i.ProductClass,
    COUNT(DISTINCT w.StockCode) as ItemCount,
    SUM(w.QtyOnHand) as TotalQty,
    SUM(w.QtyOnHand * w.UnitCost) as TotalValue,
    SUM(w.QtyAllocated) as TotalAllocated,
    SUM(w.QtyOnOrder) as TotalOnOrder
FROM InvWarehouse w
JOIN InvMaster i ON w.StockCode = i.StockCode
WHERE w.QtyOnHand > 0
GROUP BY i.ProductClass
ORDER BY SUM(w.QtyOnHand * w.UnitCost) DESC''',

            "customer_profitability": '''-- Customer Profitability Analysis (12 months)
SELECT TOP 20
    c.Customer,
    c.Name,
    c.CustomerClass,
    COUNT(DISTINCT m.SalesOrder) as OrderCount,
    SUM(d.MOrderQty * d.MPrice) as GrossSales,
    SUM(d.MOrderQty * d.MUnitCost) as TotalCost,
    SUM(d.MOrderQty * d.MPrice) - SUM(d.MOrderQty * d.MUnitCost) as GrossProfit,
    CASE WHEN SUM(d.MOrderQty * d.MPrice) > 0
         THEN (SUM(d.MOrderQty * d.MPrice) - SUM(d.MOrderQty * d.MUnitCost)) / SUM(d.MOrderQty * d.MPrice) * 100
         ELSE 0 END as MarginPct
FROM ArCustomer c
JOIN SorMaster m ON c.Customer = m.Customer
JOIN SorDetail d ON m.SalesOrder = d.SalesOrder
WHERE m.OrderDate >= DATEADD(year, -1, GETDATE())
GROUP BY c.Customer, c.Name, c.CustomerClass
HAVING SUM(d.MOrderQty * d.MPrice) > 0
ORDER BY GrossSales DESC''',

            "wip_costing": '''-- Work in Progress Costing Analysis
SELECT TOP 20
    j.Job,
    j.StockCode,
    j.StockDescription,
    j.QtyToMake,
    j.QtyManufactured,
    j.ExpLabour,
    j.ExpMaterial,
    j.ExpLabour + j.ExpMaterial as TotalExpected,
    j.MatCostToDate1 + j.MatCostToDate2 + j.MatCostToDate3 as ActualMaterial,
    j.LabCostToDate1 + j.LabCostToDate2 + j.LabCostToDate3 as ActualLabour
FROM WipMaster j
WHERE j.Complete <> 'Y'
  AND (j.ExpLabour + j.ExpMaterial) > 0
ORDER BY j.ExpLabour + j.ExpMaterial DESC''',

            "order_fulfillment": '''-- Order Fulfillment by Salesperson (12 months)
SELECT
    m.Salesperson,
    COUNT(DISTINCT m.SalesOrder) as TotalOrders,
    SUM(CASE WHEN m.OrderStatus = '9' THEN 1 ELSE 0 END) as CompletedOrders,
    SUM(d.MOrderQty) as TotalQtyOrdered,
    SUM(d.MShipQty) as TotalQtyShipped,
    SUM(d.MBackOrderQty) as TotalBackordered,
    CASE WHEN SUM(d.MOrderQty) > 0
         THEN SUM(d.MBackOrderQty) / SUM(d.MOrderQty) * 100
         ELSE 0 END as BackorderPct
FROM SorMaster m
JOIN SorDetail d ON m.SalesOrder = d.SalesOrder
WHERE m.OrderDate >= DATEADD(month, -12, GETDATE())
GROUP BY m.Salesperson
ORDER BY TotalOrders DESC''',

            "stock_aging": '''-- Stock Aging Analysis (Items not sold in 6+ months)
SELECT TOP 50
    w.StockCode,
    i.Description,
    w.Warehouse,
    w.QtyOnHand,
    w.UnitCost,
    w.QtyOnHand * w.UnitCost as StockValue,
    w.DateLastSale,
    DATEDIFF(day, w.DateLastSale, GETDATE()) as DaysSinceLastSale
FROM InvWarehouse w
JOIN InvMaster i ON w.StockCode = i.StockCode
WHERE w.QtyOnHand > 0
  AND w.DateLastSale < DATEADD(month, -6, GETDATE())
ORDER BY w.QtyOnHand * w.UnitCost DESC''',

            "price_list": '''-- Price List for Stock Code
SELECT
    p.StockCode,
    i.Description,
    p.PriceCode,
    p.SellingPrice,
    p.PriceBasis,
    p.CommissionCode,
    p.Currency
FROM InvPrice p
JOIN InvMaster i ON p.StockCode = i.StockCode
WHERE p.StockCode = '<STOCK_CODE>'
ORDER BY p.PriceCode''',

            "ap_invoice_aging": '''-- Accounts Payable Aging Report
SELECT
    s.Supplier,
    s.SupplierName,
    i.Invoice,
    i.InvoiceDate,
    i.DueDate,
    i.OrigInvValue,
    (i.MthInvBal1 + i.MthInvBal2 + i.MthInvBal3) as TotalOwing,
    DATEDIFF(day, i.DueDate, GETDATE()) as DaysOverdue,
    CASE
        WHEN DATEDIFF(day, i.DueDate, GETDATE()) <= 0 THEN 'Current'
        WHEN DATEDIFF(day, i.DueDate, GETDATE()) <= 30 THEN '1-30 days'
        WHEN DATEDIFF(day, i.DueDate, GETDATE()) <= 60 THEN '31-60 days'
        WHEN DATEDIFF(day, i.DueDate, GETDATE()) <= 90 THEN '61-90 days'
        ELSE 'Over 90 days'
    END as AgingBucket
FROM ApInvoice i
JOIN ApSupplier s ON i.Supplier = s.Supplier
WHERE (i.MthInvBal1 + i.MthInvBal2 + i.MthInvBal3) > 0
ORDER BY i.DueDate''',

            "ap_supplier_summary": '''-- Supplier Summary with Total Owing
SELECT
    s.Supplier,
    s.SupplierName,
    s.SupplierClass,
    s.Currency,
    s.TermsCode,
    COUNT(i.Invoice) as InvoiceCount,
    SUM(i.MthInvBal1 + i.MthInvBal2 + i.MthInvBal3) as TotalOwing,
    MIN(i.DueDate) as OldestDueDate
FROM ApSupplier s
LEFT JOIN ApInvoice i ON s.Supplier = i.Supplier
    AND (i.MthInvBal1 + i.MthInvBal2 + i.MthInvBal3) > 0
GROUP BY s.Supplier, s.SupplierName, s.SupplierClass, s.Currency, s.TermsCode
HAVING SUM(i.MthInvBal1 + i.MthInvBal2 + i.MthInvBal3) > 0
ORDER BY TotalOwing DESC''',

            "gl_trial_balance": '''-- Trial Balance (Current Period)
SELECT
    m.GlCode,
    m.Description,
    m.AccountType,
    m.GlGroup,
    m.CurrentBalance,
    m.PtdDrValue as PeriodDebits,
    m.PtdCrValue as PeriodCredits,
    m.PtdDrValue + m.PtdCrValue as PeriodNet
FROM GenMaster m
WHERE m.CurrentBalance <> 0
   OR m.PtdDrValue <> 0
   OR m.PtdCrValue <> 0
ORDER BY m.GlCode''',

            "gl_journal_entries": '''-- GL Journal Entries (Recent)
SELECT TOP 100
    j.GlYear,
    j.GlPeriod,
    j.Journal,
    j.EntryNumber,
    j.GlCode,
    m.Description as AccountDescription,
    j.EntryValue,
    j.EntryDate,
    j.Source,
    j.Reference
FROM GenJournalDetail j
JOIN GenMaster m ON j.GlCode = m.GlCode
ORDER BY j.EntryDate DESC, j.Journal DESC''',

            "gl_account_activity": '''-- GL Account Activity for Period
SELECT
    j.GlYear,
    j.GlPeriod,
    j.Journal,
    j.EntryDate,
    j.EntryValue,
    j.Source,
    j.Reference,
    j.SubModTransDesc
FROM GenJournalDetail j
WHERE j.GlCode = '<GL_CODE>'
  AND j.GlYear = YEAR(GETDATE())
ORDER BY j.EntryDate, j.Journal''',

            "grn_receipts": '''-- Goods Received Notes (Recent)
SELECT TOP 50
    d.Grn,
    d.Supplier,
    s.SupplierName,
    d.PurchaseOrder,
    d.OrigReceiptDate,
    d.StockCode,
    d.StockDescription,
    d.QtyReceived,
    d.OrigGrnValue,
    d.Warehouse
FROM GrnDetails d
JOIN ApSupplier s ON d.Supplier = s.Supplier
ORDER BY d.OrigReceiptDate DESC, d.Grn DESC''',

            "po_receipts_pending": '''-- Purchase Orders Awaiting Receipt
SELECT
    p.PurchaseOrder,
    p.Supplier,
    s.SupplierName,
    p.OrderDueDate,
    d.MStockCode,
    d.MStockDes,
    d.MOrderQty,
    d.MReceivedQty,
    d.MOrderQty - d.MReceivedQty as QtyOutstanding,
    d.MPrice,
    (d.MOrderQty - d.MReceivedQty) * d.MPrice as OutstandingValue
FROM PorMasterHdr p
JOIN PorMasterDetail d ON p.PurchaseOrder = d.PurchaseOrder
JOIN ApSupplier s ON p.Supplier = s.Supplier
WHERE p.OrderStatus NOT IN ('9', '/')
  AND d.MOrderQty > d.MReceivedQty
ORDER BY p.OrderDueDate, p.PurchaseOrder''',

            "bank_transactions": '''-- Bank Transactions (Recent)
SELECT TOP 100
    t.Bank,
    b.Description as BankName,
    t.TrnDate,
    t.TrnType,
    t.TrnValue,
    t.TrnReference,
    t.Narration,
    t.ReconciledFlag,
    t.Supplier
FROM CshTransactions t
JOIN ApBank b ON t.Bank = b.Bank
ORDER BY t.TrnDate DESC''',

            "bank_balances": '''-- Bank Account Balances
SELECT
    b.Bank,
    b.Description,
    b.Currency,
    b.CbStmtBal1 as StatementBalance,
    b.CbStmtBalLoc1 as LocalBalance,
    (SELECT SUM(CASE WHEN t.TrnType = 'D' THEN t.TrnValue ELSE 0 END)
     FROM CshTransactions t WHERE t.Bank = b.Bank AND t.ReconciledFlag = 'N') as UnreconciledDeposits,
    (SELECT SUM(CASE WHEN t.TrnType = 'W' THEN t.TrnValue ELSE 0 END)
     FROM CshTransactions t WHERE t.Bank = b.Bank AND t.ReconciledFlag = 'N') as UnreconciledWithdrawals
FROM ApBank b
ORDER BY b.Bank''',

            "sales_by_month": '''-- Sales by Month (12 months)
SELECT
    YEAR(m.OrderDate) as OrderYear,
    MONTH(m.OrderDate) as OrderMonth,
    COUNT(DISTINCT m.SalesOrder) as OrderCount,
    COUNT(DISTINCT m.Customer) as CustomerCount,
    SUM(d.MOrderQty * d.MPrice) as GrossSales
FROM SorMaster m
JOIN SorDetail d ON m.SalesOrder = d.SalesOrder
WHERE m.OrderDate >= DATEADD(month, -12, GETDATE())
  AND m.OrderStatus NOT IN ('/')
GROUP BY YEAR(m.OrderDate), MONTH(m.OrderDate)
ORDER BY OrderYear, OrderMonth''',

            "sales_by_product_class": '''-- Sales by Product Class (12 months)
SELECT
    i.ProductClass,
    COUNT(DISTINCT d.SalesOrder) as OrderCount,
    SUM(d.MOrderQty) as TotalQty,
    SUM(d.MOrderQty * d.MPrice) as GrossSales,
    SUM(d.MOrderQty * d.MUnitCost) as TotalCost,
    SUM(d.MOrderQty * d.MPrice) - SUM(d.MOrderQty * d.MUnitCost) as GrossProfit
FROM SorDetail d
JOIN SorMaster m ON d.SalesOrder = m.SalesOrder
JOIN InvMaster i ON d.MStockCode = i.StockCode
WHERE m.OrderDate >= DATEADD(month, -12, GETDATE())
  AND m.OrderStatus NOT IN ('/')
GROUP BY i.ProductClass
ORDER BY GrossSales DESC''',

            "inventory_turnover": '''-- Inventory Turnover Analysis
SELECT TOP 50
    w.StockCode,
    i.Description,
    i.ProductClass,
    w.Warehouse,
    w.QtyOnHand,
    w.UnitCost,
    w.QtyOnHand * w.UnitCost as StockValue,
    (SELECT SUM(ABS(TrnQty)) FROM InvMovements m
     WHERE m.StockCode = w.StockCode AND m.Warehouse = w.Warehouse
     AND m.TrnType IN ('I', 'R') AND m.EntryDate >= DATEADD(month, -12, GETDATE())) as YearlyMovement,
    CASE WHEN w.QtyOnHand > 0 THEN
        (SELECT SUM(ABS(TrnQty)) FROM InvMovements m
         WHERE m.StockCode = w.StockCode AND m.Warehouse = w.Warehouse
         AND m.TrnType IN ('I', 'R') AND m.EntryDate >= DATEADD(month, -12, GETDATE())) / w.QtyOnHand
    ELSE 0 END as TurnoverRatio
FROM InvWarehouse w
JOIN InvMaster i ON w.StockCode = i.StockCode
WHERE w.QtyOnHand > 0
ORDER BY w.QtyOnHand * w.UnitCost DESC''',

            "customer_credit_analysis": '''-- Customer Credit Analysis
SELECT
    c.Customer,
    c.Name,
    c.CreditLimit,
    c.CreditStatus,
    c.CustomerOnHold,
    b.ValCurrentInv + b.Val30daysInv + b.Val60daysInv + b.Val90daysInv + b.Val120daysInv as TotalBalance,
    c.CreditLimit - (b.ValCurrentInv + b.Val30daysInv + b.Val60daysInv + b.Val90daysInv + b.Val120daysInv) as AvailableCredit,
    CASE WHEN c.CreditLimit > 0 THEN
        (b.ValCurrentInv + b.Val30daysInv + b.Val60daysInv + b.Val90daysInv + b.Val120daysInv) / c.CreditLimit * 100
    ELSE 0 END as CreditUtilizationPct,
    b.Val90daysInv + b.Val120daysInv as OverdueAmount
FROM ArCustomer c
JOIN ArCustomerBal b ON c.Customer = b.Customer
WHERE c.CreditLimit > 0
  AND (b.ValCurrentInv + b.Val30daysInv + b.Val60daysInv + b.Val90daysInv + b.Val120daysInv) > 0
ORDER BY CreditUtilizationPct DESC''',

            "top_selling_items": '''-- Top Selling Items (12 months)
SELECT TOP 50
    d.MStockCode as StockCode,
    i.Description,
    i.ProductClass,
    COUNT(DISTINCT d.SalesOrder) as OrderCount,
    SUM(d.MOrderQty) as TotalQtySold,
    SUM(d.MOrderQty * d.MPrice) as TotalSales,
    SUM(d.MOrderQty * d.MPrice) - SUM(d.MOrderQty * d.MUnitCost) as GrossProfit
FROM SorDetail d
JOIN SorMaster m ON d.SalesOrder = m.SalesOrder
JOIN InvMaster i ON d.MStockCode = i.StockCode
WHERE m.OrderDate >= DATEADD(month, -12, GETDATE())
  AND m.OrderStatus NOT IN ('/')
GROUP BY d.MStockCode, i.Description, i.ProductClass
ORDER BY TotalSales DESC''',

            "supplier_performance": '''-- Supplier Performance (On-time delivery)
SELECT TOP 30
    p.Supplier,
    s.SupplierName,
    COUNT(DISTINCT p.PurchaseOrder) as TotalPOs,
    COUNT(DISTINCT CASE WHEN p.OrderStatus = '9' THEN p.PurchaseOrder END) as CompletedPOs,
    SUM(d.MOrderQty * d.MPrice) as TotalPOValue,
    SUM(d.MReceivedQty * d.MPrice) as TotalReceivedValue
FROM PorMasterHdr p
JOIN PorMasterDetail d ON p.PurchaseOrder = d.PurchaseOrder
JOIN ApSupplier s ON p.Supplier = s.Supplier
WHERE p.OrderEntryDate >= DATEADD(month, -12, GETDATE())
GROUP BY p.Supplier, s.SupplierName
ORDER BY TotalPOValue DESC''',

            "ar_customer_receipts": '''-- Customer Receipts/Payments (Recent)
SELECT TOP 100
    p.Bank,
    b.Description as BankName,
    p.CbTrnDate as PaymentDate,
    p.Customer,
    c.Name as CustomerName,
    p.Invoice,
    p.DocumentType,
    p.GrossPayment,
    p.DiscountAllowed,
    p.NetPayment,
    p.PaymentNumber
FROM CshArPayments p
JOIN ApBank b ON p.Bank = b.Bank
JOIN ArCustomer c ON p.Customer = c.Customer
ORDER BY p.CbTrnDate DESC''',

            "serial_inventory": '''-- Serialized Items On Hand
SELECT TOP 100
    h.StockCode,
    i.Description,
    h.Warehouse,
    h.Serial,
    h.SerialDescription,
    h.QtyOnHand,
    h.QtyAvailable,
    h.DateCreated,
    h.ExpiryDate,
    h.Customer
FROM InvSerialHead h
JOIN InvMaster i ON h.StockCode = i.StockCode
WHERE h.QtyOnHand > 0
ORDER BY h.DateCreated DESC''',

            "serial_transactions": '''-- Serial Number Transaction History
SELECT TOP 100
    t.StockCode,
    t.Serial,
    t.EntryDate,
    t.DetailType,
    t.Warehouse,
    t.TrnQty,
    t.TrnValue,
    t.Notation,
    t.SalesOrder,
    t.CustSupplier,
    t.CustSupName
FROM InvSerialTrn t
ORDER BY t.EntryDate DESC, t.StockCode, t.Serial''',
        }

        query_type_lower = query_type.lower().strip()

        if query_type_lower == "list":
            lines = ["Available query templates:\n"]
            descriptions = {
                "customers": "Customer master list with key fields",
                "customer_balances": "Customer balances and aging analysis",
                "sales_orders": "Open sales orders summary",
                "order_details": "Sales order with line item details",
                "inventory": "Stock levels by warehouse",
                "invoices": "Open invoice listing",
                "suppliers": "Supplier master list",
                "purchase_orders": "Open purchase orders",
                "jobs": "Work in progress / manufacturing jobs",
                "stock_movements": "Recent inventory transactions (last 30 days)",
                "bom_structure": "Bill of Materials for a stock code",
                "customer_history": "Customer order history with totals",
                "supplier_payables": "Suppliers with outstanding balances",
                "low_stock": "Items below minimum quantity level",
                "sales_by_salesperson": "Sales summary by salesperson (12 months)",
                "backorders": "Backorder report with values",
                "inventory_valuation": "Inventory value by product class",
                "customer_profitability": "Customer margin analysis (12 months)",
                "wip_costing": "Job costing - expected vs actual",
                "order_fulfillment": "Fulfillment metrics by salesperson",
                "stock_aging": "Slow-moving inventory (6+ months)",
                "price_list": "Price list for a stock code",
                "ap_invoice_aging": "AP invoice aging with aging buckets",
                "ap_supplier_summary": "Supplier summary with outstanding totals",
                "gl_trial_balance": "Trial balance with period activity",
                "gl_journal_entries": "Recent GL journal entries",
                "gl_account_activity": "Activity for specific GL account",
                "grn_receipts": "Recent goods received notes",
                "po_receipts_pending": "PO lines awaiting receipt",
                "bank_transactions": "Recent bank/cashbook transactions",
                "bank_balances": "Bank account balances with unreconciled items",
                "sales_by_month": "Monthly sales trend (12 months)",
                "sales_by_product_class": "Sales analysis by product class",
                "inventory_turnover": "Inventory turnover ratio analysis",
                "customer_credit_analysis": "Customer credit utilization and risk",
                "top_selling_items": "Top selling items by revenue",
                "supplier_performance": "Supplier performance and PO analysis",
                "ar_customer_receipts": "Customer payments/receipts received",
                "serial_inventory": "Serialized items currently on hand",
                "serial_transactions": "Serial number transaction history",
            }
            for name, desc in descriptions.items():
                lines.append(f"  {name}: {desc}")
            lines.append("\nUse get_query_template('<name>') to get the SQL.")
            return "\n".join(lines)

        if query_type_lower not in templates:
            available = ", ".join(templates.keys())
            return f"Unknown query type: '{query_type}'.\n\nAvailable types: {available}\n\nUse 'list' to see descriptions."

        return templates[query_type_lower]

    @mcp.tool()
    @audit_tool_call("get_syspro_help")
    async def get_syspro_help(topic: str) -> str:
        """Get quick help on common SYSPRO questions and concepts.

        Provides domain knowledge about SYSPRO tables, relationships,
        and common patterns to help users navigate the database.

        Args:
            topic: Topic to get help on (e.g., 'customer', 'inventory', 'pricing')
                   Use 'list' to see all available topics.

        Returns:
            Helpful information about the topic.
        """
        help_topics = {
            "customer": """## Customer Data in SYSPRO

**Main Tables:**
- `ArCustomer` - Customer master file (addresses, terms, credit info)
- `ArCustomerBal` - Customer balances and aging buckets
- `ArInvoice` - Open invoices
- `ArMultAddress` - Multiple ship-to addresses

**Key Columns:**
- `Customer` - Customer code (primary key)
- `Name` - Customer name
- `CreditLimit` - Credit limit
- `CustomerOnHold` - Y/N flag
- `CreditStatus` - 0=OK, 4=Referral, 6=Special terms

**Common Joins:**
- ArCustomer -> ArCustomerBal ON Customer
- ArCustomer -> SorMaster ON Customer (sales orders)
- ArCustomer -> ArInvoice ON Customer""",

            "inventory": """## Inventory Data in SYSPRO

**Main Tables:**
- `InvMaster` - Stock code master (descriptions, UOM, costs)
- `InvWarehouse` - Stock by warehouse (quantities, costs)
- `InvMovements` - Transaction history
- `InvBin` - Bin locations

**Key Columns (InvMaster):**
- `StockCode` - Item code (primary key)
- `Description` - Item description
- `StockUom` - Unit of measure
- `ProductClass` - Product classification

**Key Columns (InvWarehouse):**
- `QtyOnHand` - Physical quantity
- `QtyAllocated` - Allocated to orders
- `QtyOnOrder` - On purchase orders
- `UnitCost` - Average unit cost

**Common Joins:**
- InvMaster -> InvWarehouse ON StockCode
- InvWarehouse -> SorDetail ON StockCode (order lines)""",

            "sales_order": """## Sales Orders in SYSPRO

**Main Tables:**
- `SorMaster` - Sales order header
- `SorDetail` - Sales order line items
- `SorQuote` - Quotations

**Key Columns (SorMaster):**
- `SalesOrder` - Order number (primary key)
- `Customer` - Customer code
- `OrderDate` - Date entered
- `OrderStatus` - 1=Entered, 2=Released, 4=Part shipped, 9=Complete, /=Cancelled
- `ActiveFlag` - Y/N

**Key Columns (SorDetail):**
- `MStockCode` - Stock code
- `MOrderQty` - Quantity ordered
- `MShipQty` - Quantity shipped
- `MBackOrderQty` - Backorder quantity
- `MPrice` - Unit price

**Common Joins:**
- SorMaster -> SorDetail ON SalesOrder
- SorMaster -> ArCustomer ON Customer""",

            "purchase_order": """## Purchase Orders in SYSPRO

**Main Tables:**
- `PorMasterHdr` - PO header
- `PorMasterDetail` - PO line items
- `GrnDetails` - Goods received notes

**Key Columns (PorMasterHdr):**
- `PurchaseOrder` - PO number (primary key)
- `Supplier` - Supplier code
- `OrderEntryDate` - Date entered
- `OrderDueDate` - Expected delivery
- `OrderStatus` - 1=Entered, 2=Printed, 9=Complete, /=Cancelled

**Key Columns (PorMasterDetail):**
- `MStockCode` - Stock code
- `MOrderQty` - Quantity ordered
- `MReceivedQty` - Quantity received
- `MPrice` - Unit price

**Common Joins:**
- PorMasterHdr -> PorMasterDetail ON PurchaseOrder
- PorMasterHdr -> ApSupplier ON Supplier""",

            "supplier": """## Supplier Data in SYSPRO

**Main Tables:**
- `ApSupplier` - Supplier master file
- `ApSupplierAddr` - Remittance addresses
- `ApInvoice` - AP invoices

**Key Columns:**
- `Supplier` - Supplier code (primary key)
- `SupplierName` - Supplier name
- `CurrentBalance` - Outstanding balance
- `OnHold` - Y/N flag
- `TermsCode` - Payment terms

**Common Joins:**
- ApSupplier -> PorMasterHdr ON Supplier
- ApSupplier -> ApInvoice ON Supplier""",

            "job": """## Work in Progress (Jobs) in SYSPRO

**Main Tables:**
- `WipMaster` - Job header
- `WipJobAllMat` - Allocated materials
- `WipJobAllLab` - Allocated labor

**Key Columns (WipMaster):**
- `Job` - Job number (primary key)
- `StockCode` - Item being manufactured
- `QtyToMake` - Planned quantity
- `QtyManufactured` - Completed quantity
- `JobStartDate` - Start date
- `JobDeliveryDate` - Due date
- `Complete` - Y/N flag

**Common Joins:**
- WipMaster -> InvMaster ON StockCode
- WipMaster -> SorMaster ON SalesOrder (if linked to sales order)""",

            "bom": """## Bill of Materials in SYSPRO

**Main Tables:**
- `BomStructure` - BOM parent-child relationships
- `BomRoute` - Routing definitions
- `BomOperation` - Operation steps

**Key Columns (BomStructure):**
- `ParentPart` - Parent stock code
- `Component` - Component stock code
- `QtyPer` - Quantity per parent
- `ScrapQty` - Scrap allowance
- `Sequence` - Sequence number

**Common Joins:**
- BomStructure -> InvMaster (ParentPart) ON StockCode
- BomStructure -> InvMaster (Component) ON StockCode""",

            "pricing": """## Pricing in SYSPRO

**Main Tables:**
- `InvPrice` - Inventory price list
- `SorPriceCode` - Sales order pricing
- `ArCstStkPrc` - Customer-specific pricing
- `TblPriceCode` - Price code definitions

**Key Concepts:**
- Price codes define different price levels (retail, wholesale, etc.)
- Customer-specific pricing overrides standard prices
- Contract pricing for specific date ranges

**Common Queries:**
- Check InvPrice for standard prices
- Check ArCstStkPrc for customer-specific prices""",

            "gl": """## General Ledger in SYSPRO

**Main Tables:**
- `GenMaster` - GL account master (balances, period activity)
- `GenJournalDetail` - Posted journal entries (the transaction detail)
- `GenHistory` - Historical period balances by year
- `GenBudgets` - Budget data

**Key Columns (GenMaster):**
- `GlCode` - GL account code (primary key)
- `Description` - Account description
- `AccountType` - A=Asset, L=Liability, C=Capital/Equity, R=Revenue, E=Expense
- `GlGroup` - Account grouping
- `CurrentBalance` - Current account balance
- `PtdDrValue`, `PtdCrValue` - Period-to-date debits/credits

**Key Columns (GenJournalDetail):**
- `GlYear`, `GlPeriod` - Fiscal year and period
- `Journal`, `EntryNumber` - Journal and entry identifiers
- `GlCode` - Account code
- `EntryValue` - Transaction amount
- `EntryDate` - Entry date
- `Source` - Source module code
- `Reference` - Document reference

**Common Joins:**
- GenMaster -> GenJournalDetail ON GlCode
- GenMaster -> GenHistory ON GlCode""",

            "ap": """## Accounts Payable in SYSPRO

**Main Tables:**
- `ApSupplier` - Supplier master file
- `ApInvoice` - AP invoices (open and history)
- `ApMultAddress` - Multiple remittance addresses

**Key Columns (ApSupplier):**
- `Supplier` - Supplier code (primary key)
- `SupplierName` - Full name
- `SupShortName` - Short name
- `CurrentBalance` - Total outstanding
- `OnHold` - Y/N on hold flag
- `TermsCode` - Payment terms code
- `Currency` - Trading currency

**Key Columns (ApInvoice):**
- `Supplier`, `Invoice` - Primary key
- `InvoiceDate`, `DueDate` - Key dates
- `OrigInvValue` - Original invoice value
- `MthInvBal1`, `MthInvBal2`, `MthInvBal3` - Aging buckets
- `InvoiceStatus` - 0=Open, 1=Part paid, 9=Paid, D=Disputed

**Common Joins:**
- ApSupplier -> ApInvoice ON Supplier
- ApSupplier -> PorMasterHdr ON Supplier""",

            "movements": """## Inventory Movements in SYSPRO

**Main Table:** `InvMovements`

**Key Columns:**
- `StockCode`, `Warehouse` - Item and location
- `EntryDate` - Transaction date
- `MovementType` - I=Inventory, S=Sales
- `TrnType` - Transaction type (see below)
- `TrnQty` - Quantity (+/-)
- `TrnValue` - Value amount
- `Reference` - Source document
- `Job`, `SalesOrder` - Linked documents

**TrnType Codes:**
- A = Adjustment (stock take/manual)
- B = Beginning balance
- C = Cost adjustment
- I = Issue to WIP job
- R = Receipt from GRN/PO
- T = Transfer between warehouses

**Useful Queries:**
- Stock movements by date range
- Issue analysis by job
- Receipt history by stock code""",

            "cashbook": """## Cash Book / Bank in SYSPRO

**Main Tables:**
- `CshTransactions` - Bank transactions (deposits, withdrawals)
- `ApBank` - Bank account master file
- `CshApPayments` - AP payment details
- `CshArPayments` - AR customer receipt details

**Key Columns (CshTransactions):**
- `Bank` - Bank account code
- `TrnDate` - Transaction date
- `TrnType` - D=Deposit, W=Withdrawal
- `TrnValue` - Transaction amount
- `TrnReference` - Reference/cheque number
- `Narration` - Description
- `ReconciledFlag` - Y/N reconciliation status
- `Supplier` - Linked supplier (for payments)

**Key Columns (ApBank):**
- `Bank` - Bank code (primary key)
- `Description` - Bank account name
- `Currency` - Account currency
- `CbStmtBal1` - Statement balance

**Common Joins:**
- CshTransactions -> ApBank ON Bank
- CshApPayments -> ApSupplier ON Supplier
- CshArPayments -> ArCustomer ON Customer""",

            "serial": """## Serial Number Tracking in SYSPRO

**Main Tables:**
- `InvSerialHead` - Serial number master (current status)
- `InvSerialTrn` - Serial transaction history
- `InvDocumentSerial` - Serial numbers on documents

**Key Columns (InvSerialHead):**
- `StockCode`, `Warehouse`, `Bin`, `Serial` - Primary key
- `SerialDescription` - Serial number description
- `QtyOnHand`, `QtyAvailable` - Current quantities (usually 1)
- `DateCreated` - When serial was created
- `ExpiryDate`, `ScrapDate` - Expiry tracking
- `Customer` - If assigned to customer
- `Lot`, `Version`, `Release` - Lot tracking links

**Key Columns (InvSerialTrn):**
- `StockCode`, `Serial`, `EntryDate`, `Line` - Primary key
- `DetailType` - Transaction type (SALES, DISP, RECV, ISSUE, etc.)
- `TrnQty` - Quantity (+/- usually 1)
- `TrnValue` - Value amount
- `Notation` - Transaction description
- `SalesOrder`, `PurchaseOrder`, `Job` - Linked documents
- `CustSupplier`, `CustSupName` - Customer/supplier info

**DetailType Codes:**
- SALES = Sale to customer
- DISP = Dispatch/shipment
- RECV = Receipt from purchase
- ISSUE = Issue to WIP job
- TRANS = Transfer between warehouses
- WIPRC = WIP receipt (production)

**Common Queries:**
- Find serial number location: Query InvSerialHead WHERE QtyOnHand > 0
- Track serial history: Query InvSerialTrn for full transaction trail
- Serial by customer: Check Customer column in InvSerialHead""",

            "list": """## Available Help Topics

Use `get_syspro_help('<topic>')` with one of:

**Core Data:**
- `customer` - Customer master and balances
- `supplier` - Supplier master and payables
- `inventory` - Stock codes and warehouse quantities
- `ap` - Accounts Payable invoices and aging

**Transactions:**
- `sales_order` - Sales orders and line items
- `purchase_order` - Purchase orders and receipts
- `job` - Work in progress / manufacturing
- `movements` - Inventory transaction codes
- `cashbook` - Bank accounts and transactions
- `serial` - Serial number tracking

**Reference:**
- `bom` - Bill of Materials structure
- `pricing` - Price lists and customer pricing
- `gl` - General Ledger accounts and journals

**Tips:**
- Use `search_tables` to find tables by business concept
- Use `get_table_schema` for detailed column info
- Use `get_lookup_value` to decode status codes
- Use `get_query_template('list')` for ready-to-use SQL""",
        }

        topic_lower = topic.lower().strip()

        if topic_lower not in help_topics:
            return f"Unknown topic: '{topic}'\n\nUse get_syspro_help('list') to see available topics."

        return help_topics[topic_lower]
