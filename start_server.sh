#!/bin/bash
# Start the MCP server

cd "$(dirname "$0")"
source .venv/bin/activate
python mcp_server/server.py
