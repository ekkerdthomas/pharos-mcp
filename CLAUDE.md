# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pharos MCP - A Model Context Protocol (MCP) server that provides natural language database querying capabilities for SYSPRO ERP systems. Enables Claude Desktop users to explore schema and execute read-only SQL queries against SYSPRO SQL Server databases.

Part of the Phygital Tech Ph-ecosystem.

## Commands

```bash
# Run the MCP server (stdio mode for Claude Desktop)
./start_mcp.sh

# Or manually:
source .venv/bin/activate
PYTHONPATH=src python -m pharos_mcp.server

# Run with HTTP/SSE transport (for remote access)
python -m pharos_mcp.server --transport sse --port 8080

# Test MCP inspector (interactive testing)
python run_server.py
```

## Architecture

```
src/pharos_mcp/
├── server.py          # FastMCP entry point, registers tools/resources
├── config.py          # YAML config loader, env var resolution
├── core/
│   ├── database.py    # DatabaseConnection, DatabaseRegistry (pymssql)
│   ├── security.py    # QueryValidator - read-only SQL enforcement
│   └── audit.py       # @audit_tool_call decorator, JSON-lines logging
├── tools/
│   ├── schema.py      # Schema exploration: search_tables, get_table_schema
│   ├── query.py       # Query execution: execute_query, preview_table
│   └── base.py        # Formatting utilities: format_table_results
└── resources/
    └── schema_resources.py  # MCP resources for schema info
```

## Key Design Patterns

**Configuration-driven**: Database connections defined in `config/databases.yaml` with credentials loaded from environment variables via `env_prefix` (e.g., `SYSPRO_DB_SERVER`, `SYSPRO_DB_USERNAME`).

**SYSPRO Domain Knowledge**: `tools/schema.py` contains `SYSPRO_DOMAIN_MAP` which maps business terms ("customer", "inventory", "sales order") to SYSPRO table prefixes (Ar, Inv, Sor). This enables intelligent table searches.

**Read-only Enforcement**: `QueryValidator` in `core/security.py` blocks INSERT/UPDATE/DELETE/DROP statements. All queries go through validation.

**Tool Registration Pattern**: Tools are registered via `register_*_tools(mcp)` functions that use `@mcp.tool()` decorator from FastMCP.

## SYSPRO Table Naming Conventions

SYSPRO uses 2-3 letter prefixes indicating the module:
- `Ar*` - Accounts Receivable (customers)
- `Ap*` - Accounts Payable (suppliers)
- `Inv*` - Inventory
- `Sor*` - Sales Orders
- `Por*` - Purchase Orders
- `Wip*` - Work in Progress (manufacturing)
- `Gen*` - General Ledger
- `Bom*` - Bill of Materials

## Environment Variables

Required in `.env`:
```
SYSPRO_DB_SERVER=<sql-server-host>
SYSPRO_DB_NAME=<database-name>
SYSPRO_DB_USERNAME=<username>
SYSPRO_DB_PASSWORD=<password>
```

## Claude Desktop Integration

Configure in `%APPDATA%\Claude\claude_desktop_config.json` (Windows with WSL):
```json
{
  "mcpServers": {
    "pharos": {
      "command": "wsl.exe",
      "args": ["/home/<user>/projects/pharos-mcp/start_mcp.sh"]
    }
  }
}
```
