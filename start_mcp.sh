#!/bin/bash
cd /home/ekkerdhomas/projects/pharos-mcp
export PYTHONPATH=/home/ekkerdhomas/projects/pharos-mcp/src
source .venv/bin/activate
exec python -m pharos_mcp.server
