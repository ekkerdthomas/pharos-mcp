"""
SYSPRO module descriptions and prefix mappings.

Maps SYSPRO table prefixes to their full module names.
"""

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


def get_module_for_table(table_name: str) -> str:
    """Get the SYSPRO module for a table based on its prefix."""
    for prefix, description in SYSPRO_MODULES.items():
        if table_name.startswith(prefix):
            return f"{prefix} ({description})"
    return ""
