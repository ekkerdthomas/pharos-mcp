# PhX SYSPRO Business Object Schemas

XML Schema Definition (XSD) files for SYSPRO business objects used by PhX API tools.

## Schema Naming Convention

- `{BO}.XSD` - Parameters schema (options, filters, settings)
- `{BO}DOC.XSD` - Document schema (data payload)

## Query Business Objects

| BO Code | Description | Schemas |
|---------|-------------|---------|
| INVQRY | Inventory Query | INVQRY.XSD |
| WIPQRY | WIP Job Query | WIPQRY.XSD |
| WIPQVA | WIP Variance/Tracking Query | WIPQVA.XSD |
| WIPQ40 | WIP Multi-level Job Query | WIPQ40.XSD |
| PORQRQ | Requisition Query | PORQRQ.XSD |
| INVQGD | Goods In Transit Query | INVQGD.XSD |

## Transaction Business Objects

| BO Code | Description | Schemas |
|---------|-------------|---------|
| WIPTLP | Post Labour | WIPTLP.XSD, WIPTLPDOC.XSD |
| WIPTJR | Post Job Receipt | WIPTJR.XSD, WIPTJRDOC.XSD |
| WIPTMI | Post Material Issue | WIPTMI.XSD, WIPTMIDOC.XSD |
| PORTRA | Requisition Approve/Clear | PORTRA.XSD, PORTRADOC.XSD |
| PORTRR | Requisition Route | PORTRR.XSD, PORTRRDOC.XSD |

## Inventory Movement Business Objects

| BO Code | Description | Schemas |
|---------|-------------|---------|
| INVTMA | Inventory Adjustment | INVTMA.XSD, INVTMADOC.XSD |
| INVTMO | Warehouse Transfer Out | INVTMO.XSD, INVTMODOC.XSD |
| INVTMI | Warehouse Transfer In | INVTMI.XSD, INVTMIDOC.XSD |
| INVTMB | Bin Transfer | INVTMB.XSD, INVTMBDOC.XSD |
| INVTMT | GIT Transfer Out | INVTMT.XSD, INVTMTDOC.XSD |
| INVTMN | GIT Transfer In | INVTMN.XSD, INVTMNDOC.XSD |

## Usage with phx_call_business_object

When using the generic `phx_call_business_object` tool, refer to these schemas for:
- Required vs optional elements
- Valid values for option fields
- Data types and field lengths

Example for WIPTLP (Post Labour):
```xml
<!-- Parameters (WIPTLP.XSD) -->
<PostLabour>
  <Parameters>
    <TransactionDate></TransactionDate>
    <IgnoreWarnings>N</IgnoreWarnings>
    <ApplyIfEntireDocumentValid>Y</ApplyIfEntireDocumentValid>
    <ValidateOnly>N</ValidateOnly>
  </Parameters>
</PostLabour>

<!-- Document (WIPTLPDOC.XSD) -->
<PostLabour>
  <Item>
    <Journal>J001</Journal>
    <LOperation>0010</LOperation>
    <LWorkCentre>WC01</LWorkCentre>
    <LRunTimeHours>2.5</LRunTimeHours>
    <LQtyComplete>10</LQtyComplete>
    <OperCompleted>N</OperCompleted>
  </Item>
</PostLabour>
```

## Source

These schemas are extracted from SYSPRO and maintained in the PhX project.
Original location: `PhX/Schemas/`
