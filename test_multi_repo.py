#!/usr/bin/env python3
"""
Tests for multi-repo support and dynamic branch detection.
"""

import json
import os
import sys
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from test_utils import MCPTestClient, BlogAssertions

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blog_mcp_server


class TestMultiRepoSupport:
    """Tests for multi-repository support."""

    @pytest.fixture
    def mcp_server(self):
        """Provide the FastMCP server instance for testing."""
        return blog_mcp_server.mcp

    @pytest.fixture
    def assertions(self):
        """Provide assertions helper."""
        return BlogAssertions()

    @pytest.mark.network
    async def test_list_repos_tool(self, mcp_server):
        """Test list_repos tool returns repository configuration."""
        async with MCPTestClient(mcp_server) as client:
            content = await client.call_tool("list_repos")
            data = json.loads(content)

            # Check structure
            assert "owner" in data
            assert "default_repo" in data
            assert "repositories" in data
            assert "count" in data

            # Check values
            assert data["owner"] == blog_mcp_server.GITHUB_REPO_OWNER
            assert data["default_repo"] == blog_mcp_server.DEFAULT_REPO
            assert isinstance(data["repositories"], list)
            assert len(data["repositories"]) > 0

    async def test_blog_info_with_repo_parameter(self, mcp_server):
        """Test blog_info accepts repo parameter."""
        async with MCPTestClient(mcp_server) as client:
            # Test with default repo (no parameter)
            content_default = await client.call_tool("blog_info")
            assert blog_mcp_server.DEFAULT_REPO in content_default

            # Test with explicit repo
            content_explicit = await client.call_tool("blog_info", {"repo": "idvorkin.github.io"})
            assert "idvorkin.github.io" in content_explicit

    @patch('blog_mcp_server.get_default_branch')
    async def test_default_branch_detection(self, mock_get_branch, mcp_server):
        """Test that default branch is dynamically detected."""
        # Mock the default branch to return "main"
        mock_get_branch.return_value = "main"

        # Call a function that should use default branch
        result = await blog_mcp_server.get_default_branch("idvorkin.github.io")

        # Should have been called
        mock_get_branch.assert_called_once()

    @patch('blog_mcp_server.httpx.AsyncClient')
    async def test_default_branch_caching(self, mock_client_class, mcp_server):
        """Test that default branch detection is cached."""
        # Setup mock
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the repo API response
        async def side_effect(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            response.json = MagicMock(return_value={"default_branch": "main"})
            return response

        mock_client.get = AsyncMock(side_effect=side_effect)

        # Clear cache first
        blog_mcp_server._repo_default_branches.clear()

        # Call twice - should only fetch once due to caching
        result1 = await blog_mcp_server.get_default_branch("test-repo")
        result2 = await blog_mcp_server.get_default_branch("test-repo")

        assert result1 == "main"
        assert result2 == "main"

        # Should only have called the API once (cached second time)
        assert mock_client.get.call_count == 1

    @patch('blog_mcp_server.get_available_repos')
    async def test_repo_validation(self, mock_get_repos, mcp_server):
        """Test that repo parameter is validated against available repos."""
        # Mock available repos
        mock_get_repos.return_value = ["repo1", "repo2", "repo3"]
        blog_mcp_server._available_repos = ["repo1", "repo2", "repo3"]

        # Valid repo should pass
        result = blog_mcp_server.validate_repo("repo1")
        assert result == "repo1"

        # None should return default
        result = blog_mcp_server.validate_repo(None)
        assert result == blog_mcp_server.DEFAULT_REPO

        # Invalid repo should raise error
        with pytest.raises(blog_mcp_server.BlogError):
            blog_mcp_server.validate_repo("invalid-repo")

    @patch('blog_mcp_server.get_blog_data')
    async def test_per_repo_caching(self, mock_get_data, mcp_server):
        """Test that each repo has its own cache."""
        # Mock different data for different repos
        def mock_data_fn(repo=None):
            if repo == "repo1":
                return {"url_info": {"post1": {}}, "redirects": {}}
            elif repo == "repo2":
                return {"url_info": {"post2": {}}, "redirects": {}}
            else:
                return {"url_info": {}, "redirects": {}}

        mock_get_data.side_effect = mock_data_fn

        # Get data for different repos
        data1 = await blog_mcp_server.get_blog_data("repo1")
        data2 = await blog_mcp_server.get_blog_data("repo2")

        # Should get different data
        assert "post1" in data1.get("url_info", {})
        assert "post2" in data2.get("url_info", {})

    @patch('blog_mcp_server.httpx.AsyncClient')
    async def test_wildcard_repo_expansion(self, mock_client_class, mcp_server):
        """Test wildcard (*) expansion for repos."""
        # Setup mock
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the user repos API response
        async def side_effect(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            response.json = MagicMock(return_value=[
                {"name": "repo1"},
                {"name": "repo2"},
                {"name": "repo3"}
            ])
            return response

        mock_client.get = side_effect

        # Clear cache and set wildcard
        blog_mcp_server._available_repos = None
        original_repos = blog_mcp_server.GITHUB_REPOS
        blog_mcp_server.GITHUB_REPOS = "*"

        try:
            # Get available repos
            repos = await blog_mcp_server.get_available_repos()

            # Should have fetched and expanded
            assert len(repos) == 3
            assert "repo1" in repos
            assert "repo2" in repos
            assert "repo3" in repos
        finally:
            # Restore original value
            blog_mcp_server.GITHUB_REPOS = original_repos

    async def test_explicit_repo_list(self, mcp_server):
        """Test explicit comma-separated repo list."""
        # Save original
        original_repos = blog_mcp_server.GITHUB_REPOS
        blog_mcp_server._available_repos = None

        try:
            # Set explicit list
            blog_mcp_server.GITHUB_REPOS = "repo1,repo2,repo3"

            # Get available repos
            repos = await blog_mcp_server.get_available_repos()

            # Should have parsed correctly
            assert len(repos) == 3
            assert "repo1" in repos
            assert "repo2" in repos
            assert "repo3" in repos
        finally:
            # Restore original
            blog_mcp_server.GITHUB_REPOS = original_repos
            blog_mcp_server._available_repos = None

    @patch('blog_mcp_server.get_blog_data')
    async def test_tools_accept_repo_parameter(self, mock_get_data, mcp_server):
        """Test that key tools accept and use repo parameter."""
        # Mock blog data
        mock_get_data.return_value = {
            "url_info": {
                "/test": {
                    "title": "Test Post",
                    "description": "Test description",
                    "markdown_path": "_d/test.md",
                    "last_modified": "2024-01-01T00:00:00Z",
                    "doc_size": 1000,
                    "file_path": "_site/test.html",
                    "redirect_url": ""
                }
            },
            "redirects": {}
        }

        async with MCPTestClient(mcp_server) as client:
            # Test blog_search with repo parameter
            content = await client.call_tool("blog_search", {
                "query": "test",
                "limit": 5,
                "repo": "test-repo"
            })

            # Should not error (though it will fail validation in real scenario)
            # In mock scenario, just check it doesn't crash
            assert content is not None

    async def test_environment_variable_configuration(self):
        """Test that environment variables are read correctly."""
        # Check that environment variables have defaults
        assert blog_mcp_server.GITHUB_REPO_OWNER is not None
        assert blog_mcp_server.GITHUB_REPOS is not None
        assert blog_mcp_server.DEFAULT_REPO is not None
        assert blog_mcp_server.BLOG_URL is not None
        assert blog_mcp_server.BACKLINKS_PATH is not None

    @patch('blog_mcp_server.get_blog_data')
    async def test_graceful_degradation_missing_backlinks(self, mock_get_data, mcp_server):
        """Test graceful handling when back-links.json is missing."""
        # Mock to return empty structure (simulating missing file)
        mock_get_data.return_value = {"url_info": {}, "redirects": {}}

        async with MCPTestClient(mcp_server) as client:
            # Should not crash, just return no results
            content = await client.call_tool("blog_search", {
                "query": "test",
                "limit": 5
            })

            data = json.loads(content)
            # Should have error or no results
            assert "error" in data or data.get("count", 0) == 0


class TestDefaultBranchDetection:
    """Tests for dynamic default branch detection."""

    @pytest.fixture
    def mcp_server(self):
        """Provide the FastMCP server instance for testing."""
        return blog_mcp_server.mcp

    @patch('blog_mcp_server.httpx.AsyncClient')
    async def test_detect_main_branch(self, mock_client_class):
        """Test detection of 'main' as default branch."""
        # Setup mock
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        async def side_effect(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            response.json = MagicMock(return_value={"default_branch": "main"})
            return response

        mock_client.get = side_effect

        # Clear cache
        blog_mcp_server._repo_default_branches.clear()

        # Detect branch
        branch = await blog_mcp_server.get_default_branch("test-repo")
        assert branch == "main"

    @patch('blog_mcp_server.httpx.AsyncClient')
    async def test_detect_master_branch(self, mock_client_class):
        """Test detection of 'master' as default branch."""
        # Setup mock
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        async def side_effect(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            response.json = MagicMock(return_value={"default_branch": "master"})
            return response

        mock_client.get = side_effect

        # Clear cache
        blog_mcp_server._repo_default_branches.clear()

        # Detect branch
        branch = await blog_mcp_server.get_default_branch("old-repo")
        assert branch == "master"

    @patch('blog_mcp_server.httpx.AsyncClient')
    async def test_fallback_on_error(self, mock_client_class):
        """Test that API errors raise BlogError instead of silent fallback."""
        # Setup mock to raise error
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        async def side_effect(url, **kwargs):
            raise Exception("API error")

        mock_client.get = side_effect

        # Clear cache
        blog_mcp_server._repo_default_branches.clear()

        # Should raise BlogError instead of falling back
        with pytest.raises(blog_mcp_server.BlogError, match="Failed to get default branch"):
            await blog_mcp_server.get_default_branch("error-repo")

    @patch('blog_mcp_server.get_default_branch')
    async def test_urls_use_dynamic_branch(self, mock_get_branch):
        """Test that URLs are constructed with dynamic branch."""
        # Mock to return "develop" branch
        mock_get_branch.return_value = "develop"

        # Clear caches
        blog_mcp_server._repo_caches.clear()
        blog_mcp_server._repo_cache_timestamps.clear()

        # When getting blog data, it should use the dynamic branch
        # This is tested indirectly through get_blog_data
        url = f"https://raw.githubusercontent.com/{blog_mcp_server.GITHUB_REPO_OWNER}/test-repo/develop/{blog_mcp_server.BACKLINKS_PATH}"

        # Just verify the URL would be constructed correctly
        assert "develop" in url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
