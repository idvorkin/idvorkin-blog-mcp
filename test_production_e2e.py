#!/usr/bin/env python3
"""
Production E2E tests for the Blog MCP Server
Tests against live endpoints (local or production) without mocking
"""

import asyncio
import os
import sys
from typing import Optional

import pytest
from fastmcp import Client

# Server endpoints
LOCAL_ENDPOINT = "http://localhost:8000/mcp"
PRODUCTION_ENDPOINT = "https://idvorkin-blog-mcp.fastmcp.app/mcp"


def get_server_endpoint() -> str:
    """Get server endpoint from environment variable or default to local."""
    endpoint = os.getenv("MCP_SERVER_ENDPOINT", LOCAL_ENDPOINT)
    print(f"Testing against: {endpoint}")
    return endpoint


class TestProductionBlogMCPServer:
    """Production E2E tests for Blog MCP Server against live endpoints."""

    @pytest.fixture(scope="class")
    def server_endpoint(self) -> str:
        """Get the server endpoint for testing."""
        return get_server_endpoint()

    @pytest.fixture(scope="class")
    async def shared_client(self, server_endpoint: str):
        """Shared client for tests to reduce connection overhead."""
        client = Client(server_endpoint)
        async with client:
            yield client

    async def test_server_connectivity(self, server_endpoint: str):
        """Test that server responds to ping."""
        client = Client(server_endpoint)
        async with client:
            await client.ping()

    async def test_list_tools(self, server_endpoint: str):
        """Test that all expected tools are available."""
        expected_tools = {
            "blog_info",
            "random_blog",
            "read_blog_post",
            "random_blog_url",
            "blog_search"
        }

        client = Client(server_endpoint)
        async with client:
            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools}

            assert expected_tools == tool_names, f"Missing tools: {expected_tools - tool_names}"

            # Check each tool has description
            for tool in tools:
                assert tool.description, f"Tool {tool.name} missing description"

    async def test_blog_info_tool(self, server_endpoint: str):
        """Test blog_info tool returns expected information."""
        client = Client(server_endpoint)
        async with client:
            result = await client.call_tool("blog_info")

            content_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])

            assert "Igor's Blog" in content_text
            assert "idvork.in" in content_text
            assert "Available tools:" in content_text
            assert "blog_info" in content_text
            assert "random_blog" in content_text

    async def test_random_blog_url_tool(self, server_endpoint: str):
        """Test random_blog_url returns valid URL."""
        client = Client(server_endpoint)
        async with client:
            result = await client.call_tool("random_blog_url")

            content_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])

            # Should return a URL
            assert content_text.startswith("https://")
            assert "idvork.in" in content_text or "github.com" in content_text

    async def test_random_blog_tool_without_content(self, server_endpoint: str):
        """Test random_blog tool without content."""
        client = Client(server_endpoint)
        async with client:
            result = await client.call_tool("random_blog", {"include_content": False})

            content_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])

            # Accept either format: "Random Blog Post:" or "Random blog post URL:"
            assert ("Random Blog Post:" in content_text or "Random blog post URL:" in content_text)
            assert ("Title:" in content_text or "URL:" in content_text or "https://" in content_text)

    async def test_random_blog_tool_with_content(self, server_endpoint: str):
        """Test random_blog tool with content."""
        client = Client(server_endpoint)
        async with client:
            result = await client.call_tool("random_blog", {"include_content": True})

            content_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])

            assert "Random Blog Post:" in content_text
            assert "Title:" in content_text
            assert "URL:" in content_text
            assert "Content:" in content_text

    async def test_blog_search_tool(self, server_endpoint: str):
        """Test blog_search tool with common terms."""
        test_queries = ["leadership", "technology", "the", "career"]

        client = Client(server_endpoint)
        async with client:
            for query in test_queries:
                result = await client.call_tool("blog_search", {"query": query, "limit": 3})

                content_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])

                # Should either find results or report no results
                assert (
                    f"Found" in content_text and "blog posts matching" in content_text
                ) or (
                    "No blog posts found" in content_text
                )

    async def test_blog_search_empty_query(self, server_endpoint: str):
        """Test blog_search with empty query returns error."""
        client = Client(server_endpoint)
        async with client:
            result = await client.call_tool("blog_search", {"query": "", "limit": 5})

            content_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])

            assert "Error: Search query is required" in content_text

    async def test_blog_search_limit_parameter(self, server_endpoint: str):
        """Test blog_search respects limit parameter."""
        client = Client(server_endpoint)
        async with client:
            # Try with small limit
            result = await client.call_tool("blog_search", {"query": "the", "limit": 2})

            content_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])

            # If results found, should respect limit
            if "Found" in content_text:
                # Count the number of "Title:" occurrences (each result has one)
                title_count = content_text.count("Title:")
                assert title_count <= 2, f"Limit not respected: found {title_count} results"

    async def test_read_blog_post_invalid_url(self, server_endpoint: str):
        """Test read_blog_post with invalid URL."""
        client = Client(server_endpoint)
        async with client:
            result = await client.call_tool("read_blog_post", {"url": ""})

            content_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])

            assert "Error: URL must be a non-empty string" in content_text

    async def test_read_blog_post_nonexistent_url(self, server_endpoint: str):
        """Test read_blog_post with nonexistent URL."""
        client = Client(server_endpoint)
        async with client:
            result = await client.call_tool("read_blog_post", {
                "url": "https://idvork.in/nonexistent-post-12345"
            })

            content_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])

            assert "Blog post not found" in content_text

    async def test_error_handling_malformed_parameters(self, server_endpoint: str):
        """Test error handling with malformed parameters."""
        client = Client(server_endpoint)
        async with client:
            # Test blog_search with invalid limit
            try:
                result = await client.call_tool("blog_search", {"query": "test", "limit": -1})
                content_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                # Should handle gracefully (either error message or default limit)
                assert len(content_text) > 0
            except Exception as e:
                # MCP protocol might reject invalid parameters
                assert "limit" in str(e).lower()


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def main():
    """Run production tests."""
    endpoint = get_server_endpoint()

    if endpoint == LOCAL_ENDPOINT:
        print("\n🏠 Running against LOCAL server")
        print("   Start server with: just serve-http")
    else:
        print("\n🌐 Running against PRODUCTION server")

    # Run the tests
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    main()