#!/usr/bin/env python3
"""
Blog MCP Server

A FastMCP server that provides tools for interacting with Igor's blog at idvork.in.

Multi-Repository Support:
- Supports multiple repositories via GITHUB_REPOS environment variable
- Wildcard support (*) to access all repos under GITHUB_REPO_OWNER
- Dynamic default branch detection (main/master)
- Per-repository caching with 5-minute TTL

This server offers nine tools:
- list_repos: List all available repositories
- blog_info: Get information about the blog
- random_blog: Get a random blog post
- read_blog_post: Read a specific blog post by URL
- random_blog_url: Get a random blog post URL
- blog_search: Search blog posts (returns JSON)
- recent_blog_posts: Get the most recent blog posts (returns JSON)
- all_blog_posts: Get all blog posts (returns JSON)
- get_recent_changes: Get recent changes/commits from the GitHub repository
"""

import asyncio
import json
import logging
import os
import random
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Environment Configuration
# ============================================================================
# GITHUB_REPO_OWNER: GitHub user/org name (default: "idvorkin")
#   Example: GITHUB_REPO_OWNER="myorg"
#
# GITHUB_REPOS: Repository specification (default: "idvorkin.github.io")
#   - Single repo: "idvorkin.github.io"
#   - Multiple repos: "repo1,repo2,repo3" (comma-separated, whitespace trimmed)
#   - All user repos: "*" (fetches all public repos via GitHub API)
#   Example: GITHUB_REPOS="blog,docs,wiki" or GITHUB_REPOS="*"
#
# DEFAULT_REPO: Fallback repo when none specified (default: "idvorkin.github.io")
#   Must be included in GITHUB_REPOS list
#   Example: DEFAULT_REPO="blog"
#
# BLOG_URL: Public blog URL (default: "https://idvork.in")
#   Used for generating blog post URLs in responses
#   Example: BLOG_URL="https://myblog.com"
#
# BACKLINKS_PATH: Path to back-links.json in repo (default: "back-links.json")
#   Relative path from repository root
#   Example: BACKLINKS_PATH="data/back-links.json"
# ============================================================================

GITHUB_REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "idvorkin")
GITHUB_REPOS = os.getenv("GITHUB_REPOS", "idvorkin.github.io")
DEFAULT_REPO = os.getenv("DEFAULT_REPO", "idvorkin.github.io")
BLOG_URL = os.getenv("BLOG_URL", "https://idvork.in")
BACKLINKS_PATH = os.getenv("BACKLINKS_PATH", "back-links.json")

# ============================================================================
# Multi-Repo Caching Architecture
# ============================================================================
# _available_repos: Cached list of available repositories (loaded once)
#   - None until first load
#   - Populated from GITHUB_REPOS (explicit list or wildcard expansion)
#
# _repo_default_branches: Maps repo name -> default branch name (e.g., "main" or "master")
#   - Cached for lifetime of server (no TTL)
#   - Server restart required if repository changes default branch
#
# _repo_caches: Maps repo name -> parsed back-links.json data
#   - Contains url_info and redirects for each repository
#   - Refreshed after CACHE_DURATION expires
#
# _repo_cache_timestamps: Maps repo name -> last fetch timestamp (unix time)
#   - Used to determine cache freshness
#
# CACHE_DURATION: Time-to-live for back-links cache (300s = 5 minutes)
#   - Fresh cache served within this window
#   - After expiry, fetch attempted; falls back to expired cache on failure
#   - No maximum age limit for expired cache fallback
# ============================================================================

_available_repos: Optional[list[str]] = None
_repo_default_branches: dict[str, str] = {}
_repo_caches: dict[str, dict] = {}
_repo_cache_timestamps: dict[str, float] = {}
CACHE_DURATION = 300  # 5 minutes

# Server configuration
mcp = FastMCP("blog-mcp-server")


class BlogError(Exception):
    """Base exception for blog operations."""

    pass


async def get_available_repos() -> list[str]:
    """Get list of available repositories based on configuration."""
    global _available_repos

    if _available_repos is not None:
        return _available_repos

    if GITHUB_REPOS == "*":
        # Fetch all repos for the user (with pagination support)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"https://api.github.com/users/{GITHUB_REPO_OWNER}/repos"
                # Set per_page=100 to reduce API calls (GitHub default is 30, max is 100)
                response = await client.get(url, params={"per_page": 100})
                response.raise_for_status()
                repos_data = response.json()
                _available_repos = [repo["name"] for repo in repos_data]
                logger.info(f"Loaded {len(_available_repos)} repositories for {GITHUB_REPO_OWNER}")
                return _available_repos
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching repositories for {GITHUB_REPO_OWNER}: {e.response.status_code}")
            if e.response.status_code == 404:
                raise BlogError(
                    f"GitHub user '{GITHUB_REPO_OWNER}' not found. "
                    f"Check GITHUB_REPO_OWNER environment variable."
                )
            elif e.response.status_code == 403:
                raise BlogError(
                    f"GitHub API rate limit exceeded or access forbidden for user '{GITHUB_REPO_OWNER}'. "
                    f"Try again later or use explicit repo list instead of wildcard."
                )
            else:
                raise BlogError(f"Failed to fetch repositories from GitHub API: HTTP {e.response.status_code}")
        except httpx.TimeoutException:
            logger.error(f"Timeout fetching repositories for {GITHUB_REPO_OWNER}")
            raise BlogError(
                f"Timeout connecting to GitHub API to fetch repositories. "
                f"Check network connectivity or use explicit repo list."
            )
        except Exception as e:
            logger.error(f"Unexpected error fetching repositories for {GITHUB_REPO_OWNER}: {e}")
            raise BlogError(f"Failed to fetch repository list: {str(e)}")
    else:
        # Parse comma-separated list
        _available_repos = [repo.strip() for repo in GITHUB_REPOS.split(",")]
        return _available_repos


def validate_repo(repo: Optional[str]) -> str:
    """Validate and return the repo name, using default if not specified.

    Note: This is a synchronous function that validates against cached repository list.
    If repositories haven't been initialized yet, validation is skipped to allow
    bootstrap. This means the first calls may use invalid repos before initialization
    completes, but they will fail later when actually fetching data.
    """
    if repo is None:
        return DEFAULT_REPO

    # If repos haven't been loaded yet, allow any repo
    # (will be validated when actually used in async context)
    if _available_repos is None:
        logger.warning(
            f"Repository validation called before initialization for '{repo}', "
            f"allowing without validation"
        )
        return repo

    if repo not in _available_repos:
        available_list = ', '.join(_available_repos)
        raise BlogError(
            f"Repository '{repo}' not found in configured repositories. "
            f"Available repositories: {available_list}. "
            f"Use list_repos tool to see available repositories or check GITHUB_REPOS environment variable."
        )

    return repo


async def get_default_branch(repo: str) -> str:
    """Get the default branch for a repository (cached).

    Note: This cache persists for the lifetime of the server. If a repository
    changes its default branch, the server must be restarted to pick up the change.
    """
    global _repo_default_branches

    if repo in _repo_default_branches:
        return _repo_default_branches[repo]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{repo}"
            response = await client.get(url)
            response.raise_for_status()
            repo_data = response.json()
            default_branch = repo_data.get("default_branch", "main")
            _repo_default_branches[repo] = default_branch
            logger.info(f"Default branch for {GITHUB_REPO_OWNER}/{repo}: {default_branch}")
            return default_branch
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching default branch for {repo}: {e.response.status_code}")
        if e.response.status_code == 404:
            raise BlogError(
                f"Repository '{GITHUB_REPO_OWNER}/{repo}' not found. "
                f"Check repository name or use list_repos tool to see available repositories."
            )
        elif e.response.status_code == 403:
            raise BlogError(
                f"Access forbidden to repository '{GITHUB_REPO_OWNER}/{repo}'. "
                f"Check permissions or API rate limit."
            )
        else:
            raise BlogError(f"Failed to get repository info: HTTP {e.response.status_code}")
    except httpx.TimeoutException:
        logger.error(f"Timeout fetching default branch for {repo}")
        raise BlogError(
            f"Timeout fetching repository '{repo}' information. "
            f"Check network connectivity."
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching default branch for {repo}: {e}")
        raise BlogError(f"Failed to get default branch for repository '{repo}': {str(e)}")


async def fetch_url(url: str) -> str:
    """Fetch content from a URL."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()

            # Limit response size to prevent memory issues
            # 1MB limit chosen as blog posts should be <100KB; anything larger is likely binary/corrupt
            content = response.text
            if len(content) > 1_000_000:
                logger.warning(
                    f"Content from {url} is very large ({len(content)} chars), truncating to 1MB"
                )
                content = content[:1_000_000]

            return content
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
            raise BlogError(f"Failed to fetch {url}: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            raise BlogError(f"Unexpected error fetching {url}: {e}") from e


async def get_blog_data(repo: Optional[str] = None) -> dict:
    """Get cached blog data from back-links.json file for a specific repository.

    Cache behavior:
    - Fresh data cached for 5 minutes (CACHE_DURATION)
    - On fetch failure, expired cache is used if available (no max age limit)
    - If no cache exists and fetch fails, error is raised
    """
    global _repo_caches, _repo_cache_timestamps

    repo = validate_repo(repo)
    current_time = time.time()

    # Return cached data if still valid
    if repo in _repo_caches and (current_time - _repo_cache_timestamps.get(repo, 0)) < CACHE_DURATION:
        return _repo_caches[repo]

    try:
        # Get default branch for this repo
        default_branch = await get_default_branch(repo)

        # Construct backlinks URL
        backlinks_url = f"https://raw.githubusercontent.com/{GITHUB_REPO_OWNER}/{repo}/{default_branch}/{BACKLINKS_PATH}"

        logger.info(f"Fetching fresh blog data from {backlinks_url}")
        content = await fetch_url(backlinks_url)
        _repo_caches[repo] = json.loads(content)
        _repo_cache_timestamps[repo] = current_time

        logger.info(f"Cached {len(_repo_caches[repo].get('url_info', {}))} blog entries for {repo}")
        return _repo_caches[repo]

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching back-links.json for {repo}: {e.response.status_code}")

        # Try expired cache first (resilience for transient failures)
        if repo in _repo_caches:
            logger.warning(f"Using expired cache for {repo} due to HTTP {e.response.status_code} error")
            return _repo_caches[repo]

        # No cache available - surface specific error
        if e.response.status_code == 404:
            raise BlogError(
                f"Blog data file not found for repository '{repo}'. "
                f"The repository may not have a '{BACKLINKS_PATH}' file on branch '{await get_default_branch(repo)}', "
                f"or the default branch detection failed."
            )
        elif e.response.status_code == 403:
            raise BlogError(
                f"Access forbidden to repository '{repo}'. "
                f"Check permissions or API rate limit."
            )
        else:
            raise BlogError(f"Failed to fetch blog data: HTTP {e.response.status_code}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in back-links.json for {repo}: {e}")
        if repo in _repo_caches:
            logger.warning(f"Using expired cache for {repo} due to JSON parse error")
            return _repo_caches[repo]
        raise BlogError(
            f"Invalid blog data format for repository '{repo}'. "
            f"The {BACKLINKS_PATH} file may be corrupted."
        )
    except BlogError:
        # Re-raise BlogErrors (from get_default_branch or fetch_url)
        # But try expired cache first
        if repo in _repo_caches:
            logger.warning(f"Using expired cache for {repo} due to error")
            return _repo_caches[repo]
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching back-links.json for {repo}: {e}")
        if repo in _repo_caches:
            logger.warning(f"Using expired cache for {repo} due to unexpected error: {e}")
            return _repo_caches[repo]
        raise BlogError(f"Failed to fetch blog data for repository '{repo}': {str(e)}")


async def get_blog_files(repo: Optional[str] = None) -> list[dict]:
    """Get all blog post files - optimized to use back-links.json.

    Blog post directories:
    - _d/: Main blog posts (Jekyll drafts/documents)
    - _posts/: Published Jekyll posts
    - td/: Technical documentation posts
    """
    try:
        # Note: get_blog_data validates repo, no need to validate here
        blog_data = await get_blog_data(repo)
        url_info = blog_data.get("url_info", {})

        # Get default branch for constructing URLs
        repo_name = repo if repo else DEFAULT_REPO
        default_branch = await get_default_branch(repo_name)

        blog_files = []
        for url, info in url_info.items():
            markdown_path = info.get("markdown_path", "")
            if not markdown_path:
                continue

            # Filter to blog post directories only
            if not (markdown_path.startswith("_d/") or
                    markdown_path.startswith("_posts/") or
                    markdown_path.startswith("td/")):
                continue

            # Convert back-links format to old blog files format for compatibility
            blog_file = {
                "name": markdown_path.split("/")[-1] if "/" in markdown_path else markdown_path,
                "path": markdown_path,
                "download_url": f"https://raw.githubusercontent.com/{GITHUB_REPO_OWNER}/{repo_name}/{default_branch}/{markdown_path}",
                "html_url": f"{BLOG_URL}{url}",
            }
            blog_files.append(blog_file)

        logger.info(f"Found {len(blog_files)} blog files for {repo_name} (optimized)")
        return blog_files

    except BlogError:
        # Re-raise BlogErrors as-is (from get_blog_data or get_default_branch)
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting blog files for {repo}: {e}")
        raise BlogError(f"Failed to get blog files for repository '{repo}': {str(e)}") from e


async def get_blog_post_by_markdown_path(markdown_path: str, repo: Optional[str] = None) -> Optional[dict]:
    """Helper to fetch and parse a specific blog post by its markdown path."""
    blog_files = await get_blog_files(repo)
    for file_info in blog_files:
        if file_info["path"] == markdown_path:
            return await parse_markdown_content(file_info)
    return None


def format_blog_post(blog_post: dict, prefix: str = "Blog Post") -> str:
    """Format a blog post dict into a readable string."""
    return f"""{prefix}:

Title: {blog_post["title"]}
URL: {blog_post["url"]}
Date: {blog_post["date"] or "Unknown"}

Content:
{blog_post["content"]}
"""


async def parse_markdown_content(file_info: dict) -> dict:
    """Parse markdown content and extract title, content, and metadata."""
    try:
        # Fetch the raw markdown content
        markdown_content = await fetch_url(file_info["download_url"])

        # Parse markdown content to extract title and content
        lines = markdown_content.split("\n")
        title = "Untitled"
        content = markdown_content
        date = None

        # Look for title in the first few lines
        for line in lines[:10]:
            line = line.strip()
            # Check for markdown title (# Title)
            if line.startswith("# "):
                title = line[2:].strip()
                break
            # Check for yaml frontmatter title
            elif line.startswith("title:"):
                title = line.replace("title:", "").strip().strip('"').strip("'")
                break

        # Look for date in yaml frontmatter
        for line in lines[:20]:
            line = line.strip()
            if line.startswith("date:"):
                date = line.replace("date:", "").strip().strip('"').strip("'")
                break

        # If no title found from markdown, use filename
        if title == "Untitled":
            title = file_info["name"].replace(".md", "").replace("-", " ").replace("_", " ").title()

        # Clean up content - remove excessive whitespace
        content = re.sub(r"\n\s*\n", "\n\n", content).strip()

        content_text = content
        excerpt_text = content[:200] + "..." if len(content) > 200 else content

        return {
            "title": title[:200],  # Limit title length
            "url": file_info["html_url"],
            "content": content_text,
            "excerpt": excerpt_text,
            "date": date,
            "filename": file_info["name"],
        }

    except Exception as e:
        logger.error(f"Error parsing markdown for {file_info.get('name', 'unknown')}: {e}")
        return {
            "title": "Error loading post",
            "url": file_info.get("html_url", ""),
            "content": f"Error: {str(e)}",
            "excerpt": f"Error: {str(e)}",
            "date": None,
            "filename": file_info.get("name", "unknown"),
        }


@mcp.tool
async def list_repos() -> str:
    """List all available repositories.

    Use this to discover which repositories are accessible before calling
    other tools with the repo parameter. If GITHUB_REPOS="*", this will
    show all public repos for GITHUB_REPO_OWNER.
    """
    try:
        repos = await get_available_repos()
        return json.dumps({
            "owner": GITHUB_REPO_OWNER,
            "default_repo": DEFAULT_REPO,
            "repositories": repos,
            "count": len(repos)
        }, indent=2)
    except BlogError as e:
        # Specific errors from get_available_repos
        logger.error(f"BlogError in list_repos: {e}")
        return json.dumps({
            "error": str(e),
            "owner": GITHUB_REPO_OWNER,
            "default_repo": DEFAULT_REPO
        }, indent=2)
    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error in list_repos: {e}")
        return json.dumps({
            "error": f"Unexpected error listing repositories: {str(e)}",
            "owner": GITHUB_REPO_OWNER,
            "default_repo": DEFAULT_REPO
        }, indent=2)


@mcp.tool
def blog_info(repo: Optional[str] = None) -> str:
    """Get information about the blog. Optionally specify a repository."""
    repo_name = repo if repo else DEFAULT_REPO
    return f"""Blog Information:
- URL: {BLOG_URL}
- Owner: {GITHUB_REPO_OWNER}
- Repository: {repo_name}
- Description: MCP server for interacting with blog content directly from GitHub
- Source: Markdown files from GitHub repository ({GITHUB_REPO_OWNER}/{repo_name})

Available tools:
- list_repos: List all available repositories
- blog_info: Get this information
- random_blog: Get a random blog post
- read_blog_post: Read a specific post by URL
- random_blog_url: Get a random post URL
- blog_search: Search posts by query (returns JSON)
- recent_blog_posts: Get the most recent blog posts (returns JSON)
- all_blog_posts: Get all blog posts (returns JSON)
- get_recent_changes: Get recent changes/commits
"""


@mcp.tool
async def random_blog(include_content: bool = True, repo: Optional[str] = None) -> str:
    """Get a random blog post. Optionally specify a repository."""
    try:
        blog_files = await get_blog_files(repo)
        if not blog_files:
            return "No blog posts found."

        random_file = random.choice(blog_files)

        if include_content:
            blog_post = await parse_markdown_content(random_file)
            return format_blog_post(blog_post, "Random Blog Post")
        else:
            return f"Random blog post URL: {random_file['html_url']}"

    except Exception as e:
        return f"Error getting random blog post: {str(e)}"


@mcp.tool
async def all_blog_posts(repo: Optional[str] = None) -> str:
    """Get all blog posts as JSON data. Optionally specify a repository."""
    try:
        # Use cached back-links data for efficiency
        blog_data = await get_blog_data(repo)
        url_info = blog_data.get("url_info", {})

        if not url_info:
            return json.dumps({"error": "No blog posts found."})

        # Collect all blog posts with their metadata
        blog_posts = []
        for url, info in url_info.items():
            # Include posts from _d/, _posts/, and td/ directories
            markdown_path = info.get("markdown_path", "")
            if not markdown_path:
                continue
            if not (markdown_path.startswith("_d/") or
                    markdown_path.startswith("_posts/") or
                    markdown_path.startswith("td/")):
                continue

            # Return rich data from back-links
            post = {
                "title": info.get("title", "Untitled"),
                "url": f"{BLOG_URL}{url}",
                "description": info.get("description", ""),
                "last_modified": info.get("last_modified", ""),
                "doc_size": info.get("doc_size", 0),
                "markdown_path": markdown_path,
                "file_path": info.get("file_path", ""),
                "redirect_url": info.get("redirect_url", ""),
            }
            blog_posts.append(post)

        if not blog_posts:
            return json.dumps({"error": "No blog posts found."})

        # Sort by last_modified timestamp (most recent first)
        def sort_key(post):
            timestamp = post.get("last_modified", "")
            if timestamp:
                return timestamp
            return "0000-00-00T00:00:00"  # Put posts without timestamps at the end

        blog_posts.sort(key=sort_key, reverse=True)

        result = {
            "count": len(blog_posts),
            "posts": blog_posts
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Error getting all blog posts: {str(e)}"})


@mcp.tool
async def read_blog_post(url: str, repo: Optional[str] = None) -> str:
    """Read a specific blog post by URL, redirect path, or markdown path. Optionally specify a repository."""
    if not url or not isinstance(url, str) or len(url.strip()) == 0:
        return "Error: URL must be a non-empty string"

    url = url.strip()

    try:
        blog_data = await get_blog_data(repo)
        url_info = blog_data.get("url_info", {})
        redirects = blog_data.get("redirects", {})  # Get top-level redirects

        # Handle different URL formats
        if url.startswith("http"):
            # Full URL - extract path
            blog_domain = BLOG_URL.replace("https://", "").replace("http://", "")
            if blog_domain in url:
                path = url.replace(f"https://{blog_domain}", "").replace(f"http://{blog_domain}", "")
                if not path:
                    path = "/"  # Root path
            else:
                return f"Error: URL must be from {blog_domain}"
        elif ".md" in url:
            # Markdown path - just search for it in url_info
            found = False
            for url_path, info in url_info.items():
                markdown_path = info.get("markdown_path", "")
                # Simple check - does the markdown_path match or contain what was provided?
                if markdown_path and (
                    markdown_path == url or
                    markdown_path.endswith(url) or
                    url.endswith(markdown_path) or
                    url.split("/")[-1] == markdown_path.split("/")[-1]  # Same filename
                ):
                    path = url_path
                    found = True
                    break

            if not found:
                return f"Blog post not found for markdown path: {url}"
        else:
            # Assume it's a path like /42 or /fortytwo or just 42
            path = url if url.startswith("/") else f"/{url}"

        # Check if path exists directly
        if path in url_info:
            markdown_path = url_info[path].get("markdown_path", "")
            if markdown_path:
                # Found it! Get the file
                blog_post = await get_blog_post_by_markdown_path(markdown_path, repo)
                if blog_post:
                    return format_blog_post(blog_post)

        # Check top-level redirects first
        if path in redirects:
            # Found a redirect! Follow it to the target path
            target_path = redirects[path]
            if target_path in url_info:
                markdown_path = url_info[target_path].get("markdown_path", "")
                if markdown_path:
                    blog_post = await get_blog_post_by_markdown_path(markdown_path, repo)
                    if blog_post:
                        return format_blog_post(blog_post, f"Blog Post (via redirect from {path})")

        # FALLBACK: Check redirect_url field in url_info (extreme backward compatibility)
        # Note: Per data spec, redirect_url in url_info is currently always empty.
        # All redirects are in the top-level 'redirects' field (checked above).
        # This fallback is kept for extreme backward compatibility with potential legacy data.
        for url_path, info in url_info.items():
            redirect_url = info.get("redirect_url", "")
            if redirect_url and (redirect_url == path or redirect_url == path.lstrip("/")):
                markdown_path = info.get("markdown_path", "")
                if markdown_path:
                    blog_post = await get_blog_post_by_markdown_path(markdown_path, repo)
                    if blog_post:
                        return format_blog_post(blog_post, f"Blog Post (via redirect from {path})")

        return f"Blog post not found for: {url}"

    except BlogError as e:
        # Expected errors with good messages
        logger.error(f"BlogError in read_blog_post for URL '{url}': {e}")
        return f"Error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in read_blog_post for URL '{url}', repo '{repo}': {e}")
        return f"An unexpected error occurred while reading the blog post: {str(e)}"


@mcp.tool
async def random_blog_url(repo: Optional[str] = None) -> str:
    """Get a random blog post URL. Optionally specify a repository."""
    try:
        blog_files = await get_blog_files(repo)
        if not blog_files:
            return "No blog posts found."

        random_file = random.choice(blog_files)
        return random_file["html_url"]

    except Exception as e:
        return f"Error getting random blog URL: {str(e)}"


@mcp.tool
async def blog_search(query: str, limit: int = 5, repo: Optional[str] = None) -> str:
    """Search blog posts by title or content, returning JSON data. Optionally specify a repository."""
    # Validate query parameter
    if not query or not isinstance(query, str) or len(query.strip()) == 0:
        return json.dumps({"error": "Search query is required and must be a non-empty string"})

    # Validate and sanitize limit
    try:
        limit = int(limit)
        if limit < 1 or limit > 20:
            limit = min(max(limit, 1), 20)  # Clamp between 1 and 20
    except (ValueError, TypeError):
        limit = 5  # Default fallback

    # Sanitize query (basic protection against injection)
    query = query.strip().lower()[:100]  # Limit query length

    try:
        # Use cached back-links data instead of fetching individual files
        blog_data = await get_blog_data(repo)
        url_info = blog_data.get("url_info", {})

        if not url_info:
            return json.dumps({"error": "No blog posts found."})

        # Search through blog posts using pre-processed metadata
        matching_posts = []
        for url, info in url_info.items():
            # Include posts from _d/, _posts/, and td/ directories
            markdown_path = info.get("markdown_path", "")
            if not markdown_path:
                continue
            if not (markdown_path.startswith("_d/") or
                    markdown_path.startswith("_posts/") or
                    markdown_path.startswith("td/")):
                continue

            # Search in title and description (no need to download full content)
            title = info.get("title", "").lower()
            description = info.get("description", "").lower()

            if query in title or query in description:
                post = {
                    "title": info.get("title", "Untitled"),
                    "url": f"{BLOG_URL}{url}",
                    "description": info.get("description", ""),
                    "last_modified": info.get("last_modified", ""),
                    "doc_size": info.get("doc_size", 0),
                    "markdown_path": markdown_path,
                    "file_path": info.get("file_path", ""),
                    "incoming_links": info.get("incoming_links", []),
                    "outgoing_links": info.get("outgoing_links", []),
                    "redirect_url": info.get("redirect_url", ""),
                }
                matching_posts.append(post)

                if len(matching_posts) >= limit:
                    break

        if not matching_posts:
            return json.dumps({"error": f"No blog posts found matching '{query}'"})

        result = {
            "query": query,
            "count": len(matching_posts),
            "limit": limit,
            "posts": matching_posts
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Error searching blog posts: {str(e)}"})


@mcp.tool
async def recent_blog_posts(limit: int = 20, repo: Optional[str] = None) -> str:
    """Get the most recent blog posts as JSON data. Optionally specify a repository."""
    # Validate and sanitize limit
    try:
        limit = int(limit)
        if limit < 1 or limit > 50:
            limit = min(max(limit, 1), 50)  # Clamp between 1 and 50
    except (ValueError, TypeError):
        limit = 20  # Default fallback

    try:
        # Use cached back-links data for efficiency
        blog_data = await get_blog_data(repo)
        url_info = blog_data.get("url_info", {})

        if not url_info:
            return json.dumps({"error": "No blog posts found."})

        # Collect all blog posts with their metadata
        blog_posts = []
        for url, info in url_info.items():
            # Include posts from _d/, _posts/, and td/ directories
            markdown_path = info.get("markdown_path", "")
            if not markdown_path:
                continue
            if not (markdown_path.startswith("_d/") or
                    markdown_path.startswith("_posts/") or
                    markdown_path.startswith("td/")):
                continue

            # Return rich data from back-links
            post = {
                "title": info.get("title", "Untitled"),
                "url": f"{BLOG_URL}{url}",
                "description": info.get("description", ""),
                "last_modified": info.get("last_modified", ""),
                "doc_size": info.get("doc_size", 0),
                "markdown_path": markdown_path,
                "file_path": info.get("file_path", ""),
                "redirect_url": info.get("redirect_url", ""),
            }
            blog_posts.append(post)

        if not blog_posts:
            return json.dumps({"error": "No blog posts found."})

        # Sort by last_modified timestamp (most recent first) - posts without timestamps go to the end
        def sort_key(post):
            timestamp = post.get("last_modified", "")
            if timestamp:
                return timestamp
            return "0000-00-00T00:00:00"  # Put posts without timestamps at the end

        blog_posts.sort(key=sort_key, reverse=True)

        # Take the requested number of posts
        recent_posts = blog_posts[:limit]

        result = {
            "count": len(recent_posts),
            "limit": limit,
            "posts": recent_posts
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Error getting recent blog posts: {str(e)}"})


@mcp.tool
async def get_recent_changes(
    path: Optional[str] = None,
    days: Optional[int] = None,
    commits: Optional[int] = None,
    include_diff: bool = False,
    repo: Optional[str] = None
) -> str:
    """Get recent changes from the GitHub repository.

    Parameters:
    - path: Optional file/directory path to filter changes (e.g., "_d/", "_posts/", "td/")
    - days: Number of days to look back (mutually exclusive with commits)
    - commits: Number of recent commits to include (mutually exclusive with days, default: 10)
    - include_diff: Whether to include the actual diff content (default: False)
    - repo: Optional repository name (defaults to configured default repo)

    Returns formatted list of recent commits with file changes.
    """
    # Validate parameters
    if days is not None and commits is not None:
        return "Error: Cannot specify both 'days' and 'commits' parameters. Choose one."

    if days is not None and days <= 0:
        return "Error: 'days' must be a positive number."

    if commits is not None and commits <= 0:
        return "Error: 'commits' must be a positive number."

    # Validate that if include_diff is true, path must be a specific file (not a directory)
    # Rationale: Including diffs for multiple files creates massive output; limit to single file
    if include_diff and path:
        if path.endswith('/'):
            return "Error: When include_diff is true, path must be a specific file, not a directory."
        if not path.endswith('.md'):
            return "Error: When include_diff is true, path must be a markdown file (ending in .md)."

    # Set defaults
    if days is None and commits is None:
        commits = 10

    # If commits specified, ensure it's reasonable
    if commits and commits > 100:
        commits = 100  # Cap at 100 to avoid excessive API calls

    try:
        # Validate and get repo
        repo = validate_repo(repo)

        # Build query parameters for commits endpoint
        params = {
            "per_page": commits if commits else 100  # Get more if filtering by date
        }

        # Add path filter if specified
        if path:
            # Ensure path doesn't start with / for GitHub API
            if path.startswith("/"):
                path = path[1:]
            params["path"] = path

        # Add date filter if specified
        if days:
            since_date = datetime.now() - timedelta(days=days)
            params["since"] = since_date.isoformat() + "Z"

        # Fetch commits list
        commits_url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{repo}/commits"
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Fetching commits from GitHub: {commits_url}")
            response = await client.get(commits_url, params=params)
            response.raise_for_status()
            commits_data = response.json()

        if not commits_data:
            return "No commits found for the specified criteria."

        # If we're filtering by days and got too many, limit them
        if days and len(commits_data) > 50:
            commits_data = commits_data[:50]

        # Fetch detailed commit info in parallel (with file changes)
        # Use semaphore to limit concurrent requests
        # Limit of 15 prevents overwhelming GitHub API (rate limit: 60/hour unauthenticated, 5000/hour authenticated)
        semaphore = asyncio.Semaphore(15)

        async def fetch_commit_details(commit_sha: str) -> dict:
            async with semaphore:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    commit_url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{repo}/commits/{commit_sha}"
                    try:
                        response = await client.get(commit_url)
                        response.raise_for_status()
                        return response.json()
                    except Exception as e:
                        logger.error(f"Error fetching commit {commit_sha}: {e}")
                        return None

        # Fetch all commit details in parallel
        tasks = [fetch_commit_details(commit["sha"]) for commit in commits_data]
        detailed_commits = await asyncio.gather(*tasks)

        # Filter out failed fetches
        detailed_commits = [c for c in detailed_commits if c is not None]

        if not detailed_commits:
            return "Error: Failed to fetch commit details."

        # Format the output
        output_lines = []

        # Add header
        if days:
            output_lines.append(f"Recent changes (last {days} days):")
        else:
            output_lines.append(f"Recent changes (last {len(detailed_commits)} commits):")
        output_lines.append("")

        for commit in detailed_commits:
            # Calculate relative time
            commit_date = datetime.fromisoformat(commit["commit"]["author"]["date"].replace("Z", "+00:00"))
            now = datetime.now(commit_date.tzinfo)
            delta = now - commit_date

            if delta.days > 0:
                time_ago = f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
            elif delta.seconds > 3600:
                hours = delta.seconds // 3600
                time_ago = f"{hours} hour{'s' if hours != 1 else ''} ago"
            else:
                minutes = delta.seconds // 60
                time_ago = f"{minutes} minute{'s' if minutes != 1 else ''} ago"

            # Add commit info
            output_lines.append(f"Commit: {commit['sha'][:7]} ({time_ago})")
            output_lines.append(f"Author: {commit['commit']['author']['name']}")
            output_lines.append(f"Message: {commit['commit']['message'].split('\n')[0]}")  # First line only

            # Add file changes - filter for blog files if no specific path was given
            if "files" in commit:
                blog_files = []
                for file in commit["files"]:
                    filename = file["filename"]
                    # If no path filter, only show blog-related files
                    if not path:
                        if not (filename.startswith("_d/") or
                                filename.startswith("_posts/") or
                                filename.startswith("td/")):
                            continue
                    blog_files.append(file)

                if blog_files:
                    output_lines.append("Files changed:")
                    for file in blog_files:
                        status = file["status"]
                        additions = file.get("additions", 0)
                        deletions = file.get("deletions", 0)

                        if status == "added":
                            change_str = f"+{additions} lines (new file)"
                        elif status == "removed":
                            change_str = f"-{deletions} lines (deleted)"
                        elif status == "renamed":
                            change_str = f"renamed from {file.get('previous_filename', '?')}"
                        else:  # modified
                            change_str = f"+{additions} -{deletions} lines"

                        output_lines.append(f"  - {file['filename']}: {change_str}")

                        # Include diff if requested and available
                        if include_diff and "patch" in file:
                            output_lines.append("    Diff:")
                            # Limit diff output to first 10 lines
                            diff_lines = file["patch"].split("\n")[:10]
                            for diff_line in diff_lines:
                                output_lines.append(f"      {diff_line}")
                            if len(file["patch"].split("\n")) > 10:
                                output_lines.append("      ... (diff truncated)")

            output_lines.append("")  # Empty line between commits

        return "\n".join(output_lines)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"Error: Repository or path not found. Path: {path or 'root'}"
        elif e.response.status_code == 403:
            return "Error: GitHub API rate limit exceeded. Please try again later."
        else:
            return f"Error: GitHub API returned status {e.response.status_code}"
    except Exception as e:
        logger.error(f"Error in get_recent_changes: {e}")
        return f"Error getting recent changes: {str(e)}"


if __name__ == "__main__":
    mcp.run()
