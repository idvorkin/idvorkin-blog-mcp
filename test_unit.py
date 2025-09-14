#!/usr/bin/env python3
"""
Unit tests for the Blog MCP Server.

Tests use a mix of real GitHub API calls for sanity checks and mocked data
for comprehensive testing without hitting rate limits.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from test_utils import MCPTestClient, BlogAssertions

# Add the current directory to Python path for importing the server
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blog_mcp_server


# Mock data for testing
MOCK_COMMITS_LIST = [
    {
        "sha": "abc123def456789",
        "commit": {
            "author": {
                "name": "Test Author",
                "date": (datetime.now() - timedelta(days=2)).isoformat() + "Z"
            },
            "message": "Update blog post about AI\n\nAdded new section on GPT-4"
        }
    },
    {
        "sha": "def456ghi789012",
        "commit": {
            "author": {
                "name": "Another Author",
                "date": (datetime.now() - timedelta(days=5)).isoformat() + "Z"
            },
            "message": "Add new post about Python tips"
        }
    }
]

MOCK_COMMIT_DETAILS = {
    "abc123def456789": {
        "sha": "abc123def456789",
        "commit": MOCK_COMMITS_LIST[0]["commit"],
        "files": [
            {
                "filename": "_d/ai-thoughts.md",
                "status": "modified",
                "additions": 10,
                "deletions": 5,
                "patch": "@@ -1,5 +1,10 @@\n-old line\n+new line\n+another new line"
            },
            {
                "filename": "_d/machine-learning.md",
                "status": "modified",
                "additions": 25,
                "deletions": 3
            }
        ]
    },
    "def456ghi789012": {
        "sha": "def456ghi789012",
        "commit": MOCK_COMMITS_LIST[1]["commit"],
        "files": [
            {
                "filename": "_posts/python-tips.md",
                "status": "added",
                "additions": 150,
                "deletions": 0
            }
        ]
    }
}


class TestBlogMCPServer:
    """Unit tests for Blog MCP Server with mixed real/mock API calls."""

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

    async def test_random_blog_tool_with_content_real(self, mcp_server, assertions):
        """Test random_blog tool with content - REAL API CALL."""
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
        """Test read_blog_post with nonexistent URL - NOW FAST with backlinks fix."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("read_blog_post", {
                "url": "https://idvork.in/nonexistent-post-99999"
            })
            assertions.assert_error_message(content, "Blog post not found")

    async def test_blog_search_tool_real(self, mcp_server, assertions):
        """Test blog_search tool with common terms - REAL API CALL."""
        async with MCPTestClient(mcp_server) as client:
            # Search for a common word that should return results
            content = await client.call_tool("blog_search", {
                "query": "leadership",
                "limit": 2  # Reduced limit
            })
            # blog_search now returns JSON
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

    async def test_get_recent_changes_default_real(self, mcp_server, assertions):
        """Test get_recent_changes with default parameters - REAL API CALL."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("get_recent_changes", {"commits": 2})  # Limit to 2 for rate limits
            # Should return recent changes
            assert "Recent changes" in content
            assert "Commit:" in content or "No commits found" in content

    @patch('blog_mcp_server.httpx.AsyncClient')
    async def test_get_recent_changes_with_commits_mock(self, mock_client_class, mcp_server, assertions):
        """Test get_recent_changes with specific number of commits - MOCKED."""
        # Setup mock
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the commit responses
        async def side_effect(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            if "/commits/" in url and "abc123def456789" in url:
                response.json = MagicMock(return_value=MOCK_COMMIT_DETAILS["abc123def456789"])
            elif "/commits/" in url and "def456ghi789012" in url:
                response.json = MagicMock(return_value=MOCK_COMMIT_DETAILS["def456ghi789012"])
            elif url.endswith("/commits"):
                # This is the commits list request
                response.json = MagicMock(return_value=MOCK_COMMITS_LIST[:2])
            else:
                response.json = MagicMock(return_value=MOCK_COMMITS_LIST[0])
            return response

        mock_client.get = side_effect

        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("get_recent_changes", {"commits": 2})
            # Should mention 2 commits
            assert "Recent changes (last 2 commits)" in content
            assert "Commit: abc123d" in content  # First 7 chars of SHA
            assert "Test Author" in content
            assert not content.startswith("Error:")

    @patch('blog_mcp_server.httpx.AsyncClient')
    async def test_get_recent_changes_with_days_mock(self, mock_client_class, mcp_server, assertions):
        """Test get_recent_changes with days parameter - MOCKED."""
        # Setup mock
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the commit details responses
        async def side_effect(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            if "/commits/" in url:
                # Return appropriate mock based on SHA in URL
                for sha, details in MOCK_COMMIT_DETAILS.items():
                    if sha in url:
                        response.json = MagicMock(return_value=details)
                        return response
            response.json = MagicMock(return_value=MOCK_COMMITS_LIST)
            return response

        mock_client.get = side_effect

        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("get_recent_changes", {"days": 7})
            # Should mention last 7 days
            assert "Recent changes (last 7 days)" in content
            assert "2 days ago" in content or "5 days ago" in content

    @patch('blog_mcp_server.httpx.AsyncClient')
    async def test_get_recent_changes_with_path_mock(self, mock_client_class, mcp_server, assertions):
        """Test get_recent_changes with path filter - MOCKED."""
        # Setup mock
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the commit details
        async def side_effect(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            if "abc123def456789" in url:
                response.json = MagicMock(return_value=MOCK_COMMIT_DETAILS["abc123def456789"])
            else:
                response.json = MagicMock(return_value=[MOCK_COMMITS_LIST[0]])
            return response

        mock_client.get = side_effect

        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("get_recent_changes", {
                "path": "_d/",
                "commits": 10
            })
            # Should return changes for _d/ path
            assert "Recent changes" in content
            assert "_d/ai-thoughts.md" in content or "_d/machine-learning.md" in content

    async def test_get_recent_changes_invalid_params(self, mcp_server, assertions):
        """Test get_recent_changes with invalid parameter combinations."""
        async with MCPTestClient(mcp_server) as client:
            # Test both days and commits specified
            content = await client.call_tool("get_recent_changes", {
                "days": 7,
                "commits": 10
            })
            assertions.assert_error_message(content, "Cannot specify both 'days' and 'commits'")

            # Test negative days
            content = await client.call_tool("get_recent_changes", {"days": -1})
            assertions.assert_error_message(content, "'days' must be a positive number")

            # Test negative commits
            content = await client.call_tool("get_recent_changes", {"commits": -5})
            assertions.assert_error_message(content, "'commits' must be a positive number")

    @patch('blog_mcp_server.httpx.AsyncClient')
    async def test_get_recent_changes_with_diff_mock(self, mock_client_class, mcp_server, assertions):
        """Test get_recent_changes with include_diff enabled - MOCKED."""
        # Setup mock
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock commit with diff/patch
        async def side_effect(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            if "abc123def456789" in url:
                response.json = MagicMock(return_value=MOCK_COMMIT_DETAILS["abc123def456789"])
            else:
                response.json = MagicMock(return_value=[MOCK_COMMITS_LIST[0]])
            return response

        mock_client.get = side_effect

        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("get_recent_changes", {
                "commits": 1,
                "include_diff": True
            })
            # Should return changes with diff
            assert "Recent changes" in content
            assert "Files changed:" in content
            assert "Diff:" in content
            assert "@@" in content or "+new line" in content

    @patch('blog_mcp_server.get_blog_data')
    async def test_blog_search_limit_mock(self, mock_get_blog_data, mcp_server):
        """Test blog_search respects limit parameter - MOCKED."""
        # Mock the blog data
        mock_get_blog_data.return_value = {
            "url_info": {
                "/post1": {
                    "title": "The First Post",
                    "description": "Content with the word",
                    "markdown_path": "_d/post1.md",
                    "last_modified": "2024-01-01T00:00:00Z",
                    "doc_size": 1000,
                    "file_path": "_site/post1.html",
                    "redirect_url": ""
                },
                "/post2": {
                    "title": "The Second Post",
                    "description": "Another the content",
                    "markdown_path": "_d/post2.md",
                    "last_modified": "2024-01-02T00:00:00Z",
                    "doc_size": 2000,
                    "file_path": "_site/post2.html",
                    "redirect_url": ""
                },
                "/post3": {
                    "title": "The Third Post",
                    "description": "Yet another the post",
                    "markdown_path": "_d/post3.md",
                    "last_modified": "2024-01-03T00:00:00Z",
                    "doc_size": 3000,
                    "file_path": "_site/post3.html",
                    "redirect_url": ""
                }
            }
        }

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

    async def test_recent_blog_posts_real(self, mcp_server):
        """Test recent_blog_posts returns JSON with recent posts - REAL API CALL."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("recent_blog_posts", {"limit": 2})  # Reduced limit
            
            # Should return valid JSON
            import json
            data = json.loads(content)
            
            # Check structure
            assert "count" in data
            assert "limit" in data
            assert "posts" in data
            assert isinstance(data["posts"], list)
            assert data["limit"] == 2
            assert data["count"] <= 2
            
            # If posts exist, check structure
            if data["posts"]:
                post = data["posts"][0]
                required_fields = ["title", "url", "description", "last_modified", "doc_size", "markdown_path", "file_path", "redirect_url"]
                for field in required_fields:
                    assert field in post, f"Missing field: {field}"

    @patch('blog_mcp_server.get_blog_data')
    async def test_all_blog_posts_mock(self, mock_get_blog_data, mcp_server):
        """Test all_blog_posts returns JSON with all posts - MOCKED."""
        # Mock the blog data
        mock_get_blog_data.return_value = {
            "url_info": {
                "/42": {
                    "title": "What I wish I knew at 42",
                    "description": "Life lessons",
                    "last_modified": "2024-01-01T00:00:00Z",
                    "doc_size": 5000,
                    "markdown_path": "_d/42.md",
                    "file_path": "_site/42.html",
                    "redirect_url": ""
                },
                "/python": {
                    "title": "Python Tips",
                    "description": "Python best practices",
                    "last_modified": "2024-01-02T00:00:00Z",
                    "doc_size": 3000,
                    "markdown_path": "_posts/python.md",
                    "file_path": "_site/python.html",
                    "redirect_url": ""
                }
            }
        }

        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("all_blog_posts", {})

            # Should return valid JSON
            data = json.loads(content)

            # Check structure
            assert "count" in data
            assert "posts" in data
            assert isinstance(data["posts"], list)
            assert data["count"] == 2  # We mocked 2 posts

            # Check first post structure
            if data["posts"]:
                post = data["posts"][0]
                required_fields = ["title", "url", "description", "last_modified", "doc_size", "markdown_path", "file_path", "redirect_url"]
                for field in required_fields:
                    assert field in post, f"Missing field: {field}"

    @patch('blog_mcp_server.get_blog_data')
    async def test_blog_search_json_format_mock(self, mock_get_blog_data, mcp_server):
        """Test blog_search returns proper JSON format - MOCKED."""
        # Mock the blog data with posts containing "the" in title/description
        mock_get_blog_data.return_value = {
            "url_info": {
                "/the-post": {
                    "title": "The Ultimate Guide",
                    "description": "Everything about the topic",
                    "last_modified": "2024-01-01T00:00:00Z",
                    "doc_size": 5000,
                    "markdown_path": "_d/the-post.md",
                    "file_path": "_site/the-post.html",
                    "redirect_url": "",
                    "incoming_links": [],
                    "outgoing_links": []
                },
                "/another": {
                    "title": "Another Post with the Word",
                    "description": "More about the subject",
                    "last_modified": "2024-01-02T00:00:00Z",
                    "doc_size": 3000,
                    "markdown_path": "_d/another.md",
                    "file_path": "_site/another.html",
                    "redirect_url": "",
                    "incoming_links": [],
                    "outgoing_links": []
                }
            }
        }

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
            "all_blog_posts",
            "get_recent_changes"
        ]

        for tool_name in expected_tools:
            assert hasattr(blog_mcp_server, tool_name)
            tool = getattr(blog_mcp_server, tool_name)
            assert tool.__class__.__name__ == "FunctionTool"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])