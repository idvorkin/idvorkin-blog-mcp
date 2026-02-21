#!/usr/bin/env python3
"""
E2E tests for the Blog MCP Server against deployed endpoints.

Tests against live endpoints (local or production) without mocking.
Use MCP_SERVER_ENDPOINT environment variable to specify the endpoint.
"""

import json
import os

import pytest
from test_utils import MCPTestClient

# Server endpoints
LOCAL_ENDPOINT = "http://localhost:9000/mcp"
PRODUCTION_ENDPOINT = "https://idvorkin-blog-and-repo.fastmcp.app/mcp"


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

    async def test_server_connectivity(self, server_endpoint: str):
        """Test that server responds to ping."""
        async with MCPTestClient(server_endpoint) as client:
            await client.ping()

    async def test_list_tools(self, server_endpoint: str):
        """Test that all expected tools are available."""
        expected_tools = {
            "list_repos",
            "blog_info",
            "random_blog",
            "read_blog_post",
            "random_blog_url",
            "blog_search",
            "recent_blog_posts",
            "all_blog_posts",
            "get_recent_changes",
            "list_open_prs",
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

    async def test_blog_search_tool(self, server_endpoint: str):
        """Test blog_search tool with common terms."""
        async with MCPTestClient(server_endpoint) as client:
            # "the" is extremely common — must always return results
            content = await client.call_tool("blog_search", {"query": "the", "limit": 3})
            data = json.loads(content)

            assert "query" in data
            assert "count" in data
            assert "posts" in data
            assert data["query"] == "the"
            assert data["count"] > 0, "Common query 'the' should always return results"

            for post in data["posts"]:
                assert "title" in post
                assert "url" in post
                assert post["url"].startswith("https://idvork.in/")

    async def test_blog_search_empty_query(self, server_endpoint: str, assertions):
        """Test blog_search with empty query returns error."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("blog_search", {"query": "", "limit": 5})
            assertions.assert_error_message(content, "Search query is required and must be a non-empty string")

    async def test_blog_search_limit_parameter(self, server_endpoint: str):
        """Test blog_search respects limit parameter."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("blog_search", {"query": "the", "limit": 2})
            data = json.loads(content)
            assert data["count"] > 0, "Common query 'the' should return results"
            assert len(data["posts"]) <= 2, f"Limit not respected: found {len(data['posts'])} results"

    async def test_read_blog_post_valid_url(self, server_endpoint: str):
        """Test read_blog_post with valid URL returns blog content."""
        async with MCPTestClient(server_endpoint) as client:
            url = "https://idvork.in/42"
            content = await client.call_tool("read_blog_post", {"url": url})

            assert not content.startswith("Error:"), f"Got error for valid URL {url}: {content}"
            assert "Title:" in content or "title:" in content, f"Missing title in response for {url}"
            assert "URL:" in content or "url:" in content, f"Missing URL in response for {url}"
            assert len(content) > 100, f"Content too short for {url}: {len(content)} chars"
            assert url in content, f"URL {url} not found in response"

    async def test_read_blog_post_with_redirect(self, server_endpoint: str):
        """Test read_blog_post with redirect URLs."""
        async with MCPTestClient(server_endpoint) as client:
            # Test redirect URL - /fortytwo redirects to /42
            content = await client.call_tool("read_blog_post", {"url": "/fortytwo"})

            # Should get the /42 post via redirect
            assert not content.startswith("Error:"), f"Got error for redirect URL: {content}"
            assert ("redirect" in content.lower() or "42" in content), "Should indicate redirect or show /42 content"
            assert len(content) > 100, "Should have substantial content"

    async def test_read_blog_post_with_markdown_path(self, server_endpoint: str):
        """Test read_blog_post with various markdown file path formats."""
        markdown_paths = [
            "_d/42.md",  # Standard path
            "/_d/42.md",  # With leading slash
            "42.md",  # Just filename
            "/42.md",  # Filename with leading slash
        ]

        async with MCPTestClient(server_endpoint) as client:
            for md_path in markdown_paths:
                content = await client.call_tool("read_blog_post", {"url": md_path})

                # Should successfully find the post
                assert not content.startswith("Error:"), f"Got error for markdown path '{md_path}': {content[:200]}"
                assert "42" in content or "forty" in content.lower(), f"Should find the 42 post for path '{md_path}'"
                assert len(content) > 100, f"Should have substantial content for path '{md_path}'"

    async def test_read_blog_post_all_formats(self, server_endpoint: str):
        """Test read_blog_post with all supported URL/path formats."""
        test_formats = [
            # Path formats
            ("42", "bare path"),
            ("/42", "absolute path"),

            # URL formats
            ("https://idvork.in/42", "full HTTPS URL"),
            ("http://idvork.in/42", "full HTTP URL"),

            # Markdown path formats
            ("_d/42.md", "standard markdown path"),
            ("/_d/42.md", "absolute markdown path"),
            ("42.md", "bare filename"),
            ("/42.md", "absolute filename"),

            # Redirect paths
            ("/fortytwo", "redirect path"),
            ("fortytwo", "bare redirect path"),
        ]

        async with MCPTestClient(server_endpoint) as client:
            for path, description in test_formats:
                content = await client.call_tool("read_blog_post", {"url": path})
                assert not content.startswith("Error:"), f"Failed for {description} '{path}': {content[:200]}"
                assert len(content) > 100, f"No content for {description} '{path}'"
                # All should resolve to the same post about 42
                assert ("42" in content or "forty" in content.lower()), f"Wrong post for {description} '{path}'"

    async def test_read_blog_post_invalid_url(self, server_endpoint: str, assertions):
        """Test read_blog_post with invalid URL."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("read_blog_post", {"url": ""})
            assertions.assert_error_message(content, "Error: URL must be a non-empty string")

    async def test_read_blog_post_from_posts_directory(self, server_endpoint: str):
        """Test read_blog_post can access posts from _posts/ directory."""
        async with MCPTestClient(server_endpoint) as client:
            # Test a post from _posts/ directory
            test_posts = [
                "_posts/2018-01-04-7-habits.md",
                "2018-01-04-7-habits.md",  # Just filename
                "/7-habits",  # URL path
            ]

            for post_path in test_posts:
                content = await client.call_tool("read_blog_post", {"url": post_path})
                # At least one should work
                if not content.startswith("Error:"):
                    assert "habit" in content.lower() or "7" in content, f"Should find 7 habits post for {post_path}"
                    assert len(content) > 100, f"Should have content for {post_path}"
                    break
            else:
                pytest.fail("Could not access any _posts/ directory posts")

    async def test_all_blog_posts_includes_all_directories(self, server_endpoint: str):
        """Test all_blog_posts includes posts from _d/, _posts/, and td/ directories."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("all_blog_posts", {})

            data = json.loads(content)

            # Count posts from different directories
            d_posts = 0
            posts_posts = 0
            td_posts = 0

            for post in data.get("posts", []):
                markdown_path = post.get("markdown_path", "")
                if markdown_path.startswith("_d/"):
                    d_posts += 1
                elif markdown_path.startswith("_posts/"):
                    posts_posts += 1
                elif markdown_path.startswith("td/"):
                    td_posts += 1

            # Should have posts from at least _d/ and _posts/
            assert d_posts > 0, "Should have posts from _d/ directory"
            assert posts_posts > 0, "Should have posts from _posts/ directory"
            # td/ might be empty, so we don't assert on it

            # Total should be more than just _d/ posts
            assert data["count"] > 200, f"Should have more than 200 posts total, got {data['count']}"

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

    async def test_recent_blog_posts_e2e(self, server_endpoint: str):
        """Test recent_blog_posts function against live endpoint."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("recent_blog_posts", {"limit": 5})

            data = json.loads(content)

            # Check structure
            assert "count" in data
            assert "limit" in data
            assert "posts" in data
            assert isinstance(data["posts"], list)
            assert data["limit"] == 5
            assert data["count"] <= 5

            # Live endpoint should always have posts
            assert len(data["posts"]) > 0, "Expected at least one recent post"
            post = data["posts"][0]
            required_fields = ["title", "url", "description", "last_modified", "doc_size", "markdown_path", "file_path", "redirect_url"]
            for field in required_fields:
                assert field in post, f"Missing field: {field}"

            # Verify URL format
            assert post["url"].startswith("https://idvork.in/")

            # Verify markdown path is from a valid directory
            assert any(
                post["markdown_path"].startswith(d) for d in ("_d/", "_posts/", "td/")
            ), f"Unexpected markdown_path prefix: {post['markdown_path']}"
            assert post["markdown_path"].endswith(".md")

    async def test_all_blog_posts_e2e(self, server_endpoint: str):
        """Test all_blog_posts function against live endpoint."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("all_blog_posts", {})

            data = json.loads(content)

            # Check structure
            assert "count" in data
            assert "posts" in data
            assert isinstance(data["posts"], list)
            assert data["count"] > 0  # Should have some posts

            # Check first post structure
            assert len(data["posts"]) > 0, "Expected at least one post"
            post = data["posts"][0]
            required_fields = ["title", "url", "description", "last_modified", "doc_size", "markdown_path", "file_path", "redirect_url"]
            for field in required_fields:
                assert field in post, f"Missing field: {field}"

            # Verify URL format
            assert post["url"].startswith("https://idvork.in/")

            # Verify markdown path is from a valid directory
            assert any(
                post["markdown_path"].startswith(d) for d in ("_d/", "_posts/", "td/")
            ), f"Unexpected markdown_path prefix: {post['markdown_path']}"
            assert post["markdown_path"].endswith(".md")

    async def test_blog_search_json_e2e(self, server_endpoint: str):
        """Test blog_search JSON format against live endpoint."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("blog_search", {
                "query": "the",  # Very common word that should match posts
                "limit": 3
            })

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
                assert data["limit"] == 3
                assert data["count"] <= 3

                # If posts exist, check structure
                if data["posts"]:
                    post = data["posts"][0]
                    required_fields = ["title", "url", "description", "last_modified", "doc_size", "markdown_path", "file_path", "redirect_url"]
                    for field in required_fields:
                        assert field in post, f"Missing field: {field}"

                    # Verify URL format
                    assert post["url"].startswith("https://idvork.in/")

                    # Verify markdown path is from a valid directory
                    assert any(
                        post["markdown_path"].startswith(d) for d in ("_d/", "_posts/", "td/")
                    ), f"Unexpected markdown_path prefix: {post['markdown_path']}"
                    assert post["markdown_path"].endswith(".md")

    async def test_get_recent_changes_default(self, server_endpoint: str):
        """Test get_recent_changes with default parameters."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("get_recent_changes", {})

            # Should return recent changes
            assert "Recent changes" in content, "Should have header"
            assert "Commit:" in content or "No commits found" in content, "Should have commits or no commits message"

            # If we have commits, verify structure
            if "Commit:" in content:
                assert "Author:" in content, "Should have author info"
                assert "Message:" in content, "Should have commit message"
                # Should have relative time like "2 days ago"
                assert "ago" in content, "Should have relative time"

    async def test_get_recent_changes_with_commits_limit(self, server_endpoint: str):
        """Test get_recent_changes with specific number of commits."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("get_recent_changes", {"commits": 3})

            # Should mention the number of commits
            assert "Recent changes (last" in content, "Should specify number of commits"
            assert not content.startswith("Error:"), "Should not be an error"

            # Count number of commits returned (each starts with "Commit:")
            if "Commit:" in content:
                commit_count = content.count("Commit:")
                assert commit_count <= 3, f"Should return at most 3 commits, got {commit_count}"

    async def test_get_recent_changes_with_days(self, server_endpoint: str):
        """Test get_recent_changes with days parameter."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("get_recent_changes", {"days": 30})

            # Should mention last N days
            assert "Recent changes (last 30 days)" in content or "No commits found" in content
            assert not content.startswith("Error:"), "Should not be an error"

    async def test_get_recent_changes_with_path_filter(self, server_endpoint: str):
        """Test get_recent_changes with path filter."""
        async with MCPTestClient(server_endpoint) as client:
            # Test with _d/ path filter
            content = await client.call_tool("get_recent_changes", {
                "path": "_d/",
                "commits": 5
            })

            # Should return changes or indicate no commits found
            assert "Recent changes" in content or "No commits found" in content

            # If we have file changes, they should all be in _d/
            if "Files changed:" in content:
                # Extract lines with file paths (start with "  - ")
                file_lines = [line for line in content.split("\n") if line.strip().startswith("- ")]
                for line in file_lines:
                    # File paths should start with _d/
                    if ".md" in line:  # Only check markdown files
                        assert "_d/" in line, f"File should be in _d/ directory: {line}"

    async def test_get_recent_changes_invalid_params(self, server_endpoint: str):
        """Test get_recent_changes with invalid parameter combinations."""
        async with MCPTestClient(server_endpoint) as client:
            # Test both days and commits specified (mutually exclusive)
            content = await client.call_tool("get_recent_changes", {
                "days": 7,
                "commits": 10
            })
            assert "Cannot specify both 'days' and 'commits'" in content, "Should reject both params"

            # Test negative days
            content = await client.call_tool("get_recent_changes", {"days": -1})
            assert "'days' must be a positive number" in content, "Should reject negative days"

            # Test negative commits
            content = await client.call_tool("get_recent_changes", {"commits": -5})
            assert "'commits' must be a positive number" in content, "Should reject negative commits"

    async def test_get_recent_changes_with_diff(self, server_endpoint: str):
        """Test get_recent_changes with include_diff enabled."""
        async with MCPTestClient(server_endpoint) as client:
            # Test with directory path should fail
            content = await client.call_tool("get_recent_changes", {
                "commits": 2,
                "include_diff": True,
                "path": "_d/"
            })
            assert "When include_diff is true, path must be a specific file" in content, "Should reject directory with include_diff"

            # Test with specific file should work
            content = await client.call_tool("get_recent_changes", {
                "commits": 2,
                "include_diff": True,
                "path": "_d/ai-thoughts.md"
            })
            # Should return changes (or no commits found for that file)
            assert ("Recent changes" in content or "No commits found" in content), "Should have valid response"
            assert not content.startswith("Error:"), "Should not be an error"

            # If there are file changes with diffs available, should see diff content
            if "Files changed:" in content and "Diff:" in content:
                # Should have diff indicators like @@ or +/- lines
                assert ("@@" in content or "+" in content or "-" in content), "Should have diff content"

    async def test_list_open_prs_e2e(self, server_endpoint: str):
        """Test list_open_prs against live endpoint."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("list_open_prs", {"since_days": 7})

            data = json.loads(content)

            # Check required top-level fields
            assert "count" in data, "Missing 'count' field"
            assert "since_days" in data, "Missing 'since_days' field"
            assert "pull_requests" in data, "Missing 'pull_requests' field"
            assert isinstance(data["pull_requests"], list), "'pull_requests' must be a list"
            assert data["since_days"] == 7, "since_days should be 7"
            assert data["count"] == len(data["pull_requests"]), "count should match length of pull_requests"

            # If there are PRs, verify structure
            if data["pull_requests"]:
                pr = data["pull_requests"][0]
                required_fields = ["repo", "number", "title", "author", "state", "created_at", "updated_at", "url"]
                for field in required_fields:
                    assert field in pr, f"Missing field '{field}' in PR"
                assert pr["state"] == "open", "All returned PRs should be open"
                assert pr["url"].startswith("https://github.com/"), "PR URL should be a GitHub URL"

    async def test_list_repos_e2e(self, server_endpoint: str):
        """Test list_repos tool returns valid repository data."""
        async with MCPTestClient(server_endpoint) as client:
            content = await client.call_tool("list_repos")
            data = json.loads(content)

            # Check required top-level fields
            assert "owner" in data, "Missing 'owner' field"
            assert "default_repo" in data, "Missing 'default_repo' field"
            assert "repositories" in data, "Missing 'repositories' field"
            assert "pagination" in data, "Missing 'pagination' field"

            # Verify values
            assert isinstance(data["repositories"], list)
            assert data["pagination"]["total_count"] > 0, "Should have at least one repository"
            assert len(data["repositories"]) > 0

    async def test_get_recent_changes_performance(self, server_endpoint: str):
        """Test get_recent_changes handles parallel requests efficiently."""
        import time

        async with MCPTestClient(server_endpoint) as client:
            # Time fetching 10 commits (should use parallel requests)
            start_time = time.time()
            content = await client.call_tool("get_recent_changes", {"commits": 10})
            elapsed_time = time.time() - start_time

            # Should complete reasonably quickly (under 10 seconds even with network latency)
            assert elapsed_time < 10, f"Should complete within 10 seconds, took {elapsed_time:.2f}s"
            assert "Recent changes" in content, "Should return valid response"


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
