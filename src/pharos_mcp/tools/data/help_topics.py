"""
SYSPRO help topics and documentation.

Provides domain knowledge about SYSPRO tables, relationships,
and common patterns to help users navigate the database.
"""

HELP_TOPICS = {
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

    "analytics": """## Business Analytics in SYSPRO

**Available Analytics Tools:**
- `get_kpi_dashboard` - Key metrics at a glance (DSO, DIO, DPO, CCC)
- `analyze_customer_health` - Churn risk, late payers, concentration
- `analyze_inventory_health` - Turnover, aging, problem areas
- `analyze_product_profitability` - Margins by product class
- `get_data_quality_report` - Data issues affecting reporting

**Key Performance Indicators:**
- DSO (Days Sales Outstanding): AR / Daily Sales
- DIO (Days Inventory Outstanding): Inventory / Daily COGS
- DPO (Days Payable Outstanding): AP / Daily Purchases
- CCC (Cash Conversion Cycle): DSO + DIO - DPO

**Common Analysis Patterns:**

Customer Churn Risk:
```sql
SELECT Customer, DATEDIFF(day, DateLastSale, GETDATE()) as DaysSinceOrder
FROM ArCustomer WHERE DateLastSale < DATEADD(day, -90, GETDATE())
```

Product Profitability (using inventory costs):
```sql
SELECT i.ProductClass,
       SUM(d.MOrderQty * d.MPrice) as Revenue,
       SUM(d.MOrderQty * w.UnitCost) as Cost
FROM SorDetail d
JOIN InvMaster i ON d.MStockCode = i.StockCode
LEFT JOIN InvWarehouse w ON d.MStockCode = w.StockCode
GROUP BY i.ProductClass
```

**Data Quality Notes:**
- SO line costs (MUnitCost) often not populated - use InvWarehouse.UnitCost
- Old POs may remain open - filter by date for accurate analysis
- Job variances can be extreme - indicates estimation issues""",

    "financials": """## Financial Reporting in SYSPRO

**IMPORTANT: GL Group structures vary by implementation!**

Different SYSPRO implementations use different GL group numbering schemes.
Some use 01xx/02xx/03xx patterns, others use 1000/2000/3000, etc.

**Recommended Tools:**
- `discover_gl_structure` - See YOUR actual GL group patterns
- `generate_income_statement` - Auto-detects your GL structure
- `compare_periods` - Year-over-year comparison

**Main Tables:**
- `GenMaster` - GL account master (current balances)
- `GenHistory` - Historical period balances by year
- `GenGroups` - GL group descriptions
- `GenJournalDetail` - Posted journal entries

**Key Columns (GenMaster):**
- `GlCode` - Account code (primary key)
- `AccountType` - A=Asset, L=Liability, C=Capital, R=Revenue, E=Expense
- `GlGroup` - Account grouping
- `CurrentBalance` - Current period balance
- `PtdDrValue`, `PtdCrValue` - Period debits/credits

**Key Columns (GenHistory):**
- `GlYear` - Fiscal year
- `BeginYearBalance` - Opening balance
- `ClosingBalPer1` through `ClosingBalPer12` - Period closing balances

**Income Statement Logic:**
- Revenue accounts (AccountType=R) have CREDIT balances (negative)
- Expense accounts (AccountType=E) have DEBIT balances (positive)
- To display properly: negate revenue, keep expenses as-is

**Tips:**
- Use `generate_income_statement(year=2024)` for any year
- Use `generate_income_statement(include_quarters=True)` for quarterly view
- Use `generate_income_statement(detailed=True)` to see GL group breakdown
- Static templates may need adjustment - use dynamic tools instead""",

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
- `financials` - Income statement and financial reporting
- `analytics` - KPIs, dashboards, and business analysis

**Tips:**
- Use `search_tables` to find tables by business concept
- Use `get_table_schema` for detailed column info
- Use `get_lookup_value` to decode status codes
- Use `get_query_template('list')` for ready-to-use SQL""",
}

# Topic aliases for common variations
TOPIC_ALIASES = {
    "general ledger": "gl",
    "generalledger": "gl",
    "general_ledger": "gl",
    "ledger": "gl",
    "customers": "customer",
    "suppliers": "supplier",
    "vendors": "supplier",
    "vendor": "supplier",
    "stock": "inventory",
    "items": "inventory",
    "parts": "inventory",
    "sales orders": "sales_order",
    "salesorders": "sales_order",
    "sales": "sales_order",
    "orders": "sales_order",
    "purchase orders": "purchase_order",
    "purchaseorders": "purchase_order",
    "pos": "purchase_order",
    "po": "purchase_order",
    "purchasing": "purchase_order",
    "jobs": "job",
    "manufacturing": "job",
    "wip": "job",
    "work in progress": "job",
    "workinprogress": "job",
    "bill of materials": "bom",
    "billofmaterials": "bom",
    "bills": "bom",
    "prices": "pricing",
    "price": "pricing",
    "accounts payable": "ap",
    "accountspayable": "ap",
    "payables": "ap",
    "accounts receivable": "customer",
    "accountsreceivable": "customer",
    "ar": "customer",
    "receivables": "customer",
    "bank": "cashbook",
    "banking": "cashbook",
    "cash": "cashbook",
    "transactions": "movements",
    "movement": "movements",
    "serials": "serial",
    "serial numbers": "serial",
    "serialnumbers": "serial",
    "lot": "serial",
    "lots": "serial",
    "financial": "financials",
    "income statement": "financials",
    "incomestatement": "financials",
    "income_statement": "financials",
    "profit and loss": "financials",
    "profitandloss": "financials",
    "pnl": "financials",
    "p&l": "financials",
    "kpi": "analytics",
    "kpis": "analytics",
    "dashboard": "analytics",
    "metrics": "analytics",
    "analysis": "analytics",
    "bi": "analytics",
    "business intelligence": "analytics",
}
