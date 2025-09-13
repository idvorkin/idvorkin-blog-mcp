#!/usr/bin/env python3
"""Test script for the deployed FastMCP blog server"""

import asyncio
from fastmcp import Client


async def test_deployed_server():
    """Test the deployed MCP server"""
    server_url = "https://idvorkin-blog-mcp.fastmcp.app/mcp"

    print(f"Testing MCP server at: {server_url}")

    try:
        # Create client
        client = Client(server_url)

        async with client:
            # Test connectivity
            print("🔍 Testing connectivity...")
            await client.ping()
            print("✅ Server is responding!")

            # List available tools
            print("\n🛠️ Available tools:")
            tools = await client.list_tools()
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")

            # Test blog_info tool
            print("\n📊 Testing blog_info tool...")
            result = await client.call_tool("blog_info")
            print(f"Result: {result}")

            # Test random_blog_url tool
            print("\n🎲 Testing random_blog_url tool...")
            result = await client.call_tool("random_blog_url")
            print(f"Random URL: {result}")

            # Test blog_search tool
            print("\n🔍 Testing blog_search tool...")
            result = await client.call_tool("blog_search", {"query": "productivity", "limit": 3})
            print(f"Search results: {result}")

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    print("\n🎉 All tests passed!")
    return True


if __name__ == "__main__":
    asyncio.run(test_deployed_server())