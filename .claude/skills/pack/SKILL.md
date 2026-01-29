# Pack MCPB Skill

Build the MCPB (MCP Bundle) for distribution to Claude Desktop users.

## Usage

```
/pack [version]
```

If version is provided, update manifest.json and pyproject.toml before packing.

## Instructions

### 1. Version Bump (if requested)

If a version argument is provided:

1. Update `version` in `manifest.json`
2. Update `version` in `pyproject.toml`
3. Verify both files have matching versions

Version format: semantic versioning (e.g., `0.1.0`, `0.2.0`, `1.0.0`)

### 2. Validate Manifest

```bash
npx @anthropic-ai/mcpb validate
```

If validation fails, fix the manifest.json issues before proceeding.

### 3. Pack the Bundle

```bash
npx @anthropic-ai/mcpb pack
```

This creates `pharos-mcp.mcpb` in the project root.

### 4. Verify Output

Report the following:
- Bundle filename
- Bundle size
- Number of files included
- SHA checksum

### 5. Distribution Reminder

After packing, remind the user:

> **Distribution options:**
> - Send `.mcpb` file directly to users
> - Attach to GitHub release
> - Submit to Anthropic extension directory

## Example Session

```
User: /pack 0.2.0

Claude: Bumping version to 0.2.0...
✓ Updated manifest.json
✓ Updated pyproject.toml

Validating manifest...
✓ Manifest schema validation passes

Packing bundle...
✓ pharos-mcp-0.2.0.mcpb created

📦 Bundle Details:
- File: pharos-mcp.mcpb
- Size: 113.5 KB
- Files: 45
- SHA: cd9118681b...

Distribution options:
- Send .mcpb file directly to users
- Attach to GitHub release
- Submit to Anthropic extension directory
```

## Files Modified

When bumping version:
- `manifest.json` - `version` field
- `pyproject.toml` - `version` field under `[project]`

## Bundle Contents

The `.mcpb` file includes:
- `manifest.json` - Extension metadata and config
- `pyproject.toml` - Python dependencies
- `config/` - Database configuration templates
- `src/pharos_mcp/` - Server code and tools
- `README.md` - Documentation

Excluded (via `.mcpbignore`):
- `.venv/` - Virtual environment
- `tests/` - Test files
- `logs/` - Log files
- `.env` - Environment secrets
- Cache directories

## Troubleshooting

**Manifest validation fails:**
- Check `repository` is an object: `{"type": "git", "url": "..."}`
- Check `server.mcp_config.command` is present
- Ensure all required fields have values

**Bundle too large:**
- Check `.mcpbignore` includes `.venv/`, `__pycache__/`, etc.
- Remove any large data files

**Missing dependencies at runtime:**
- Verify `pyproject.toml` has all dependencies listed
- UV runtime installs deps automatically on user's machine
