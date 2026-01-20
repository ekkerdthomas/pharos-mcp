# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pharos MCP - A Model Context Protocol (MCP) server that provides natural language database querying capabilities for SYSPRO ERP and Tempo MRP systems. Enables Claude Desktop users to explore schema and execute read-only SQL queries against SQL Server databases.

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

**Domain Knowledge**: `tools/data/domain_map.py` contains `SYSPRO_DOMAIN_MAP` which maps business terms ("customer", "inventory", "sales order") to SYSPRO table prefixes (Ar, Inv, Sor). `tools/data/tempo_domain_map.py` contains `TEMPO_DOMAIN_MAP` for Tempo MRP tables. This enables intelligent table searches.

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

## Tempo MRP Database

Tempo is a dedicated MRP (Material Requirements Planning) system that integrates with SYSPRO. It uses a run-based data model where each MRP run creates a snapshot of planning data.

### Tempo Schema Organization

Tempo uses SQL Server schemas to organize tables:
- `master.*` - Item master data (Items)
- `mrp.*` - MRP core tables (Demands, Supply, Suggestions, Inventory, Runs)
- `forecast.*` - Forecasting tables (ForecastResults, ForecastAccuracy)
- `analytics.*` - Analysis tables (ItemClassification, LeadTimeDetail)
- `auth.*` - Users, Companies, Permissions, Licenses

### Tempo Key Tables

**Core MRP (mrp schema):**
- `mrp.Items` → `master.Items` - Item master data
- `mrp.Inventory` - Stock levels by warehouse
- `mrp.Demands` - Demand records (sales orders, job requirements)
- `mrp.Supply` - Supply records (purchase orders, jobs, transfers)
- `mrp.Suggestions` - MRP-generated planned orders and actions
- `mrp.Runs` - MRP run history and configuration

**Forecasting (forecast schema):**
- `forecast.ForecastResults` - Forecast data
- `forecast.ForecastAccuracy` - Forecast performance metrics

**Classification (analytics schema):**
- `analytics.ItemClassification` - ABC analysis results
- `analytics.LeadTimeDetail` - Lead time analysis

**Configuration (auth schema):**
- `auth.Companies` - Multi-tenant company configuration
- `auth.Users` - User management

### Tempo Query Templates

Query templates are in `tools/data/tempo_templates/` (44 templates):
- `mrp_core.py` - Demands, supply, suggestions, pegging
- `forecasting.py` - Forecasts, accuracy metrics
- `inventory.py` - Stock levels, ABC classification
- `analytics.py` - MRP runs, lead times, audit

Use `get_tempo_query_template("list")` to see all templates.
Replace `<COMPANY_ID>` placeholder with company (e.g., 'TTM', 'TTML', 'IV').

### Tempo Domain Knowledge

Domain mappings are in `tools/data/tempo_domain_map.py` - maps business terms to Tempo tables.
Module descriptions are in `tools/data/tempo_modules.py`.

## Environment Variables

Required in `.env`:
```
# SYSPRO Company Database
SYSPRO_DB_SERVER=<sql-server-host>
SYSPRO_DB_NAME=<database-name>
SYSPRO_DB_USERNAME=<username>
SYSPRO_DB_PASSWORD=<password>

# Tempo MRP Database (optional)
TEMPO_DB_SERVER=<sql-server-host>
TEMPO_DB_NAME=Tempo
TEMPO_DB_USERNAME=<username>
TEMPO_DB_PASSWORD=<password>
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
