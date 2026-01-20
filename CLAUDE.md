# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pharos MCP - A Model Context Protocol (MCP) server that provides natural language database querying capabilities for SYSPRO ERP, Tempo MRP, and PostgreSQL data warehouse systems. Enables Claude Desktop users to explore schema and execute read-only SQL queries against SQL Server and PostgreSQL databases.

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
│   ├── database.py    # DatabaseConnection, DatabaseRegistry
│   ├── dialect.py     # Database dialect abstraction (MSSQL, PostgreSQL)
│   ├── security.py    # QueryValidator - read-only SQL enforcement
│   └── audit.py       # @audit_tool_call decorator, JSON-lines logging
├── tools/
│   ├── schema.py      # Schema exploration: search_tables, get_table_schema
│   ├── query.py       # Query execution: execute_query, preview_table
│   ├── warehouse.py   # PostgreSQL warehouse tools: warehouse_list_tables, etc.
│   └── base.py        # Formatting utilities: format_table_results
└── resources/
    └── schema_resources.py  # MCP resources for schema info
```

## Key Design Patterns

**Configuration-driven**: Database connections defined in `config/databases.yaml` with credentials loaded from environment variables via `env_prefix` (e.g., `SYSPRO_DB_SERVER`, `SYSPRO_DB_USERNAME`).

**Dialect Abstraction**: `core/dialect.py` provides `DatabaseDialect` base class with `MSSQLDialect` (pymssql) and `PostgreSQLDialect` (psycopg) implementations. This allows the same `DatabaseConnection` class to work with both SQL Server and PostgreSQL.

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

## PostgreSQL Data Warehouse

The warehouse is a PostgreSQL database containing SYSPRO data transformed via dbt for analytics.

### Warehouse Schema Organization

- `raw` - Raw SYSPRO data (56 tables: ar_customer, sor_master, inv_master, etc.)
- `public_stg` - Staging views (35 tables: stg_ar_customer, stg_sor_master, etc.)
- `public_marts` - Dimensional models (20 tables)

### Warehouse Key Tables

**Dimensions (public_marts):**
- `dim_customer` - Customer master
- `dim_product` - Product/inventory master
- `dim_supplier` - Supplier master
- `dim_date` - Date dimension
- `dim_gl_account` - GL account master
- `dim_job` - Job/work order master

**Facts (public_marts):**
- `fct_sales` - Sales order line items
- `fct_invoices` - AR invoices
- `fct_purchases` - Purchase order items
- `fct_gl_journal` - GL journal entries
- `fct_job_cost` - Job costing details

**Reports (public_marts):**
- `rpt_income_statement` - P&L by period/GL group
- `rpt_balance_sheet` - Balance sheet by account
- `rpt_job_variance` - Job cost variances

### Warehouse Tools

Tools in `tools/warehouse.py`:
- `warehouse_list_schemas()` - List schemas with table counts
- `warehouse_list_tables(schema)` - List tables in a schema
- `warehouse_get_columns(table, schema)` - Get column definitions
- `warehouse_preview(table, schema, limit)` - Preview table data
- `warehouse_search(term, schema)` - Search tables/columns
- `warehouse_table_info(table, schema)` - Detailed table info
- `warehouse_count(table, schema, where)` - Count records

Use `execute_query(sql, database="warehouse")` for custom queries.

## Environment Variables

Required in `.env`:
```
# SYSPRO Company Database (SQL Server)
SYSPRO_DB_SERVER=<sql-server-host>
SYSPRO_DB_NAME=<database-name>
SYSPRO_DB_USERNAME=<username>
SYSPRO_DB_PASSWORD=<password>

# Tempo MRP Database (SQL Server, optional)
TEMPO_DB_SERVER=<sql-server-host>
TEMPO_DB_NAME=Tempo
TEMPO_DB_USERNAME=<username>
TEMPO_DB_PASSWORD=<password>

# Data Warehouse (PostgreSQL, optional)
WAREHOUSE_DB_HOST=<postgresql-host>
WAREHOUSE_DB_PORT=5432
WAREHOUSE_DB_NAME=<database-name>
WAREHOUSE_DB_USERNAME=<username>
WAREHOUSE_DB_PASSWORD=<password>
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
