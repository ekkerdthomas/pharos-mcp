"""
SQL query templates for common SYSPRO reporting needs.

Ready-to-use queries for customers, sales, inventory, financials, etc.
"""

QUERY_TEMPLATES = {
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

    "income_statement": '''-- Income Statement (Current Period)
-- Revenue (GlGroup 01xx) - shown as positive
-- Cost of Sales (GlGroup 02xx) - shown as expense
-- Other Income (GlGroup 03xx) - shown as positive
-- Operating Expenses (GlGroup 04xx) - shown as expense
-- Taxation (GlGroup 07xx) - shown as expense
SELECT
    CASE
        WHEN g.GlGroup LIKE '01%' THEN '1-REVENUE'
        WHEN g.GlGroup LIKE '02%' THEN '2-COST OF SALES'
        WHEN g.GlGroup LIKE '03%' THEN '3-OTHER INCOME'
        WHEN g.GlGroup LIKE '04%' THEN '4-OPERATING EXPENSES'
        WHEN g.GlGroup LIKE '07%' THEN '5-TAXATION'
    END as Section,
    gg.Description as LineItem,
    CASE
        WHEN g.GlGroup LIKE '01%' OR g.GlGroup LIKE '03%' THEN -SUM(g.CurrentBalance)
        ELSE SUM(g.CurrentBalance)
    END as Amount
FROM GenMaster g
LEFT JOIN GenGroups gg ON g.GlGroup = gg.GlGroup AND g.Company = gg.Company
WHERE g.GlGroup LIKE '0[1-7]%'
GROUP BY g.GlGroup, gg.Description
HAVING SUM(g.CurrentBalance) <> 0
ORDER BY 1, 2''',

    "income_statement_summary": '''-- Income Statement Summary Totals
SELECT
    'Revenue' as Category,
    -SUM(CurrentBalance) as Amount
FROM GenMaster WHERE GlGroup LIKE '01%'
UNION ALL
SELECT
    'Cost of Sales' as Category,
    SUM(CurrentBalance) as Amount
FROM GenMaster WHERE GlGroup LIKE '02%'
UNION ALL
SELECT
    'Gross Profit' as Category,
    -SUM(CASE WHEN GlGroup LIKE '01%' THEN CurrentBalance ELSE 0 END)
    - SUM(CASE WHEN GlGroup LIKE '02%' THEN CurrentBalance ELSE 0 END) as Amount
FROM GenMaster WHERE GlGroup LIKE '0[12]%'
UNION ALL
SELECT
    'Other Income' as Category,
    -SUM(CurrentBalance) as Amount
FROM GenMaster WHERE GlGroup LIKE '03%'
UNION ALL
SELECT
    'Operating Expenses' as Category,
    SUM(CurrentBalance) as Amount
FROM GenMaster WHERE GlGroup LIKE '04%'
UNION ALL
SELECT
    'Taxation' as Category,
    SUM(CurrentBalance) as Amount
FROM GenMaster WHERE GlGroup LIKE '07%'
UNION ALL
SELECT
    'Net Profit' as Category,
    -SUM(CASE WHEN GlGroup LIKE '01%' OR GlGroup LIKE '03%' THEN CurrentBalance ELSE 0 END)
    - SUM(CASE WHEN GlGroup LIKE '02%' OR GlGroup LIKE '04%' OR GlGroup LIKE '07%' THEN CurrentBalance ELSE 0 END) as Amount
FROM GenMaster WHERE GlGroup LIKE '0[1-7]%' ''',

    "balance_sheet": '''-- Balance Sheet (Current Period)
-- Assets (AccountType A) - shown as positive
-- Liabilities (AccountType L) - shown as positive
-- Capital/Equity (AccountType C) - shown as positive
SELECT
    CASE m.AccountType
        WHEN 'A' THEN '1-ASSETS'
        WHEN 'L' THEN '2-LIABILITIES'
        WHEN 'C' THEN '3-EQUITY'
    END as Section,
    m.AccountType,
    g.Description as GroupDescription,
    SUM(CASE
        WHEN m.AccountType = 'A' THEN m.CurrentBalance
        ELSE -m.CurrentBalance
    END) as Amount
FROM GenMaster m
LEFT JOIN GenGroups g ON m.GlGroup = g.GlGroup AND m.Company = g.Company
WHERE m.AccountType IN ('A', 'L', 'C')
GROUP BY m.AccountType, m.GlGroup, g.Description
HAVING SUM(m.CurrentBalance) <> 0
ORDER BY 1, m.GlGroup''',
}

# Descriptions for the 'list' command
TEMPLATE_DESCRIPTIONS = {
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
    "income_statement": "Income statement by GL group (current period)",
    "income_statement_summary": "Income statement summary totals",
    "balance_sheet": "Balance sheet by account type (current period)",
}
