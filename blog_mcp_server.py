#!/usr/bin/env python3
"""
Blog MCP Server

A FastMCP server that provides tools for interacting with GitHub repositories.
Supports multiple repos with repo parameters on all tools.

Configuration via environment variables:
- GITHUB_REPO_OWNER: GitHub username/org (default: idvorkin)
- GITHUB_REPOS: Comma-separated list of repos or '*' for all (default: idvorkin.github.io)
- DEFAULT_REPO: Default repo when not specified (default: idvorkin.github.io)
- BLOG_URL: Base URL for blog (optional, only for blog repos)
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

# Server configuration from environment variables
GITHUB_OWNER = os.getenv("GITHUB_REPO_OWNER", "idvorkin")
GITHUB_REPOS_CONFIG = os.getenv("GITHUB_REPOS", "idvorkin.github.io")
DEFAULT_REPO = os.getenv("DEFAULT_REPO", "idvorkin.github.io")
BLOG_URL = os.getenv("BLOG_URL", "https://idvork.in")

# Server name based on configuration
server_name = f"{GITHUB_OWNER}-mcp-server"
mcp = FastMCP(server_name)

# Cache for back-links data per repo (expires after 5 minutes)
# Structure: {repo_name: {"data": dict, "timestamp": float}}
_repo_caches: dict[str, dict] = {}
CACHE_DURATION = 300  # 5 minutes

# Allowed repos (populated at startup)
_allowed_repos: list[str] = []


class BlogError(Exception):
    """Base exception for blog operations."""

    pass


async def initialize_repos() -> None:
    """Initialize the list of allowed repos based on configuration."""
    global _allowed_repos

    if GITHUB_REPOS_CONFIG == "*":
        # Fetch all repos from GitHub API
        logger.info(f"Fetching all repos for {GITHUB_OWNER}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"https://api.github.com/users/{GITHUB_OWNER}/repos",
                    params={"per_page": 100, "type": "public"}
                )
                response.raise_for_status()
                repos_data = response.json()
                _allowed_repos = [repo["name"] for repo in repos_data]
                logger.info(f"Loaded {len(_allowed_repos)} repos for {GITHUB_OWNER}")
        except Exception as e:
            logger.error(f"Failed to fetch repos for {GITHUB_OWNER}: {e}")
            # Fall back to default repo
            _allowed_repos = [DEFAULT_REPO]
    else:
        # Use explicit list from config
        _allowed_repos = [repo.strip() for repo in GITHUB_REPOS_CONFIG.split(",")]
        logger.info(f"Configured repos: {_allowed_repos}")

    # Ensure default repo is in the list
    if DEFAULT_REPO not in _allowed_repos:
        _allowed_repos.insert(0, DEFAULT_REPO)


def validate_repo(repo: Optional[str]) -> str:
    """Validate and return the repo name, using default if not specified."""
    if repo is None:
        return DEFAULT_REPO

    repo = repo.strip()
    if repo not in _allowed_repos:
        raise BlogError(
            f"Repository '{repo}' not allowed. Available repos: {', '.join(_allowed_repos)}"
        )

    return repo


def get_repo_url(repo: str) -> str:
    """Get the GitHub API URL for a repository."""
    return f"https://api.github.com/repos/{GITHUB_OWNER}/{repo}"


def get_backlinks_url(repo: str, branch: str = "master") -> str:
    """Get the URL for back-links.json for a repository."""
    return f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{repo}/{branch}/back-links.json"


async def fetch_url(url: str) -> str:
    """Fetch content from a URL."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()

            # Limit response size to prevent memory issues
            content = response.text
            if len(content) > 1_000_000:  # 1MB limit
                logger.warning(
                    f"Content from {url} is very large ({len(content)} chars), truncating"
                )
                content = content[:1_000_000]

            return content
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
            raise BlogError(f"Failed to fetch {url}: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            raise BlogError(f"Unexpected error fetching {url}: {e}") from e


async def get_blog_data(repo: str) -> dict:
    """Get cached blog data from back-links.json file for a specific repo."""
    global _repo_caches

    current_time = time.time()
    repo_cache = _repo_caches.get(repo)

    # Return cached data if still valid
    if repo_cache and (current_time - repo_cache["timestamp"]) < CACHE_DURATION:
        return repo_cache["data"]

    try:
        logger.info(f"Fetching fresh blog data from back-links.json for {repo}")
        backlinks_url = get_backlinks_url(repo)
        content = await fetch_url(backlinks_url)
        data = json.loads(content)

        # Update cache
        _repo_caches[repo] = {"data": data, "timestamp": current_time}

        logger.info(f"Cached {len(data.get('url_info', {}))} entries for {repo}")
        return data

    except Exception as e:
        logger.error(f"Failed to fetch back-links.json for {repo}: {e}")
        # Fall back to cached data if available, even if expired
        if repo_cache:
            logger.warning(f"Using expired cache for {repo} due to fetch failure")
            return repo_cache["data"]

        # If this repo doesn't have back-links.json, return empty structure
        logger.warning(f"Repository {repo} does not have back-links.json, returning empty data")
        return {"url_info": {}, "redirects": {}}


async def get_blog_files(repo: str) -> list[dict]:
    """Get all blog post files - optimized to use back-links.json."""
    try:
        blog_data = await get_blog_data(repo)
        url_info = blog_data.get("url_info", {})

        blog_files = []
        for url, info in url_info.items():
            # Include blog posts from _d/, _posts/, and td/ directories
            markdown_path = info.get("markdown_path", "")
            if not markdown_path:
                continue
            # Include posts from _d/, _posts/, and td/ directories
            if not (markdown_path.startswith("_d/") or
                    markdown_path.startswith("_posts/") or
                    markdown_path.startswith("td/")):
                continue

            # Convert back-links format to old blog files format for compatibility
            blog_file = {
                "name": markdown_path.split("/")[-1] if "/" in markdown_path else markdown_path,
                "path": markdown_path,
                "download_url": f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{repo}/master/{markdown_path}",
                "html_url": f"{BLOG_URL}{url}",  # Use the actual blog URL
            }
            blog_files.append(blog_file)

        logger.info(f"Found {len(blog_files)} blog files for {repo} (optimized)")
        return blog_files  # Return all blog files

    except Exception as e:
        logger.error(f"Error getting blog files for {repo}: {e}")
        return []


async def get_blog_post_by_markdown_path(markdown_path: str, repo: str) -> Optional[dict]:
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

        # Don't clip content length
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
    """List all available repositories that can be accessed"""
    if not _allowed_repos:
        await initialize_repos()

    repos_info = []
    repos_info.append(f"Available repositories for {GITHUB_OWNER}:")
    repos_info.append(f"Total: {len(_allowed_repos)} repos")
    repos_info.append(f"Default repo: {DEFAULT_REPO}")
    repos_info.append("")
    repos_info.append("Repositories:")
    for repo in _allowed_repos:
        repos_info.append(f"  - {repo}")

    return "\n".join(repos_info)


@mcp.tool
def blog_info(repo: Optional[str] = None) -> str:
    """Get information about the repository and available tools

    Parameters:
    - repo: Repository name (optional, defaults to configured default repo)
    """
    try:
        repo_name = validate_repo(repo)
    except BlogError as e:
        return f"Error: {e}"

    return f"""Repository Information:
- Owner: {GITHUB_OWNER}
- Repository: {repo_name}
- GitHub URL: {get_repo_url(repo_name)}
- Blog URL: {BLOG_URL} (if applicable)

Available tools:
- list_repos: List all available repositories
- blog_info: Get repository information
- random_blog: Get a random blog post
- read_blog_post: Read a specific post by URL
- random_blog_url: Get a random post URL
- blog_search: Search posts by query (returns JSON)
- recent_blog_posts: Get the most recent blog posts (returns JSON)
- all_blog_posts: Get all blog posts (returns JSON)
- get_recent_changes: Get recent commits from the repository

All tools accept an optional 'repo' parameter to specify which repository to use.
"""


@mcp.tool
async def random_blog(include_content: bool = True, repo: Optional[str] = None) -> str:
    """Get a random blog post from the repository

    Parameters:
    - include_content: Whether to include full content (default: True)
    - repo: Repository name (optional, defaults to configured default repo)
    """
    try:
        repo_name = validate_repo(repo)
        blog_files = await get_blog_files(repo_name)
        if not blog_files:
            return f"No blog posts found in repository '{repo_name}'."

        random_file = random.choice(blog_files)

        if include_content:
            blog_post = await parse_markdown_content(random_file)
            return format_blog_post(blog_post, f"Random Blog Post from {repo_name}")
        else:
            return f"Random blog post URL: {random_file['html_url']}"

    except BlogError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error getting random blog post: {str(e)}"


@mcp.tool
async def all_blog_posts(repo: Optional[str] = None) -> str:
    """Get all blog posts from the repository as JSON data

    Parameters:
    - repo: Repository name (optional, defaults to configured default repo)
    """
    try:
        repo_name = validate_repo(repo)

        # Use cached back-links data for efficiency
        blog_data = await get_blog_data(repo_name)
        url_info = blog_data.get("url_info", {})

        if not url_info:
            return json.dumps({"error": f"No blog posts found in repository '{repo_name}'."})

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
            return json.dumps({"error": f"No blog posts found in repository '{repo_name}'."})

        # Sort by last_modified timestamp (most recent first)
        def sort_key(post):
            timestamp = post.get("last_modified", "")
            if timestamp:
                return timestamp
            return "0000-00-00T00:00:00"  # Put posts without timestamps at the end

        blog_posts.sort(key=sort_key, reverse=True)

        result = {
            "repository": repo_name,
            "count": len(blog_posts),
            "posts": blog_posts
        }

        return json.dumps(result, indent=2)

    except BlogError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Error getting all blog posts: {str(e)}"})


@mcp.tool
async def read_blog_post(url: str, repo: Optional[str] = None) -> str:
    """Read a specific blog post by URL, redirect path, or markdown path (e.g., _d/42.md)

    Parameters:
    - url: Blog post URL, redirect path, or markdown path
    - repo: Repository name (optional, defaults to configured default repo)
    """
    if not url or not isinstance(url, str) or len(url.strip()) == 0:
        return "Error: URL must be a non-empty string"

    url = url.strip()

    try:
        repo_name = validate_repo(repo)
        blog_data = await get_blog_data(repo_name)
        url_info = blog_data.get("url_info", {})
        redirects = blog_data.get("redirects", {})  # Get top-level redirects

        # Handle different URL formats
        if url.startswith("http"):
            # Full URL - extract path
            if "idvork.in" in url:
                path = url.replace("https://idvork.in", "").replace("http://idvork.in", "")
                if not path:
                    path = "/"  # Root path
            else:
                return "Error: URL must be from idvork.in"
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
                blog_post = await get_blog_post_by_markdown_path(markdown_path, repo_name)
                if blog_post:
                    return format_blog_post(blog_post)

        # Check top-level redirects first
        if path in redirects:
            # Found a redirect! Follow it to the target path
            target_path = redirects[path]
            if target_path in url_info:
                markdown_path = url_info[target_path].get("markdown_path", "")
                if markdown_path:
                    blog_post = await get_blog_post_by_markdown_path(markdown_path, repo_name)
                    if blog_post:
                        return format_blog_post(blog_post, f"Blog Post (via redirect from {path})")

        # FALLBACK: Check deprecated redirect_url in url_info (for backward compatibility)
        # TODO: This can be removed in a future update when all redirects are moved to top-level 'redirects'
        for url_path, info in url_info.items():
            redirect_url = info.get("redirect_url", "")
            if redirect_url and (redirect_url == path or redirect_url == path.lstrip("/")):
                # Found a post that redirects to our path
                markdown_path = info.get("markdown_path", "")
                if markdown_path:
                    blog_post = await get_blog_post_by_markdown_path(markdown_path, repo_name)
                    if blog_post:
                        return format_blog_post(blog_post, f"Blog Post (via deprecated redirect from {path})")

        # Future improvements:
        # - Consider implementing recursive redirect resolution with depth limit
        # - Add case-insensitive redirect matching
        # - Implement more detailed error logging for failed redirects

        return f"Blog post not found for: {url}"

    except BlogError as e:
        return f"Error: {e}"
    except Exception as e:
        logger.error(f"Unexpected error in read_blog_post: {e}")
        return "An unexpected error occurred while reading the blog post"


@mcp.tool
async def random_blog_url(repo: Optional[str] = None) -> str:
    """Get a random blog post URL from the repository

    Parameters:
    - repo: Repository name (optional, defaults to configured default repo)
    """
    try:
        repo_name = validate_repo(repo)
        blog_files = await get_blog_files(repo_name)
        if not blog_files:
            return f"No blog posts found in repository '{repo_name}'."

        random_file = random.choice(blog_files)
        return random_file["html_url"]

    except BlogError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error getting random blog URL: {str(e)}"


@mcp.tool
async def blog_search(query: str, limit: int = 5, repo: Optional[str] = None) -> str:
    """Search blog posts by title or content, returning JSON data

    Parameters:
    - query: Search query to match against title and description
    - limit: Maximum number of results (default: 5, max: 20)
    - repo: Repository name (optional, defaults to configured default repo)
    """
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
        repo_name = validate_repo(repo)

        # Use cached back-links data instead of fetching individual files
        blog_data = await get_blog_data(repo_name)
        url_info = blog_data.get("url_info", {})

        if not url_info:
            return json.dumps({"error": f"No blog posts found in repository '{repo_name}'."})

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
            "repository": repo_name,
            "query": query,
            "count": len(matching_posts),
            "limit": limit,
            "posts": matching_posts
        }

        return json.dumps(result, indent=2)

    except BlogError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Error searching blog posts: {str(e)}"})


@mcp.tool
async def recent_blog_posts(limit: int = 20, repo: Optional[str] = None) -> str:
    """Get the most recent blog posts from the repository as JSON data

    Parameters:
    - limit: Maximum number of posts (default: 20, max: 50)
    - repo: Repository name (optional, defaults to configured default repo)
    """
    # Validate and sanitize limit
    try:
        limit = int(limit)
        if limit < 1 or limit > 50:
            limit = min(max(limit, 1), 50)  # Clamp between 1 and 50
    except (ValueError, TypeError):
        limit = 20  # Default fallback

    try:
        repo_name = validate_repo(repo)

        # Use cached back-links data for efficiency
        blog_data = await get_blog_data(repo_name)
        url_info = blog_data.get("url_info", {})

        if not url_info:
            return json.dumps({"error": f"No blog posts found in repository '{repo_name}'."})

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
            return json.dumps({"error": f"No blog posts found in repository '{repo_name}'."})

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
            "repository": repo_name,
            "count": len(recent_posts),
            "limit": limit,
            "posts": recent_posts
        }

        return json.dumps(result, indent=2)

    except BlogError as e:
        return json.dumps({"error": str(e)})
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
    - repo: Repository name (optional, defaults to configured default repo)

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
        repo_name = validate_repo(repo)
        repo_url = get_repo_url(repo_name)

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
        commits_url = f"{repo_url}/commits"
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
        # Use semaphore to limit concurrent requests to 15
        semaphore = asyncio.Semaphore(15)

        async def fetch_commit_details(commit_sha: str) -> dict:
            async with semaphore:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    commit_url = f"{repo_url}/commits/{commit_sha}"
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

    except BlogError as e:
        return f"Error: {e}"
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
    # Initialize repos at startup
    import asyncio
    asyncio.run(initialize_repos())
    mcp.run()
