# Pharos MCP

**Ask your ERP questions. Get answers, not queries.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Model Context Protocol (MCP) server that enables natural language querying of SYSPRO ERP databases through Claude Desktop. Non-technical users can explore database schema and execute read-only SQL queries using plain English.

Part of the **Phygital Tech Ph-ecosystem**.

## Features

- **Natural Language Queries**: Ask questions like "show me all customer tables" or "what columns are in InvMaster?"
- **SYSPRO Domain Knowledge**: Built-in mapping of business terms to SYSPRO table prefixes (customer → Ar*, inventory → Inv*, etc.)
- **Read-Only Safety**: All queries are validated to prevent data modification
- **Schema Exploration**: Search tables, view columns, find relationships
- **Query Execution**: Run SELECT queries with automatic result formatting
- **Audit Logging**: All tool calls logged to `logs/audit.jsonl`

## Prerequisites

- Python 3.11+
- Access to a SYSPRO SQL Server database
- Claude Desktop (for end-user access)

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd pharos-mcp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### 1. Database Credentials

Create a `.env` file in the project root:

```env
# SYSPRO Company Database
SYSPRO_DB_SERVER=your-sql-server.example.com
SYSPRO_DB_NAME=SysproCompanyXXX
SYSPRO_DB_USERNAME=your-username
SYSPRO_DB_PASSWORD=your-password
SYSPRO_DB_TRUSTED_CONNECTION=false

# SYSPRO Admin Database (optional)
SYSPRO_ADMIN_DB_SERVER=your-sql-server.example.com
SYSPRO_ADMIN_DB_NAME=sysprodb
SYSPRO_ADMIN_DB_USERNAME=your-username
SYSPRO_ADMIN_DB_PASSWORD=your-password
SYSPRO_ADMIN_DB_TRUSTED_CONNECTION=false
```

### 2. Claude Desktop Integration

Add to your Claude Desktop config file:

**Windows (with WSL):** `%APPDATA%\Claude\claude_desktop_config.json`
```json
{
  "mcpServers": {
    "pharos": {
      "command": "wsl.exe",
      "args": ["/path/to/pharos-mcp/start_mcp.sh"]
    }
  }
}
```

**Linux/macOS:** `~/.config/Claude/claude_desktop_config.json`
```json
{
  "mcpServers": {
    "pharos": {
      "command": "/path/to/pharos-mcp/start_mcp.sh"
    }
  }
}
```

Restart Claude Desktop after configuration.

## Usage

Once configured, open Claude Desktop and ask questions like:

- "Search for tables related to customers"
- "Show me the schema of the ArCustomer table"
- "Preview data from InvMaster"
- "How many sales orders are in the system?"
- "Find tables related to inventory"
- "What columns are in SorMaster?"
- "Execute: SELECT TOP 10 * FROM ArCustomer"

## Available Tools

| Tool | Description |
|------|-------------|
| `search_tables` | Search for tables by business term or name pattern |
| `get_table_schema` | Get detailed schema for a specific table |
| `get_table_columns` | List all columns with data types |
| `find_related_tables` | Discover tables with similar prefixes |
| `search_columns` | Search for columns across all tables |
| `execute_query` | Run read-only SQL queries |
| `preview_table` | Preview sample data from a table |
| `count_records` | Count records in a table |
| `list_modules` | List SYSPRO module prefixes |
| `list_databases` | List configured databases |

## SYSPRO Table Prefixes

Pharos MCP understands SYSPRO's naming conventions:

| Prefix | Module |
|--------|--------|
| `Ar*` | Accounts Receivable (Customers) |
| `Ap*` | Accounts Payable (Suppliers) |
| `Inv*` | Inventory |
| `Sor*` | Sales Orders |
| `Por*` | Purchase Orders |
| `Wip*` | Work in Progress |
| `Gen*` | General Ledger |
| `Bom*` | Bill of Materials |
| `Sal*` | Sales Analysis |
| `Cb*` | Cashbook |

## Project Structure

```
pharos-mcp/
├── config/
│   ├── databases.yaml    # Database connection config
│   ├── tools.yaml        # Tool settings
│   └── prompts.yaml      # Prompt templates
├── src/pharos_mcp/
│   ├── server.py         # MCP server entry point
│   ├── config.py         # Configuration loader
│   ├── core/
│   │   ├── database.py   # Database connection management
│   │   ├── security.py   # Query validation
│   │   └── audit.py      # Audit logging
│   ├── tools/
│   │   ├── schema.py     # Schema exploration tools
│   │   ├── query.py      # Query execution tools
│   │   └── base.py       # Formatting utilities
│   └── resources/
│       └── schema_resources.py
├── logs/                  # Audit logs
├── .env                   # Database credentials (not committed)
├── requirements.txt
├── start_mcp.sh          # Startup script
└── run_server.py         # MCP inspector entry point
```

## Running Manually

```bash
# Standard mode (stdio for Claude Desktop)
./start_mcp.sh

# HTTP/SSE mode (for remote access)
python -m pharos_mcp.server --transport sse --port 8080
```

## Security

- All queries are validated for read-only operations
- INSERT, UPDATE, DELETE, DROP, and other modifying statements are blocked
- Database credentials are loaded from environment variables, not committed to source
- Audit logging tracks all tool invocations

## License

MIT
