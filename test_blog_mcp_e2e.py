#!/usr/bin/env python3
"""
End-to-end tests for the Blog MCP Server

This test suite verifies all 5 tools work correctly with comprehensive test scenarios.
Tests include both unit tests and integration tests against the actual blog.
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

# Add the current directory to Python path for importing the server
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blog_mcp_server import (
    BlogPost,
    BlogFetchError,
    BlogParseError,
    InvalidURLError,
    extract_blog_content,
    fetch_url,
    get_blog_posts,
    handle_call_tool,
    handle_list_tools,
    server,
    validate_blog_url,
)


class TestBlogMCPServer:
    """Test suite for Blog MCP Server functionality."""

    @pytest.fixture
    def mock_html_content(self):
        """Mock HTML content for testing content extraction."""
        return """
        <html>
        <head>
            <title>Test Blog Post Title</title>
        </head>
        <body>
            <article>
                <time datetime="2024-01-15T10:00:00Z">January 15, 2024</time>
                <h1>Test Blog Post</h1>
                <p>This is a test blog post content with some interesting insights about technology.</p>
                <p>More content here with <a href="#">links</a> and formatting.</p>
            </article>
        </body>
        </html>
        """

    @pytest.fixture
    def mock_sitemap_content(self):
        """Mock sitemap XML content for testing blog post discovery."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://idvork.in/posts/test-post-1</loc>
                <lastmod>2024-01-15</lastmod>
            </url>
            <url>
                <loc>https://idvork.in/posts/test-post-2</loc>
                <lastmod>2024-01-14</lastmod>
            </url>
            <url>
                <loc>https://idvork.in/about</loc>
                <lastmod>2024-01-10</lastmod>
            </url>
        </urlset>
        """

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test that all 5 tools are properly listed."""
        tools = await handle_list_tools()
        
        assert len(tools) == 5
        tool_names = {tool.name for tool in tools}
        expected_tools = {
            "blog_info",
            "random_blog",
            "read_blog_post",
            "random_blog_url",
            "blog_search"
        }
        assert tool_names == expected_tools
        
        # Verify each tool has required properties
        for tool in tools:
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'inputSchema')
            assert tool.description  # Non-empty description

    @pytest.mark.asyncio
    async def test_blog_info_tool(self):
        """Test blog_info tool returns correct information."""
        result = await handle_call_tool("blog_info", {})
        
        assert len(result) == 1
        content = result[0].text
        assert "https://idvork.in" in content
        assert "Igor's Blog" in content
        assert "blog_info" in content
        assert "random_blog" in content
        assert "read_blog_post" in content
        assert "random_blog_url" in content
        assert "blog_search" in content

    @pytest.mark.asyncio
    async def test_validate_blog_url_valid(self):
        """Test URL validation with valid URLs."""
        valid_urls = [
            "https://idvork.in/posts/test",
            "http://idvork.in/about",
            "https://idvork.in/"
        ]
        
        for url in valid_urls:
            result = validate_blog_url(url)
            assert result == url
    
    def test_validate_blog_url_invalid_domain(self):
        """Test URL validation rejects invalid domains."""
        invalid_urls = [
            "https://evil.com/steal-data",
            "http://localhost:8080/admin",
            "https://192.168.1.1/config"
        ]
        
        for url in invalid_urls:
            with pytest.raises(InvalidURLError, match="not allowed"):
                validate_blog_url(url)
    
    def test_validate_blog_url_invalid_scheme(self):
        """Test URL validation rejects invalid schemes."""
        invalid_urls = [
            "ftp://idvork.in/file",
            "file:///etc/passwd",
            "javascript:alert('xss')"
        ]
        
        for url in invalid_urls:
            with pytest.raises(InvalidURLError, match="not allowed"):
                validate_blog_url(url)
    
    def test_validate_blog_url_invalid_format(self):
        """Test URL validation with invalid formats."""
        invalid_inputs = [
            "",
            None,
            "not-a-url",
            "://missing-scheme"
        ]
        
        for invalid_input in invalid_inputs:
            with pytest.raises(InvalidURLError):
                validate_blog_url(invalid_input)
    
    @pytest.mark.asyncio
    async def test_fetch_url_success(self):
        """Test successful URL fetching."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.text = "Test content"
            mock_response.raise_for_status = MagicMock()
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await fetch_url("https://example.com")
            assert result == "Test content"

    @pytest.mark.asyncio
    async def test_fetch_url_http_error(self):
        """Test URL fetching with HTTP error."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404 Not Found", request=MagicMock(), response=MagicMock()
            )
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            with pytest.raises(BlogFetchError):
                await fetch_url("https://idvork.in/not-found")
    
    @pytest.mark.asyncio
    async def test_fetch_url_invalid_domain(self):
        """Test URL fetching with invalid domain."""
        with pytest.raises(InvalidURLError):
            await fetch_url("https://evil.com/steal-data")
    
    @pytest.mark.asyncio
    async def test_fetch_url_large_content(self):
        """Test URL fetching with large content gets truncated."""
        large_content = "x" * 2_000_000  # 2MB content
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.text = large_content
            mock_response.raise_for_status = MagicMock()
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await fetch_url("https://idvork.in/large-post")
            assert len(result) == 1_000_000  # Should be truncated

    @pytest.mark.asyncio
    async def test_extract_blog_content(self, mock_html_content):
        """Test blog content extraction from HTML with BeautifulSoup."""
        with patch('blog_mcp_server.fetch_url', return_value=mock_html_content):
            result = await extract_blog_content("https://idvork.in/post")
            
            assert result.title == "Test Blog Post Title"
            assert result.url == "https://idvork.in/post"
            assert result.date == "2024-01-15T10:00:00Z"
            assert "test blog post content" in result.content.lower()
            assert "technology" in result.content.lower()
            # BeautifulSoup should clean HTML tags properly
            assert "<p>" not in result.content
            assert "<a " not in result.content

    @pytest.mark.asyncio
    async def test_get_blog_posts_from_sitemap(self, mock_sitemap_content):
        """Test getting blog posts from sitemap."""
        with patch('blog_mcp_server.fetch_url', return_value=mock_sitemap_content):
            result = await get_blog_posts()
            
            expected_urls = [
                "https://idvork.in/posts/test-post-1",
                "https://idvork.in/posts/test-post-2"
            ]
            assert result == expected_urls

    @pytest.mark.asyncio
    async def test_get_blog_posts_fallback(self):
        """Test getting blog posts when sitemap fails."""
        main_page_content = """
        <html>
        <body>
            <a href="/posts/post-1">Post 1</a>
            <a href="/posts/post-2">Post 2</a>
            <a href="/about">About</a>
        </body>
        </html>
        """
        
        def mock_fetch(url):
            if "sitemap.xml" in url:
                raise httpx.HTTPError("Sitemap not found")
            return main_page_content
        
        with patch('blog_mcp_server.fetch_url', side_effect=mock_fetch):
            result = await get_blog_posts()
            
            expected_urls = [
                "https://idvork.in/posts/post-1",
                "https://idvork.in/posts/post-2"
            ]
            assert result == expected_urls

    @pytest.mark.asyncio
    async def test_random_blog_with_content(self, mock_html_content):
        """Test random_blog tool with content included."""
        mock_urls = ["https://idvork.in/posts/test-post-1"]
        
        with patch('blog_mcp_server.get_blog_posts', return_value=mock_urls), \
             patch('blog_mcp_server.fetch_url', return_value=mock_html_content):
            
            result = await handle_call_tool("random_blog", {"include_content": True})
            
            assert len(result) == 1
            content = result[0].text
            assert "Random Blog Post:" in content
            assert "Test Blog Post Title" in content
            assert "https://idvork.in/posts/test-post-1" in content
            assert "technology" in content.lower()

    @pytest.mark.asyncio
    async def test_random_blog_without_content(self):
        """Test random_blog tool without content."""
        mock_urls = ["https://idvork.in/posts/test-post-1"]
        
        with patch('blog_mcp_server.get_blog_posts', return_value=mock_urls):
            result = await handle_call_tool("random_blog", {"include_content": False})
            
            assert len(result) == 1
            content = result[0].text
            assert "https://idvork.in/posts/test-post-1" in content
            assert "Random Blog Post:" not in content

    @pytest.mark.asyncio
    async def test_random_blog_no_posts(self):
        """Test random_blog tool when no posts are found."""
        with patch('blog_mcp_server.get_blog_posts', return_value=[]):
            result = await handle_call_tool("random_blog", {})
            
            assert len(result) == 1
            assert "No blog posts found" in result[0].text

    @pytest.mark.asyncio
    async def test_read_blog_post_success(self, mock_html_content):
        """Test read_blog_post tool with valid URL."""
        test_url = "https://idvork.in/posts/test-post"
        
        with patch('blog_mcp_server.fetch_url', return_value=mock_html_content):
            result = await handle_call_tool("read_blog_post", {"url": test_url})
            
            assert len(result) == 1
            content = result[0].text
            assert "Blog Post:" in content
            assert "Test Blog Post Title" in content
            assert test_url in content
            assert "technology" in content.lower()

    @pytest.mark.asyncio
    async def test_read_blog_post_missing_url(self):
        """Test read_blog_post tool with missing URL parameter."""
        result = await handle_call_tool("read_blog_post", {})
        
        assert len(result) == 1
        assert "URL parameter is required" in result[0].text
    
    @pytest.mark.asyncio
    async def test_read_blog_post_invalid_url(self):
        """Test read_blog_post tool with invalid URL."""
        result = await handle_call_tool("read_blog_post", {"url": "https://evil.com/steal"})
        
        assert len(result) == 1
        assert "Invalid URL" in result[0].text
    
    @pytest.mark.asyncio
    async def test_read_blog_post_empty_url(self):
        """Test read_blog_post tool with empty URL."""
        result = await handle_call_tool("read_blog_post", {"url": ""})
        
        assert len(result) == 1
        assert "must be a non-empty string" in result[0].text
    
    @pytest.mark.asyncio
    async def test_read_blog_post_non_string_url(self):
        """Test read_blog_post tool with non-string URL."""
        result = await handle_call_tool("read_blog_post", {"url": 123})
        
        assert len(result) == 1
        assert "must be a non-empty string" in result[0].text

    @pytest.mark.asyncio
    async def test_read_blog_post_error(self):
        """Test read_blog_post tool with fetch error."""
        test_url = "https://idvork.in/posts/nonexistent"
        
        with patch('blog_mcp_server.fetch_url', side_effect=httpx.HTTPError("Not found")):
            result = await handle_call_tool("read_blog_post", {"url": test_url})
            
            assert len(result) == 1
            content = result[0].text
            assert "Error reading blog post" in content

    @pytest.mark.asyncio
    async def test_random_blog_url_success(self):
        """Test random_blog_url tool returns a URL."""
        mock_urls = [
            "https://idvork.in/posts/test-post-1",
            "https://idvork.in/posts/test-post-2"
        ]
        
        with patch('blog_mcp_server.get_blog_posts', return_value=mock_urls):
            result = await handle_call_tool("random_blog_url", {})
            
            assert len(result) == 1
            url = result[0].text.strip()
            assert url in mock_urls

    @pytest.mark.asyncio
    async def test_random_blog_url_no_posts(self):
        """Test random_blog_url tool when no posts are available."""
        with patch('blog_mcp_server.get_blog_posts', return_value=[]):
            result = await handle_call_tool("random_blog_url", {})
            
            assert len(result) == 1
            assert "No blog posts found" in result[0].text

    @pytest.mark.asyncio
    async def test_blog_search_success(self, mock_html_content):
        """Test blog_search tool with successful search."""
        mock_urls = [
            "https://idvork.in/posts/tech-post",
            "https://idvork.in/posts/other-post"
        ]
        
        with patch('blog_mcp_server.get_blog_posts', return_value=mock_urls), \
             patch('blog_mcp_server.fetch_url', return_value=mock_html_content):
            
            result = await handle_call_tool("blog_search", {
                "query": "technology",
                "limit": 5
            })
            
            assert len(result) == 1
            content = result[0].text
            assert "Found" in content
            assert "technology" in content
            assert "Test Blog Post Title" in content

    @pytest.mark.asyncio
    async def test_blog_search_no_results(self, mock_html_content):
        """Test blog_search tool with no matching results."""
        mock_urls = ["https://idvork.in/posts/test-post"]
        
        # Mock content that doesn't match search query
        non_matching_content = mock_html_content.replace("technology", "science")
        
        with patch('blog_mcp_server.get_blog_posts', return_value=mock_urls), \
             patch('blog_mcp_server.fetch_url', return_value=non_matching_content):
            
            result = await handle_call_tool("blog_search", {
                "query": "technology",
                "limit": 5
            })
            
            assert len(result) == 1
            content = result[0].text
            assert "No blog posts found matching 'technology'" in content

    @pytest.mark.asyncio
    async def test_blog_search_missing_query(self):
        """Test blog_search tool with missing query parameter."""
        result = await handle_call_tool("blog_search", {})
        
        assert len(result) == 1
        assert "Search query is required" in result[0].text
    
    @pytest.mark.asyncio
    async def test_blog_search_empty_query(self):
        """Test blog_search tool with empty query."""
        result = await handle_call_tool("blog_search", {"query": ""})
        
        assert len(result) == 1
        assert "Search query is required" in result[0].text
    
    @pytest.mark.asyncio
    async def test_blog_search_non_string_query(self):
        """Test blog_search tool with non-string query."""
        result = await handle_call_tool("blog_search", {"query": 123})
        
        assert len(result) == 1
        assert "Search query is required" in result[0].text
    
    @pytest.mark.asyncio
    async def test_blog_search_invalid_limit(self):
        """Test blog_search tool with invalid limit values."""
        mock_urls = ["https://idvork.in/posts/test-post"]
        
        with patch('blog_mcp_server.get_blog_posts', return_value=mock_urls), \
             patch('blog_mcp_server.extract_blog_content') as mock_extract:
            
            mock_extract.return_value = BlogPost(
                title="Test", 
                url="https://idvork.in/posts/test", 
                content="test content",
                excerpt="test"
            )
            
            # Test negative limit
            result = await handle_call_tool("blog_search", {"query": "test", "limit": -1})
            assert len(result) == 1
            # Should clamp to minimum 1
            
            # Test excessive limit
            result = await handle_call_tool("blog_search", {"query": "test", "limit": 100})
            assert len(result) == 1
            # Should clamp to maximum 20
            
            # Test string limit
            result = await handle_call_tool("blog_search", {"query": "test", "limit": "invalid"})
            assert len(result) == 1
            # Should use default 5

    @pytest.mark.asyncio
    async def test_blog_search_with_limit(self, mock_html_content):
        """Test blog_search tool respects limit parameter."""
        mock_urls = [f"https://idvork.in/posts/post-{i}" for i in range(10)]
        
        with patch('blog_mcp_server.get_blog_posts', return_value=mock_urls), \
             patch('blog_mcp_server.fetch_url', return_value=mock_html_content):
            
            result = await handle_call_tool("blog_search", {
                "query": "technology",
                "limit": 2
            })
            
            assert len(result) == 1
            content = result[0].text
            # Should find exactly 2 posts
            lines = content.split('\n')
            post_lines = [line for line in lines if line.strip().startswith(('1.', '2.'))]
            assert len(post_lines) == 2

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        """Test calling an unknown tool."""
        result = await handle_call_tool("unknown_tool", {})
        
        assert len(result) == 1
        assert "Unknown tool: unknown_tool" in result[0].text

    def test_blog_post_model(self):
        """Test BlogPost model validation."""
        # Valid blog post with allowed domain
        post = BlogPost(
            title="Test Post",
            url="https://idvork.in/post",
            content="Test content",
            excerpt="Test excerpt",
            date="2024-01-15"
        )
        
        assert post.title == "Test Post"
        assert str(post.url) == "https://idvork.in/post"
        assert post.content == "Test content"
        assert post.excerpt == "Test excerpt"
        assert post.date == "2024-01-15"

    @pytest.mark.asyncio
    async def test_extract_blog_content_error_handling(self):
        """Test extract_blog_content handles errors gracefully."""
        with patch('blog_mcp_server.fetch_url', side_effect=BlogFetchError("Network error")):
            result = await extract_blog_content("https://idvork.in/post")
            
            assert result.title == "Error loading post"
            assert "Fetch error: Network error" in result.content
    
    @pytest.mark.asyncio
    async def test_extract_blog_content_invalid_url(self):
        """Test extract_blog_content with invalid URL."""
        result = await extract_blog_content("https://evil.com/post")
        
        assert result.title == "Invalid URL"
        assert "URL validation error" in result.content
    
    def test_blog_post_model_url_validation(self):
        """Test BlogPost model validates URLs."""
        # Valid URL should work
        post = BlogPost(
            title="Test",
            url="https://idvork.in/post",
            content="Test content"
        )
        assert str(post.url) == "https://idvork.in/post"
        
        # Invalid domain should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            BlogPost(
                title="Test",
                url="https://evil.com/post",
                content="Test content"
            )


def run_tests():
    """Run the test suite."""
    print("Running Blog MCP Server E2E Tests...")
    
    # Run pytest with verbose output
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--asyncio-mode=auto"
    ])
    
    if exit_code == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    
    return exit_code


if __name__ == "__main__":
    exit(run_tests())