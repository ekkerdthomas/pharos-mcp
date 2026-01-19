#!/usr/bin/env python3
"""
Standalone entry point for MCP inspector and direct execution.

Usage:
    # stdio mode (for Claude Code, MCP inspector)
    python run_server.py

    # SSE mode (HTTP server for remote access)
    python run_server.py --transport sse --port 8080
"""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from pharos_mcp.server import main

if __name__ == "__main__":
    main()
