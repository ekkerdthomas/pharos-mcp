# PhX API Documentation

Live OpenAPI/Swagger documentation fetched from the PhX REST API.

## MCP Resources

Access API documentation via MCP resources (fetched live from PHX_URL):

- `phx://api` - Overview of all endpoints grouped by category
- `phx://api/endpoint/{path}` - Detailed docs for specific endpoint

### Examples

```
# Get API overview
phx://api

# Get inventory query endpoint docs (use dashes instead of slashes)
phx://api/endpoint/api-QueryBo-inventory

# Get labour posting endpoint docs
phx://api/endpoint/api-WipTransaction-post-labour
```

## Configuration

Requires `PHX_URL` environment variable pointing to PhX API:
```
PHX_URL=https://syspro-api.phygital-tech.ai
```

## Key Endpoint Categories

### Query (BO Call) - Read-only, DirectAuth
- `/api/QueryBo/inventory` - Query stock item
- `/api/QueryBo/wip-job` - Query WIP job details
- `/api/QueryBo/wip-tracking` - Query job variances
- `/api/QueryBo/requisition` - Query requisitions

### WIP Transactions (BO Call) - Write, DirectAuth
- `/api/WipTransaction/post-labour` - Post labour to job
- `/api/WipTransaction/post-job-receipt` - Complete job receipt
- `/api/WipTransaction/post-material` - Issue material to job

### Requisition (BO Call) - Write, DirectAuth
- `/api/RequisitionBo/approve` - Approve requisition
- `/api/RequisitionBo/route` - Route requisition

## Caching

Swagger spec is cached for 5 minutes to reduce API calls.
