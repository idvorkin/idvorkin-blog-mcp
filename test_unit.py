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
            # blog_search now returns JSON
            import json
            data = json.loads(content)

            # Check structure
            assert "query" in data
            assert data["query"] == "leadership"
            assert "count" in data
            assert "posts" in data

            # If posts found, verify structure
            if data["count"] > 0:
                assert len(data["posts"]) > 0
                assert "title" in data["posts"][0]
                assert "url" in data["posts"][0]

    async def test_blog_search_empty_query(self, mcp_server, assertions):
        """Test blog_search with empty query."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("blog_search", {"query": "", "limit": 5})
            assertions.assert_error_message(content, "Search query is required and must be a non-empty string")

    async def test_blog_search_limit(self, mcp_server):
        """Test blog_search respects limit parameter."""
        async with MCPTestClient(mcp_server) as client:
            # Search with small limit
            content = await client.call_tool("blog_search", {
                "query": "the",  # Very common word
                "limit": 2
            })

            import json
            data = json.loads(content)

            # If results found, check limit is respected
            if "posts" in data and data.get("count", 0) > 0:
                assert len(data["posts"]) <= 2, f"Limit not respected: found {len(data['posts'])} results"
                assert data["limit"] == 2

    async def test_recent_blog_posts(self, mcp_server):
        """Test recent_blog_posts returns JSON with recent posts."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("recent_blog_posts", {"limit": 3})
            
            # Should return valid JSON
            import json
            data = json.loads(content)
            
            # Check structure
            assert "count" in data
            assert "limit" in data
            assert "posts" in data
            assert isinstance(data["posts"], list)
            assert data["limit"] == 3
            assert data["count"] <= 3
            
            # If posts exist, check structure
            if data["posts"]:
                post = data["posts"][0]
                required_fields = ["title", "url", "description", "last_modified", "doc_size", "markdown_path", "file_path", "redirect_url"]
                for field in required_fields:
                    assert field in post, f"Missing field: {field}"

    async def test_all_blog_posts(self, mcp_server):
        """Test all_blog_posts returns JSON with all posts."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("all_blog_posts", {})
            
            # Should return valid JSON
            import json
            data = json.loads(content)
            
            # Check structure
            assert "count" in data
            assert "posts" in data
            assert isinstance(data["posts"], list)
            assert data["count"] > 0  # Should have some posts
            
            # Check first post structure
            if data["posts"]:
                post = data["posts"][0]
                required_fields = ["title", "url", "description", "last_modified", "doc_size", "markdown_path", "file_path", "redirect_url"]
                for field in required_fields:
                    assert field in post, f"Missing field: {field}"

    async def test_blog_search_json_format(self, mcp_server):
        """Test blog_search returns proper JSON format."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("blog_search", {
                "query": "the",  # Very common word that should match posts
                "limit": 2
            })
            
            # Should return valid JSON
            import json
            data = json.loads(content)
            
            # Check if we got results or error
            if "error" in data:
                # If no results, that's also valid JSON
                assert isinstance(data["error"], str)
                assert len(data["error"]) > 0
            else:
                # Check structure for successful results
                assert "query" in data
                assert "count" in data
                assert "limit" in data
                assert "posts" in data
                assert isinstance(data["posts"], list)
                assert data["query"] == "the"
                assert data["limit"] == 2
                assert data["count"] <= 2
                
                # If posts exist, check structure
                if data["posts"]:
                    post = data["posts"][0]
                    required_fields = ["title", "url", "description", "last_modified", "doc_size", "markdown_path", "file_path", "redirect_url"]
                    for field in required_fields:
                        assert field in post, f"Missing field: {field}"

    def test_server_configuration(self):
        """Test that the FastMCP server is properly configured."""
        assert blog_mcp_server.mcp.name == "blog-mcp-server"

        # Verify tools are registered
        expected_tools = [
            "blog_info",
            "random_blog",
            "read_blog_post",
            "random_blog_url",
            "blog_search",
            "recent_blog_posts",
            "all_blog_posts"
        ]

        for tool_name in expected_tools:
            assert hasattr(blog_mcp_server, tool_name)
            tool = getattr(blog_mcp_server, tool_name)
            assert tool.__class__.__name__ == "FunctionTool"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])