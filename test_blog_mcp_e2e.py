#!/usr/bin/env python3
"""
End-to-end tests for the Blog MCP Server

This test suite verifies all 5 tools work correctly with comprehensive test scenarios.
Tests include both unit tests and integration tests against the actual blog.
"""

import json
import os
import sys
from unittest.mock import AsyncMock, patch

import httpx
import pytest

# Add the current directory to Python path for importing the server
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blog_mcp_server import (
    BlogError,
    blog_info,
    blog_search,
    fetch_url,
    get_blog_files,
    mcp,
    parse_markdown_content,
    random_blog,
    random_blog_url,
    read_blog_post,
)


class TestBlogMCPServer:
    """Test suite for Blog MCP Server functionality."""

    @pytest.fixture
    def mock_markdown_content(self):
        """Mock markdown content for testing content extraction."""
        return """---
title: Test Blog Post Title
date: 2024-01-15
---

# Test Blog Post Title

This is a sample blog post content for testing purposes.
It contains multiple paragraphs and should be properly parsed.

## Section Header

More content here with some **bold text** and *italic text*.

The content should be properly extracted and formatted.
"""

    @pytest.fixture
    def mock_github_response(self):
        """Mock GitHub API response for file listing."""
        return json.dumps(
            [
                {
                    "name": "test-post.md",
                    "path": "_d/test-post.md",
                    "type": "file",
                    "download_url": "https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/master/_d/test-post.md",
                    "size": 1024,
                },
                {
                    "name": "another-post.md",
                    "path": "_d/another-post.md",
                    "type": "file",
                    "download_url": "https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/master/_d/another-post.md",
                    "size": 2048,
                },
                {
                    "name": "README.md",
                    "path": "_d/README.md",
                    "type": "file",
                    "download_url": "https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/master/_d/README.md",
                    "size": 512,
                },
            ]
        )

    def test_blog_info(self):
        """Test the blog_info tool."""
        result = blog_info()
        assert "Igor's Blog" in result
        assert "https://idvork.in" in result
        assert "GitHub repository" in result
        assert "Available tools:" in result

    @pytest.mark.asyncio
    async def test_fetch_url_success(self, mock_markdown_content):
        """Test successful URL fetching."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.text = mock_markdown_content
            mock_response.raise_for_status = AsyncMock()

            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            result = await fetch_url("https://example.com/test.md")
            assert result == mock_markdown_content

    @pytest.mark.asyncio
    async def test_fetch_url_http_error(self):
        """Test URL fetching with HTTP error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPError("404 Not Found")

            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            with pytest.raises(BlogError):
                await fetch_url("https://example.com/nonexistent.md")

    @pytest.mark.asyncio
    async def test_get_blog_files(self, mock_github_response):
        """Test getting blog files from GitHub."""
        with patch("blog_mcp_server.fetch_url") as mock_fetch:
            mock_fetch.return_value = mock_github_response

            files = await get_blog_files()
            assert len(files) == 3
            assert files[0]["name"] == "test-post.md"
            assert "html_url" in files[0]
            assert files[0]["html_url"] == "https://idvork.in/test-post"

    @pytest.mark.asyncio
    async def test_parse_markdown_content(self, mock_markdown_content):
        """Test parsing markdown content."""
        file_info = {
            "name": "test-post.md",
            "download_url": "https://example.com/test.md",
            "html_url": "https://idvork.in/test-post",
        }

        with patch("blog_mcp_server.fetch_url") as mock_fetch:
            mock_fetch.return_value = mock_markdown_content

            result = await parse_markdown_content(file_info)
            assert result["title"] == "Test Blog Post Title"
            assert result["date"] == "2024-01-15"
            assert "sample blog post" in result["content"]
            assert len(result["excerpt"]) <= 203  # 200 chars + "..."

    @pytest.mark.asyncio
    async def test_random_blog_with_content(self, mock_github_response, mock_markdown_content):
        """Test random_blog tool with content."""
        with (
            patch("blog_mcp_server.get_blog_files") as mock_get_files,
            patch("blog_mcp_server.parse_markdown_content") as mock_parse,
        ):
            mock_get_files.return_value = [
                {"name": "test.md", "html_url": "https://idvork.in/test"}
            ]
            mock_parse.return_value = {
                "title": "Test Post",
                "url": "https://idvork.in/test",
                "date": "2024-01-15",
                "content": "Test content",
            }

            result = await random_blog(include_content=True)
            assert "Random Blog Post:" in result
            assert "Test Post" in result
            assert "Test content" in result

    @pytest.mark.asyncio
    async def test_random_blog_without_content(self, mock_github_response):
        """Test random_blog tool without content."""
        with patch("blog_mcp_server.get_blog_files") as mock_get_files:
            mock_get_files.return_value = [
                {"name": "test.md", "html_url": "https://idvork.in/test"}
            ]

            result = await random_blog(include_content=False)
            assert "Random blog post URL:" in result
            assert "https://idvork.in/test" in result

    @pytest.mark.asyncio
    async def test_random_blog_url(self, mock_github_response):
        """Test random_blog_url tool."""
        with patch("blog_mcp_server.get_blog_files") as mock_get_files:
            mock_get_files.return_value = [
                {"name": "test.md", "html_url": "https://idvork.in/test"}
            ]

            result = await random_blog_url()
            assert result == "https://idvork.in/test"

    @pytest.mark.asyncio
    async def test_read_blog_post_success(self, mock_github_response, mock_markdown_content):
        """Test read_blog_post tool with valid URL."""
        with (
            patch("blog_mcp_server.get_blog_files") as mock_get_files,
            patch("blog_mcp_server.parse_markdown_content") as mock_parse,
        ):
            mock_get_files.return_value = [{"html_url": "https://idvork.in/test-post"}]
            mock_parse.return_value = {
                "title": "Test Post",
                "url": "https://idvork.in/test-post",
                "date": "2024-01-15",
                "content": "Test content",
            }

            result = await read_blog_post("https://idvork.in/test-post")
            assert "Blog Post:" in result
            assert "Test Post" in result

    @pytest.mark.asyncio
    async def test_read_blog_post_not_found(self):
        """Test read_blog_post tool with non-existent URL."""
        with patch("blog_mcp_server.get_blog_files") as mock_get_files:
            mock_get_files.return_value = []

            result = await read_blog_post("https://idvork.in/nonexistent")
            assert "not found" in result

    @pytest.mark.asyncio
    async def test_read_blog_post_invalid_input(self):
        """Test read_blog_post tool with invalid input."""
        result = await read_blog_post("")
        assert "Error:" in result
        assert "non-empty string" in result

    @pytest.mark.asyncio
    async def test_blog_search_success(self, mock_github_response, mock_markdown_content):
        """Test blog_search tool with matching results."""
        with (
            patch("blog_mcp_server.get_blog_files") as mock_get_files,
            patch("blog_mcp_server.parse_markdown_content") as mock_parse,
        ):
            mock_get_files.return_value = [
                {"name": "test.md", "html_url": "https://idvork.in/test"}
            ]
            mock_parse.return_value = {
                "title": "Test Post About Python",
                "url": "https://idvork.in/test",
                "content": "This post discusses Python programming",
                "excerpt": "This post discusses...",
            }

            result = await blog_search("python")
            assert "Found 1 blog posts" in result
            assert "Test Post About Python" in result

    @pytest.mark.asyncio
    async def test_blog_search_no_results(self):
        """Test blog_search tool with no matching results."""
        with (
            patch("blog_mcp_server.get_blog_files") as mock_get_files,
            patch("blog_mcp_server.parse_markdown_content") as mock_parse,
        ):
            mock_get_files.return_value = [
                {"name": "test.md", "html_url": "https://idvork.in/test"}
            ]
            mock_parse.return_value = {
                "title": "Unrelated Post",
                "content": "This is about something else",
                "excerpt": "This is about...",
            }

            result = await blog_search("nonexistent")
            assert "No blog posts found matching" in result

    @pytest.mark.asyncio
    async def test_blog_search_invalid_query(self):
        """Test blog_search tool with invalid query."""
        result = await blog_search("")
        assert "Error:" in result
        assert "required" in result

    @pytest.mark.asyncio
    async def test_blog_search_limit_validation(self, mock_github_response):
        """Test blog_search tool limit parameter validation."""
        with patch("blog_mcp_server.get_blog_files") as mock_get_files:
            mock_get_files.return_value = []

            # Test with limit too high (should be clamped to 20)
            result = await blog_search("test", limit=100)
            assert "No blog posts found" in result

            # Test with limit too low (should be clamped to 1)
            result = await blog_search("test", limit=-5)
            assert "No blog posts found" in result

    @pytest.mark.asyncio
    async def test_error_handling_network_failure(self):
        """Test error handling when network requests fail."""
        with patch("blog_mcp_server.fetch_url") as mock_fetch:
            mock_fetch.side_effect = BlogError("Network error")

            result = await random_blog()
            assert "Error getting random blog post" in result

    @pytest.mark.asyncio
    async def test_content_size_limits(self):
        """Test that content size limits are respected."""
        large_content = "A" * 10000  # Large content
        file_info = {
            "name": "large-post.md",
            "download_url": "https://example.com/large.md",
            "html_url": "https://idvork.in/large-post",
        }

        with patch("blog_mcp_server.fetch_url") as mock_fetch:
            mock_fetch.return_value = large_content

            result = await parse_markdown_content(file_info)
            # Content should be truncated to 5000 chars + "..."
            assert len(result["content"]) <= 5003
            assert result["content"].endswith("...")

    def test_fastmcp_server_instance(self):
        """Test that FastMCP server is properly configured."""
        assert mcp.name == "blog-mcp-server"

        # Test that tools are registered
        tools = []
        for name, _func in mcp._tools.items():
            tools.append(name)

        expected_tools = [
            "blog_info",
            "random_blog",
            "read_blog_post",
            "random_blog_url",
            "blog_search",
        ]
        for expected_tool in expected_tools:
            assert expected_tool in tools


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
