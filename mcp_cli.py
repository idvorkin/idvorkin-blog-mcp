#!/usr/bin/env python3
"""
Simple CLI for calling MCP tools.
Uses MCP_SERVER_ENDPOINT environment variable or defaults to local.
"""

import asyncio
import json
import os
import sys
from test_utils import MCPTestClient

# Server endpoints (same as test_e2e.py)
LOCAL_ENDPOINT = "http://localhost:8000/mcp"
PRODUCTION_ENDPOINT = "https://idvorkin-blog-and-repo.fastmcp.app/mcp"


def get_server_endpoint() -> str:
    """Get server endpoint from environment variable or default to local."""
    endpoint = os.getenv("MCP_SERVER_ENDPOINT", LOCAL_ENDPOINT)
    return endpoint


async def call_tool(tool_name: str, args: dict = None):
    """Call an MCP tool and print the result."""
    if args is None:
        args = {}

    endpoint = get_server_endpoint()
    async with MCPTestClient(endpoint) as client:
        result = await client.call_tool(tool_name, args)
        print(result)


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: mcp_cli.py <tool_name> [json_args]")
        print(f"Server: {get_server_endpoint()}")
        print("\nExamples:")
        print("  mcp_cli.py blog_info")
        print("  mcp_cli.py read_blog_post '{\"url\":\"https://idvork.in/42\"}'")
        print("  MCP_SERVER_ENDPOINT=https://idvorkin-blog-and-repo.fastmcp.app/mcp mcp_cli.py blog_info")
        sys.exit(1)

    tool_name = sys.argv[1]
    args = {}

    if len(sys.argv) > 2:
        try:
            args = json.loads(sys.argv[2])
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON arguments: {sys.argv[2]}")
            sys.exit(1)

    asyncio.run(call_tool(tool_name, args))


if __name__ == "__main__":
    main()