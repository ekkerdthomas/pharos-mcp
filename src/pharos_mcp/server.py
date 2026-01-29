"""
Pharos MCP - Main entry point.

This module initializes and runs the MCP server with all registered
tools and resources for SYSPRO database integration.
"""

import logging

import anyio
from mcp.server.fastmcp import FastMCP

from .core.protocol_logger import logged_stdio_server
from .resources import register_schema_resources
from .tools import (
    register_analytics_tools,
    register_connection_tools,
    register_financial_tools,
    register_phx_tools,
    register_query_tools,
    register_schema_tools,
    register_tempo_analytics_tools,
    register_tempo_enrichment_tools,
    register_tempo_mrp_debug_tools,
    register_warehouse_tools,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create the FastMCP server instance
mcp = FastMCP("pharos-mcp")


def create_server() -> FastMCP:
    """Create and configure the MCP server.

    Returns:
        Configured FastMCP Server instance.
    """
    # Register all tools
    logger.info("Registering connection management tools...")
    register_connection_tools(mcp)

    logger.info("Registering schema tools...")
    register_schema_tools(mcp)

    logger.info("Registering query tools...")
    register_query_tools(mcp)

    logger.info("Registering financial tools...")
    register_financial_tools(mcp)

    logger.info("Registering analytics tools...")
    register_analytics_tools(mcp)

    logger.info("Registering Tempo analytics tools...")
    register_tempo_analytics_tools(mcp)

    logger.info("Registering Tempo enrichment tools...")
    register_tempo_enrichment_tools(mcp)

    logger.info("Registering Tempo MRP debug tools...")
    register_tempo_mrp_debug_tools(mcp)

    logger.info("Registering warehouse tools...")
    register_warehouse_tools(mcp)

    logger.info("Registering PhX API tools...")
    register_phx_tools(mcp)

    # Register resources
    logger.info("Registering resources...")
    register_schema_resources(mcp)

    logger.info("Pharos MCP initialized")
    return mcp


async def run_stdio_with_logging() -> None:
    """Run the server using stdio transport with protocol logging."""
    async with logged_stdio_server() as (read_stream, write_stream):
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            mcp._mcp_server.create_initialization_options(),
        )


def run(transport: str = "stdio", host: str = "0.0.0.0", port: int = 8080) -> None:
    """Entry point for running the server.

    Args:
        transport: Transport type - "stdio" (default) or "sse" for HTTP.
        host: Host to bind to when using SSE transport.
        port: Port to bind to when using SSE transport.
    """
    create_server()

    if transport == "sse":
        import uvicorn

        logger.info(f"Starting SSE server on http://{host}:{port}")
        logger.info("SSE endpoint: /sse")
        logger.info("Messages endpoint: /messages/")
        app = mcp.sse_app()
        uvicorn.run(app, host=host, port=port)
    else:
        anyio.run(run_stdio_with_logging)


def main():
    """CLI entry point with argument parsing."""
    import argparse

    parser = argparse.ArgumentParser(description="Pharos MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type (default: stdio)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to for SSE transport (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for SSE transport (default: 8080)"
    )

    args = parser.parse_args()
    run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
