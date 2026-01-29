"""
MCP Resources for Pharos MCP schema information.

Resources provide context that MCP clients can load to understand
the SYSPRO database structure without making individual tool calls.
"""

import logging
import os
import time
from typing import Any

import httpx

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Cache for swagger spec
_swagger_cache: dict[str, Any] | None = None
_swagger_cache_time: float = 0
_SWAGGER_CACHE_TTL = 300  # 5 minutes


async def _load_swagger() -> dict[str, Any] | None:
    """Fetch swagger.json from PhX API with caching."""
    global _swagger_cache, _swagger_cache_time

    # Return cached version if still valid
    if _swagger_cache and (time.time() - _swagger_cache_time) < _SWAGGER_CACHE_TTL:
        return _swagger_cache

    # Get PhX URL from environment
    phx_url = os.getenv("PHX_URL", "").rstrip("/")
    if not phx_url:
        logger.warning("PHX_URL not configured, cannot fetch swagger.json")
        return None

    swagger_url = f"{phx_url}/swagger/v1/swagger.json"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(swagger_url)
            response.raise_for_status()
            _swagger_cache = response.json()
            _swagger_cache_time = time.time()
            logger.info(f"Fetched swagger.json from {swagger_url}")
            return _swagger_cache
    except Exception as e:
        logger.error(f"Failed to fetch swagger.json from {swagger_url}: {e}")
        # Return stale cache if available
        if _swagger_cache:
            logger.info("Using stale swagger cache")
            return _swagger_cache
        return None


def _resolve_ref(swagger: dict[str, Any], ref: str) -> dict[str, Any]:
    """Resolve a $ref pointer in the swagger spec."""
    if not ref.startswith("#/"):
        return {}
    parts = ref[2:].split("/")
    obj = swagger
    for part in parts:
        obj = obj.get(part, {})
    return obj


def _format_schema(swagger: dict[str, Any], schema: dict[str, Any], indent: int = 0) -> str:
    """Format a schema object as readable text."""
    if "$ref" in schema:
        schema = _resolve_ref(swagger, schema["$ref"])

    lines = []
    prefix = "  " * indent

    if schema.get("type") == "object":
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        for name, prop in props.items():
            prop_type = prop.get("type", "object")
            if "$ref" in prop:
                ref_name = prop["$ref"].split("/")[-1]
                prop_type = ref_name
            req_marker = "*" if name in required else ""
            desc = prop.get("description", "")
            if desc:
                lines.append(f"{prefix}- {name}{req_marker}: {prop_type} - {desc}")
            else:
                lines.append(f"{prefix}- {name}{req_marker}: {prop_type}")
    elif schema.get("type") == "array":
        items = schema.get("items", {})
        if "$ref" in items:
            ref_name = items["$ref"].split("/")[-1]
            lines.append(f"{prefix}Array of {ref_name}")
        else:
            lines.append(f"{prefix}Array of {items.get('type', 'object')}")

    return "\n".join(lines)


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

    @mcp.resource("phx://api")
    async def phx_api_overview() -> str:
        """PhX API overview with all endpoints grouped by category."""
        swagger = await _load_swagger()
        if not swagger:
            phx_url = os.getenv("PHX_URL", "")
            return f"Error: Could not fetch API docs from {phx_url}/swagger/v1/swagger.json. Check PHX_URL is configured."

        # Group endpoints by tag
        endpoints_by_tag: dict[str, list[tuple[str, str, str, str]]] = {}
        for path, methods in swagger.get("paths", {}).items():
            for method, details in methods.items():
                if method in ("get", "post", "put", "delete", "patch"):
                    tags = details.get("tags", ["Other"])
                    summary = details.get("summary", "")
                    op_id = details.get("operationId", "")
                    for tag in tags:
                        if tag not in endpoints_by_tag:
                            endpoints_by_tag[tag] = []
                        endpoints_by_tag[tag].append((method.upper(), path, summary, op_id))

        lines = ["# PhX API Reference\n"]
        lines.append("SYSPRO WCF REST wrapper providing modern HTTP access to SYSPRO business objects.\n")
        lines.append("## Authentication\n")
        lines.append("**DirectAuth endpoints** (BO Call): Credentials in request body")
        lines.append("**TokenAuth endpoints**: Requires X-UserId header from /api/Auth/logon\n")

        # Sort tags: prioritize Query and WIP
        priority_tags = ["Query (BO Call)", "WIP Transactions (BO Call)", "Requisition (BO Call)"]
        sorted_tags = [t for t in priority_tags if t in endpoints_by_tag]
        sorted_tags += [t for t in sorted(endpoints_by_tag.keys()) if t not in priority_tags]

        for tag in sorted_tags:
            endpoints = endpoints_by_tag[tag]
            lines.append(f"\n## {tag}\n")
            lines.append("| Method | Endpoint | Description |")
            lines.append("|--------|----------|-------------|")
            for method, path, summary, _ in sorted(endpoints, key=lambda x: x[1]):
                lines.append(f"| {method} | `{path}` | {summary} |")

        lines.append("\n## Usage\n")
        lines.append("Get endpoint details: `phx://api/endpoint/{path-with-dashes}`")
        lines.append("Example: `phx://api/endpoint/api-QueryBo-inventory`")

        return "\n".join(lines)

    @mcp.resource("phx://api/endpoint/{endpoint}")
    async def phx_api_endpoint(endpoint: str) -> str:
        """Get detailed documentation for a specific PhX API endpoint.

        Args:
            endpoint: Endpoint path without leading slash, with - instead of /
                      Example: api-QueryBo-inventory for /api/QueryBo/inventory
        """
        swagger = await _load_swagger()
        if not swagger:
            phx_url = os.getenv("PHX_URL", "")
            return f"Error: Could not fetch API docs from {phx_url}/swagger/v1/swagger.json. Check PHX_URL is configured."

        # Convert dashes back to slashes for path lookup
        path = "/" + endpoint.replace("-", "/")

        path_info = swagger.get("paths", {}).get(path)
        if not path_info:
            # List available endpoints
            available = list(swagger.get("paths", {}).keys())[:15]
            formatted = [p.replace("/", "-")[1:] for p in available]
            return (
                f"Endpoint '{path}' not found.\n\n"
                f"Use dashes instead of slashes in the endpoint path.\n"
                f"Example: `phx://api/endpoint/api-QueryBo-inventory`\n\n"
                f"Available endpoints:\n" + "\n".join(f"- {p}" for p in formatted)
            )

        lines = [f"# {path}\n"]

        for method, details in path_info.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue

            lines.append(f"## {method.upper()}\n")
            lines.append(f"**{details.get('summary', 'No summary')}**\n")

            if details.get("description"):
                lines.append(details["description"] + "\n")

            # Request body
            if "requestBody" in details:
                lines.append("### Request Body\n")
                content = details["requestBody"].get("content", {})
                json_content = content.get("application/json", content.get("text/json", {}))
                if "schema" in json_content:
                    schema = json_content["schema"]
                    if "$ref" in schema:
                        schema_name = schema["$ref"].split("/")[-1]
                        resolved = _resolve_ref(swagger, schema["$ref"])
                        lines.append(f"**{schema_name}**\n")
                        lines.append(_format_schema(swagger, resolved))
                        lines.append("")

            # Responses
            lines.append("### Responses\n")
            for status, resp in details.get("responses", {}).items():
                desc = resp.get("description", "")
                lines.append(f"- **{status}**: {desc}")

            lines.append("")

        return "\n".join(lines)
