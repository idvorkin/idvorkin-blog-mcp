#!/usr/bin/env python3
"""
Unit tests for the Blog MCP Server using real GitHub API.

Tests use real GitHub API calls for simplicity and reliability.
The API is fast and the blog data is stable, so mocking isn't necessary.
"""

import os
import sys

import pytest
from test_utils import MCPTestClient, BlogAssertions

# Add the current directory to Python path for importing the server
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blog_mcp_server


class TestBlogMCPServer:
    """Unit tests for Blog MCP Server with real GitHub API."""

    @pytest.fixture
    def mcp_server(self):
        """Provide the FastMCP server instance for testing."""
        return blog_mcp_server.mcp

    @pytest.fixture
    def assertions(self):
        """Provide assertions helper."""
        return BlogAssertions()

    async def test_blog_info_tool(self, mcp_server, assertions):
        """Test blog_info tool returns expected information."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("blog_info")
            assertions.assert_blog_info(content)

    async def test_random_blog_tool_without_content(self, mcp_server, assertions):
        """Test random_blog tool without content."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("random_blog", {"include_content": False})
            assertions.assert_random_blog_post(content, with_content=False)

    async def test_random_blog_tool_with_content(self, mcp_server, assertions):
        """Test random_blog tool with content."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("random_blog", {"include_content": True})
            assertions.assert_random_blog_post(content, with_content=True)

    async def test_random_blog_url_tool(self, mcp_server, assertions):
        """Test random_blog_url tool returns valid URL."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("random_blog_url")
            assertions.assert_valid_url(content)

    async def test_read_blog_post_invalid_url(self, mcp_server, assertions):
        """Test read_blog_post with invalid URL."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("read_blog_post", {"url": ""})
            assertions.assert_error_message(content, "Error: URL must be a non-empty string")

    async def test_read_blog_post_nonexistent_url(self, mcp_server, assertions):
        """Test read_blog_post with nonexistent URL."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("read_blog_post", {
                "url": "https://idvork.in/nonexistent-post-99999"
            })
            assertions.assert_error_message(content, "Blog post not found")

    async def test_blog_search_tool(self, mcp_server, assertions):
        """Test blog_search tool with common terms."""
        async with MCPTestClient(mcp_server) as client:
            # Search for a common word that should return results
            content = await client.call_tool("blog_search", {
                "query": "leadership",
                "limit": 3
            })
            assertions.assert_search_results(content, "leadership")

    async def test_blog_search_empty_query(self, mcp_server, assertions):
        """Test blog_search with empty query."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("blog_search", {"query": "", "limit": 5})
            assertions.assert_error_message(content, "Error: Search query is required")

    async def test_blog_search_limit(self, mcp_server):
        """Test blog_search respects limit parameter."""
        async with MCPTestClient(mcp_server) as client:
            # Search with small limit
            content = await client.call_tool("blog_search", {
                "query": "the",  # Very common word
                "limit": 2
            })

            # If results found, count them
            if "Found" in content and "blog posts matching" in content:
                # Count title occurrences (each result has one)
                title_count = content.count("Title:")
                assert title_count <= 2, f"Limit not respected: found {title_count} results"

    def test_server_configuration(self):
        """Test that the FastMCP server is properly configured."""
        assert blog_mcp_server.mcp.name == "blog-mcp-server"

        # Verify tools are registered
        expected_tools = [
            "blog_info",
            "random_blog",
            "read_blog_post",
            "random_blog_url",
            "blog_search"
        ]

        for tool_name in expected_tools:
            assert hasattr(blog_mcp_server, tool_name)
            tool = getattr(blog_mcp_server, tool_name)
            assert tool.__class__.__name__ == "FunctionTool"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])