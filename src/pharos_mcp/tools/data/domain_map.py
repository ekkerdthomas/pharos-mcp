"""
SYSPRO domain knowledge: maps business concepts to table prefixes.

This enables intelligent table searches - when a user searches for
"customer", the system knows to look for Ar*, ArCustomer*, CusSor* tables.
"""

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
