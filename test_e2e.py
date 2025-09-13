#!/usr/bin/env python3
"""
E2E tests for the Blog MCP Server against deployed endpoints.

Tests against live endpoints (local or production) without mocking.
Use MCP_SERVER_ENDPOINT environment variable to specify the endpoint.
"""

import asyncio
import os

import pytest
from test_utils import MCPTestClient, BlogAssertions

# Server endpoints
LOCAL_ENDPOINT = "http://localhost:8000/mcp"
PRODUCTION_ENDPOINT = "https://idvorkin-blog-mcp.fastmcp.app/mcp"


def get_server_endpoint() -> str:
    """Get server endpoint from environment variable or default to local."""
    endpoint = os.getenv("MCP_SERVER_ENDPOINT", LOCAL_ENDPOINT)
    print(f"Testing against: {endpoint}")
    return endpoint


class TestE2EBlogMCPServer:
    """E2E tests for Blog MCP Server against live endpoints."""

    @pytest.fixture(scope="class")
    def server_endpoint(self) -> str:
        """Get the server endpoint for testing."""
        return get_server_endpoint()

    @pytest.fixture
    def assertions(self):
        """Provide assertions helper."""
        return BlogAssertions()

    async def test_server_connectivity(self, server_endpoint: str):
        """Test that server responds to ping."""
        async with MCPTestClient(server_endpoint) as client:
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

        async with MCPTestClient(server_endpoint) as client:
            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools}

            assert expected_tools == tool_names, f"Missing tools: {expected_tools - tool_names}"

            # Check each tool has description
            for tool in tools:
                assert tool.description, f"Tool {tool.name} missing description"

    async def test_blog_info_tool(self, server_endpoint: str, assertions):
        """Test blog_info tool returns expected information."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("blog_info")
            assertions.assert_blog_info(content)
            assert "blog_info" in content
            assert "random_blog" in content

    async def test_random_blog_url_tool(self, server_endpoint: str, assertions):
        """Test random_blog_url returns valid URL."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("random_blog_url")
            assertions.assert_valid_url(content)

    async def test_random_blog_tool_without_content(self, server_endpoint: str, assertions):
        """Test random_blog tool without content."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("random_blog", {"include_content": False})
            assertions.assert_random_blog_post(content, with_content=False)

    async def test_random_blog_tool_with_content(self, server_endpoint: str, assertions):
        """Test random_blog tool with content."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("random_blog", {"include_content": True})
            assertions.assert_random_blog_post(content, with_content=True)

    async def test_blog_search_tool(self, server_endpoint: str, assertions):
        """Test blog_search tool with common terms."""
        test_queries = ["leadership", "technology", "the", "career"]

        async with MCPTestClient(server_endpoint) as client:
            for query in test_queries:
                content = await client.call_tool("blog_search", {"query": query, "limit": 3})
                assertions.assert_search_results(content, query)

    async def test_blog_search_empty_query(self, server_endpoint: str, assertions):
        """Test blog_search with empty query returns error."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("blog_search", {"query": "", "limit": 5})
            assertions.assert_error_message(content, "Error: Search query is required")

    async def test_blog_search_limit_parameter(self, server_endpoint: str):
        """Test blog_search respects limit parameter."""
        async with MCPTestClient(server_endpoint) as client:
            # Try with small limit
            content = await client.call_tool("blog_search", {"query": "the", "limit": 2})

            # If results found, should respect limit
            if "Found" in content:
                # Count the number of "Title:" occurrences (each result has one)
                title_count = content.count("Title:")
                assert title_count <= 2, f"Limit not respected: found {title_count} results"

    async def test_read_blog_post_invalid_url(self, server_endpoint: str, assertions):
        """Test read_blog_post with invalid URL."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("read_blog_post", {"url": ""})
            assertions.assert_error_message(content, "Error: URL must be a non-empty string")

    async def test_read_blog_post_nonexistent_url(self, server_endpoint: str, assertions):
        """Test read_blog_post with nonexistent URL."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("read_blog_post", {
                "url": "https://idvork.in/nonexistent-post-12345"
            })
            assertions.assert_error_message(content, "Blog post not found")

    async def test_error_handling_malformed_parameters(self, server_endpoint: str):
        """Test error handling with malformed parameters."""
        async with MCPTestClient(server_endpoint) as client:
            # Test blog_search with invalid limit
            try:
                content = await client.call_tool("blog_search", {"query": "test", "limit": -1})
                # Should handle gracefully (either error message or default limit)
                assert len(content) > 0
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