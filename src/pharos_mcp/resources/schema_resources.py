"""
MCP Resources for Pharos MCP schema information.

Resources provide context that MCP clients can load to understand
the SYSPRO database structure without making individual tool calls.
"""

from mcp.server.fastmcp import FastMCP


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
