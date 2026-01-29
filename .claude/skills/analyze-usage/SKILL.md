# Analyze Usage Skill

Analyze real MCP protocol logs to identify improvement opportunities from actual usage patterns.

## Usage

```
/analyze-usage [options]
```

Options:
- `report` - Generate full improvement report (default)
- `errors` - Focus on recent errors
- `tools` - Show tool usage statistics
- `sessions` - List recent sessions

## Instructions

### 1. Generate Improvement Report

```bash
source .venv/bin/activate
PYTHONPATH=src python -c "
from pharos_mcp.core import analyze_protocol_log
print(analyze_protocol_log())
"
```

This produces a markdown report showing:
- Session counts and totals
- Tool usage with error rates
- Recent errors
- Improvement opportunities

### 2. Detailed Tool Analysis

```python
from pharos_mcp.core import ProtocolAnalyzer

analyzer = ProtocolAnalyzer()

# Tool usage stats - identify high-error tools
stats = analyzer.get_tool_usage_stats()
for tool, s in stats.items():
    print(f"{tool}: {s['count']} calls, {s['error_rate']:.1%} errors")
    print(f"  Common args: {list(s['common_args'].keys())}")
```

### 3. Examine Recent Errors

```python
errors = analyzer.get_errors(limit=20)
for e in errors:
    print(f"{e.get('timestamp', '')[:19]}")
    print(f"  {e.get('error')}")
    print()
```

### 4. Review Specific Tool Calls

```python
# Get tool calls with their responses
tool_calls = analyzer.get_tool_calls(limit=50)

# Filter to specific tool
for call in tool_calls:
    if call['tool_name'] == 'execute_query':
        print(f"Args: {call['arguments']}")
        if call.get('is_error'):
            print(f"Error: {call.get('error')}")
        elif call.get('result_preview'):
            print(f"Result: {call['result_preview'][:100]}...")
        print()
```

### 5. Session Analysis

```python
sessions = analyzer.get_sessions()
for s in sessions[:10]:
    print(f"Session {s['session_id']}: {s['tool_calls']} tool calls, {s['errors']} errors")
    print(f"  Methods: {list(s['methods'].keys())}")
```

## Improvement Workflow

1. **Identify high-error tools** - Tools with >10% error rate need investigation
2. **Review error messages** - Group similar errors to find root causes
3. **Check common arguments** - Ensure tools handle typical parameter patterns
4. **Find missing responses** - Tools that don't respond may be crashing
5. **Create fixes** - Use `/improve-mcp` to implement and test fixes

## Example Session

```
User: /analyze-usage

Claude: Analyzing protocol logs...

## Sessions: 12
- Total messages: 847
- Total tool calls: 156
- Total errors: 8

## Tool Usage
| Tool | Calls | Errors | Error Rate |
|------|-------|--------|------------|
| execute_query | 89 | 5 | 5.6% |
| search_tables | 34 | 0 | 0.0% |
| get_table_schema | 23 | 2 | 8.7% |
| warehouse_search | 10 | 1 | 10.0% |

## Improvement Opportunities

### Tools with High Error Rates (>10%)
- **warehouse_search**: 10.0% error rate (1/10)

### Recent Errors
- `2026-01-29T10:30`: Invalid column name 'foo'
- `2026-01-29T10:28`: Database 'unknown' not configured

## Recommendations
1. Add validation for column names in warehouse_search
2. Improve error message for unknown database parameter
```

## Log Location

Protocol logs are at: `logs/protocol.jsonl`

Configure via environment:
- `PHAROS_PROTOCOL_LOG=true/false` - Enable/disable logging
- `PHAROS_PROTOCOL_LOG_DIR=/path` - Custom log directory

## Output Format

Summarize findings as:

| Priority | Tool | Issue | Suggested Fix |
|----------|------|-------|---------------|
| High | tool_name | Description of issue | How to fix it |
