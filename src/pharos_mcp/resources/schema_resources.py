"""
MCP Resources for Pharos MCP schema information.

Resources provide context that MCP clients can load to understand
the SYSPRO database structure without making individual tool calls.
"""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Path to PhX schemas
SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent / "schemas" / "phx"


def register_schema_resources(mcp: FastMCP) -> None:
    """Register schema resources with the MCP server.

    Args:
        mcp: The FastMCP server instance.
    """

    @mcp.resource("pharos://help/getting-started")
    async def getting_started() -> str:
        """Getting started guide for Pharos MCP."""
        return """# Pharos MCP - Getting Started

Welcome to Pharos MCP. This server provides tools for exploring
and querying SYSPRO ERP databases.

## Available Tool Categories

### Schema Tools
- `search_tables` - Find tables by name or description
- `get_table_schema` - Get complete table details including columns
- `get_table_columns` - Get column definitions with valid values
- `find_related_tables` - Find FK relationships
- `search_columns` - Search for columns across all tables
- `list_modules` - List SYSPRO modules

### Query Tools
- `execute_query` - Run validated SELECT queries
- `preview_table` - Quick data preview
- `count_records` - Count with optional filter
- `list_databases` - List available databases

## Common SYSPRO Tables

### Customers (AR Module)
- ArCustomer - Customer master data
- ArInvoice - Customer invoices
- ArTrnDetail - Transaction details

### Inventory (INV Module)
- InvMaster - Stock item master
- InvWarehouse - Warehouse stock levels
- InvMovements - Stock movements

### Sales (SOR Module)
- SorMaster - Sales order headers
- SorDetail - Sales order lines
- SorDetailMerch - Merchandise details

### Purchasing (POR Module)
- PorMasterHdr - Purchase order headers
- PorMasterDetail - Purchase order lines

## Example Queries

1. Find customer tables:
   search_tables("customer")

2. View customer schema:
   get_table_schema("ArCustomer")

3. Preview customers:
   preview_table("ArCustomer", limit=10)

4. Custom query:
   execute_query("SELECT TOP 10 Customer, Name FROM ArCustomer")
"""

    @mcp.resource("syspro://help/common-tables")
    async def common_tables() -> str:
        """Reference of common SYSPRO tables."""
        return """# Common SYSPRO Tables Reference

## Accounts Receivable (AR)
| Table | Description |
|-------|-------------|
| ArCustomer | Customer master file |
| ArCustomerBal | Customer balances |
| ArInvoice | Invoice header |
| ArTrnDetail | Transaction details |
| ArBranch | Branch information |

## Inventory (INV)
| Table | Description |
|-------|-------------|
| InvMaster | Stock item master |
| InvWarehouse | Warehouse stock levels |
| InvMovements | Stock movements |
| InvMultBin | Multi-bin locations |
| InvPrice | Pricing information |

## Sales Orders (SOR)
| Table | Description |
|-------|-------------|
| SorMaster | Sales order header |
| SorDetail | Sales order lines |
| SorDetailMerch | Merchandise details |
| SorBackOrder | Back order information |

## Purchase Orders (POR)
| Table | Description |
|-------|-------------|
| PorMasterHdr | Purchase order header |
| PorMasterDetail | Purchase order lines |
| PorSupplier | Supplier master |

## General Ledger (GL)
| Table | Description |
|-------|-------------|
| GenMaster | GL account master |
| GenTransactionPost | Posted transactions |
| GenBudget | Budget information |

## Work In Progress (WIP)
| Table | Description |
|-------|-------------|
| WipMaster | Job master |
| WipJobAllMat | Job materials |
| WipJobAllLab | Job labor |
"""

    @mcp.resource("syspro://modules/{module}")
    async def module_info(module: str) -> str:
        """Get information about a specific SYSPRO module."""
        module_info = {
            "AR": {
                "name": "Accounts Receivable",
                "description": "Manages customer accounts, invoicing, and payments.",
                "key_tables": ["ArCustomer", "ArInvoice", "ArTrnDetail", "ArPayment"],
            },
            "INV": {
                "name": "Inventory",
                "description": "Manages stock items, warehouses, and movements.",
                "key_tables": ["InvMaster", "InvWarehouse", "InvMovements", "InvPrice"],
            },
            "SOR": {
                "name": "Sales Orders",
                "description": "Manages sales orders, quotes, and deliveries.",
                "key_tables": ["SorMaster", "SorDetail", "SorBackOrder"],
            },
            "POR": {
                "name": "Purchase Orders",
                "description": "Manages purchase orders and supplier relationships.",
                "key_tables": ["PorMasterHdr", "PorMasterDetail", "PorSupplier"],
            },
            "GL": {
                "name": "General Ledger",
                "description": "Manages chart of accounts and financial transactions.",
                "key_tables": ["GenMaster", "GenTransactionPost", "GenBudget"],
            },
            "WIP": {
                "name": "Work In Progress",
                "description": "Manages job costing and manufacturing.",
                "key_tables": ["WipMaster", "WipJobAllMat", "WipJobAllLab"],
            },
            "BOM": {
                "name": "Bill of Materials",
                "description": "Manages product structures and routings.",
                "key_tables": ["BomStructure", "BomRoute", "BomOperations"],
            },
            "AP": {
                "name": "Accounts Payable",
                "description": "Manages supplier accounts and payments.",
                "key_tables": ["ApSupplier", "ApInvoice", "ApPayment"],
            },
        }

        info = module_info.get(module.upper())
        if not info:
            available = ", ".join(module_info.keys())
            return f"Module '{module}' not found. Available: {available}"

        tables = "\n".join(f"- {t}" for t in info["key_tables"])
        return f"""# {info['name']} Module ({module.upper()})

{info['description']}

## Key Tables
{tables}

Use `search_tables` with module="{module.upper()}" to see all tables in this module.
"""

    @mcp.resource("phx://schemas")
    async def phx_schemas_list() -> str:
        """List available PhX SYSPRO business object schemas."""
        return """# PhX SYSPRO Business Object Schemas

XML Schema Definition (XSD) files for SYSPRO business objects.

## Schema Naming Convention
- `{BO}.XSD` - Parameters schema (options, filters)
- `{BO}DOC.XSD` - Document schema (data payload)

## Query Business Objects
| BO | Description | URI |
|----|-------------|-----|
| INVQRY | Inventory Query | `phx://schemas/INVQRY` |
| WIPQRY | WIP Job Query | `phx://schemas/WIPQRY` |
| WIPQVA | WIP Variance Query | `phx://schemas/WIPQVA` |
| WIPQ40 | WIP Multi-level Query | `phx://schemas/WIPQ40` |
| PORQRQ | Requisition Query | `phx://schemas/PORQRQ` |
| INVQGD | Goods In Transit Query | `phx://schemas/INVQGD` |

## Transaction Business Objects
| BO | Description | URI |
|----|-------------|-----|
| WIPTLP | Post Labour | `phx://schemas/WIPTLP` |
| WIPTJR | Post Job Receipt | `phx://schemas/WIPTJR` |
| WIPTMI | Post Material Issue | `phx://schemas/WIPTMI` |
| PORTRA | Requisition Approve | `phx://schemas/PORTRA` |
| PORTRR | Requisition Route | `phx://schemas/PORTRR` |

## Inventory Movement Business Objects
| BO | Description | URI |
|----|-------------|-----|
| INVTMA | Inventory Adjustment | `phx://schemas/INVTMA` |
| INVTMO | Warehouse Transfer Out | `phx://schemas/INVTMO` |
| INVTMI | Warehouse Transfer In | `phx://schemas/INVTMI` |
| INVTMB | Bin Transfer | `phx://schemas/INVTMB` |
| INVTMT | GIT Transfer Out | `phx://schemas/INVTMT` |
| INVTMN | GIT Transfer In | `phx://schemas/INVTMN` |

## Usage
Load a schema with: `phx://schemas/{BO_CODE}`
Example: `phx://schemas/WIPTLP` for labour posting schema
"""

    @mcp.resource("phx://schemas/{bo_code}")
    async def phx_schema(bo_code: str) -> str:
        """Get XSD schema for a SYSPRO business object.

        Args:
            bo_code: Business object code (e.g., WIPTLP, INVQRY)
        """
        bo_code = bo_code.upper()

        # Try to find both parameter and document schemas
        param_file = SCHEMAS_DIR / f"{bo_code}.XSD"
        doc_file = SCHEMAS_DIR / f"{bo_code}DOC.XSD"

        result_parts = [f"# {bo_code} Schema\n"]

        if param_file.exists():
            result_parts.append(f"## Parameters Schema ({bo_code}.XSD)\n")
            result_parts.append("```xml")
            result_parts.append(param_file.read_text(encoding="utf-8"))
            result_parts.append("```\n")

        if doc_file.exists():
            result_parts.append(f"## Document Schema ({bo_code}DOC.XSD)\n")
            result_parts.append("```xml")
            result_parts.append(doc_file.read_text(encoding="utf-8"))
            result_parts.append("```\n")

        if not param_file.exists() and not doc_file.exists():
            available = [f.stem for f in SCHEMAS_DIR.glob("*.XSD") if not f.stem.endswith("DOC")]
            return f"Schema '{bo_code}' not found.\n\nAvailable: {', '.join(sorted(set(available)))}"

        return "\n".join(result_parts)
