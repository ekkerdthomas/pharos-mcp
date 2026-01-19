"""
SYSPRO lookup table mappings and status code definitions.

Contains:
- SYSPRO_LOOKUP_TABLES: Maps lookup types to (table, code_column, description_column)
- SYSPRO_STATUS_CODES: Static code definitions for status fields
"""

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
