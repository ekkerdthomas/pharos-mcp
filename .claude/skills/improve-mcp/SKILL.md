# Improve MCP Skill

Run an improvement loop to test and enhance the Pharos MCP tools.

## Usage

```
/improve-mcp [tool-category]
```

Categories:
- `warehouse` - PostgreSQL warehouse tools
- `schema` - SYSPRO schema exploration tools
- `query` - Query execution tools
- `tempo` - Tempo MRP tools
- `all` - All tool categories (default)

## Instructions

### 1. Setup Test Environment

```python
source .venv/bin/activate
python -c "from pharos_mcp.server import create_server; create_server(); print('Server OK')"
```

### 2. Test Tools Systematically

For each tool category, test:

1. **Happy Path** - Normal usage with valid inputs
2. **Edge Cases** - Empty results, large datasets, special characters
3. **Error Handling** - Invalid inputs, missing tables, bad SQL
4. **Security** - SQL injection attempts, dangerous keywords
5. **Database Parameter** - Test with different databases (syspro_company, warehouse, tempo)

### 3. Testing Patterns

#### Warehouse Tools
```python
from pharos_mcp.tools.warehouse import register_warehouse_tools
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('test')
register_warehouse_tools(mcp)
tools = mcp._tool_manager._tools

# Test tool
result = tools['warehouse_list_schemas'].fn()
print(result)
```

#### Async Tools (query.py)
```python
import asyncio
from pharos_mcp.tools.query import register_query_tools

async def test():
    result = await tools['execute_query'].fn(sql="SELECT 1", database="warehouse")
    print(result)

asyncio.run(test())
```

### 4. Common Issues to Check

- [ ] Unused parameters (accepted but ignored)
- [ ] SQL injection vulnerabilities in WHERE/columns
- [ ] Uncaught exceptions (should return user-friendly messages)
- [ ] Noisy results (audit tables, empty schemas)
- [ ] Missing error handling for database connections
- [ ] Incorrect SQL syntax for database type (LIMIT vs TOP)

### 5. Security Validation Checklist

Test these dangerous patterns are blocked:
- `; DROP TABLE`
- `--` (comment injection)
- `/*` (block comment)
- `DELETE`, `INSERT`, `UPDATE`, `TRUNCATE`, `ALTER`, `CREATE`

### 6. Fix and Document

For each issue found:

1. **Fix the code** - Add validation, error handling, or security checks
2. **Test the fix** - Verify the issue is resolved
3. **Run full tests** - `pytest tests/ -q`
4. **Commit with clear message** - Describe what was fixed and why

### 7. Commit Improvements

After fixing issues, commit with conventional commit format:

```bash
git add <files>
git commit -m "fix: <description of what was fixed>

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

## Example Session

```
User: /improve-mcp warehouse

Claude: Starting improvement loop for warehouse tools...

Testing warehouse_list_schemas...
✓ Happy path works
✓ Excludes system schemas

Testing warehouse_search...
✗ Found issue: includes dbt audit tables
→ Fix: Add public_dbt_test__audit to EXCLUDED_SCHEMAS

Testing warehouse_count...
✗ Found issue: SQL injection in WHERE clause
→ Fix: Add dangerous keyword validation

[Commits fixes and pushes]

Improvement loop complete:
- 3 issues found
- 3 issues fixed
- All tests passing
```

## Output Format

After each improvement loop, summarize:

| Issue | Fix | Commit |
|-------|-----|--------|
| Description of issue | How it was fixed | Commit hash |
