"""Entry point for the MCP server.

Run with:
    python -m app.main
    or
    mcp run app/main.py
"""

from app.mcp.server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
