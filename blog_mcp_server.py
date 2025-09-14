#!/usr/bin/env python3
"""
Blog MCP Server

A FastMCP server that provides tools for interacting with Igor's blog at idvork.in.
This server offers eight tools:
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

# Server configuration
mcp = FastMCP("blog-mcp-server")
GITHUB_REPO_URL = "https://api.github.com/repos/idvorkin/idvorkin.github.io"
BLOG_URL = "https://idvork.in"
BACKLINKS_URL = "https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/master/back-links.json"

# Cache for back-links data (expires after 5 minutes)
_blog_cache: Optional[dict] = None
_cache_timestamp: float = 0
CACHE_DURATION = 300  # 5 minutes


class BlogError(Exception):
    """Base exception for blog operations."""

    pass


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


async def get_blog_data() -> dict:
    """Get cached blog data from back-links.json file."""
    global _blog_cache, _cache_timestamp

    current_time = time.time()

    # Return cached data if still valid
    if _blog_cache and (current_time - _cache_timestamp) < CACHE_DURATION:
        return _blog_cache

    try:
        logger.info("Fetching fresh blog data from back-links.json")
        content = await fetch_url(BACKLINKS_URL)
        _blog_cache = json.loads(content)
        _cache_timestamp = current_time

        logger.info(f"Cached {len(_blog_cache.get('url_info', {}))} blog entries")
        return _blog_cache

    except Exception as e:
        logger.error(f"Failed to fetch back-links.json: {e}")
        # Fall back to cached data if available, even if expired
        if _blog_cache:
            logger.warning("Using expired cache due to fetch failure")
            return _blog_cache
        raise BlogError(f"Failed to get blog data: {e}") from e


async def get_blog_files() -> list[dict]:
    """Get all blog post files - optimized to use back-links.json."""
    try:
        blog_data = await get_blog_data()
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
                "download_url": f"https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/master/{markdown_path}",
                "html_url": f"{BLOG_URL}{url}",  # Use the actual blog URL
            }
            blog_files.append(blog_file)

        logger.info(f"Found {len(blog_files)} blog files (optimized)")
        return blog_files  # Return all blog files

    except Exception as e:
        logger.error(f"Error getting blog files: {e}")
        return []


async def get_blog_post_by_markdown_path(markdown_path: str) -> Optional[dict]:
    """Helper to fetch and parse a specific blog post by its markdown path."""
    blog_files = await get_blog_files()
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
def blog_info() -> str:
    """Get information about Igor's blog at idvork.in"""
    return f"""Blog Information:
- URL: {BLOG_URL}
- Name: Igor's Blog  
- Description: Personal blog by Igor Dvorkin covering technology, leadership, and life insights
- Source: Markdown files from GitHub repository (idvorkin/idvorkin.github.io)
- MCP server for interacting with the blog content directly from GitHub.

Available tools:
- blog_info: Get this information
- random_blog: Get a random blog post
- read_blog_post: Read a specific post by URL
- random_blog_url: Get a random post URL
- blog_search: Search posts by query (returns JSON)
- recent_blog_posts: Get the most recent blog posts (returns JSON)
- all_blog_posts: Get all blog posts (returns JSON)
"""


@mcp.tool
async def random_blog(include_content: bool = True) -> str:
    """Get a random blog post from idvork.in"""
    try:
        blog_files = await get_blog_files()
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
async def all_blog_posts() -> str:
    """Get all blog posts from idvork.in as JSON data"""
    try:
        # Use cached back-links data for efficiency
        blog_data = await get_blog_data()
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
async def read_blog_post(url: str) -> str:
    """Read a specific blog post by URL, redirect path, or markdown path (e.g., _d/42.md)"""
    if not url or not isinstance(url, str) or len(url.strip()) == 0:
        return "Error: URL must be a non-empty string"

    url = url.strip()

    try:
        blog_data = await get_blog_data()
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
                blog_post = await get_blog_post_by_markdown_path(markdown_path)
                if blog_post:
                    return format_blog_post(blog_post)

        # Check top-level redirects first
        if path in redirects:
            # Found a redirect! Follow it to the target path
            target_path = redirects[path]
            if target_path in url_info:
                markdown_path = url_info[target_path].get("markdown_path", "")
                if markdown_path:
                    blog_post = await get_blog_post_by_markdown_path(markdown_path)
                    if blog_post:
                        return format_blog_post(blog_post, f"Blog Post (via redirect from {path})")

        # Check redirects using back-links data (much faster than downloading all files!)
        # Look through url_info to find any post that redirects to this path
        for url_path, info in url_info.items():
            redirect_url = info.get("redirect_url", "")
            if redirect_url and (redirect_url == path or redirect_url == path.lstrip("/")):
                # Found a post that redirects to our path
                markdown_path = info.get("markdown_path", "")
                if markdown_path:
                    blog_post = await get_blog_post_by_markdown_path(markdown_path)
                    if blog_post:
                        return format_blog_post(blog_post, f"Blog Post (via redirect from {path})")

        return f"Blog post not found for: {url}"

    except Exception as e:
        logger.error(f"Unexpected error in read_blog_post: {e}")
        return "An unexpected error occurred while reading the blog post"


@mcp.tool
async def random_blog_url() -> str:
    """Get a random blog post URL from idvork.in"""
    try:
        blog_files = await get_blog_files()
        if not blog_files:
            return "No blog posts found."

        random_file = random.choice(blog_files)
        return random_file["html_url"]

    except Exception as e:
        return f"Error getting random blog URL: {str(e)}"


@mcp.tool
async def blog_search(query: str, limit: int = 5) -> str:
    """Search blog posts by title or content, returning JSON data"""
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
        blog_data = await get_blog_data()
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
async def recent_blog_posts(limit: int = 20) -> str:
    """Get the most recent blog posts from idvork.in as JSON data"""
    # Validate and sanitize limit
    try:
        limit = int(limit)
        if limit < 1 or limit > 50:
            limit = min(max(limit, 1), 50)  # Clamp between 1 and 50
    except (ValueError, TypeError):
        limit = 20  # Default fallback

    try:
        # Use cached back-links data for efficiency
        blog_data = await get_blog_data()
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
    include_diff: bool = False
) -> str:
    """Get recent changes from the GitHub repository for blog posts.

    Parameters:
    - path: Optional file/directory path to filter changes (e.g., "_d/", "_posts/", "td/")
    - days: Number of days to look back (mutually exclusive with commits)
    - commits: Number of recent commits to include (mutually exclusive with days, default: 10)
    - include_diff: Whether to include the actual diff content (default: False)

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
        commits_url = f"{GITHUB_REPO_URL}/commits"
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
                    commit_url = f"{GITHUB_REPO_URL}/commits/{commit_sha}"
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
