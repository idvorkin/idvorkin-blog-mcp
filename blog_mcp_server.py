#!/usr/bin/env python3
"""
Blog MCP Server

A FastMCP server that provides tools for interacting with Igor's blog at idvork.in.
This server offers seven tools:
- blog_info: Get information about the blog
- random_blog: Get a random blog post
- read_blog_post: Read a specific blog post by URL
- random_blog_url: Get a random blog post URL
- blog_search: Search blog posts (returns JSON)
- recent_blog_posts: Get the most recent blog posts (returns JSON)
- all_blog_posts: Get all blog posts (returns JSON)
"""

import json
import logging
import random
import re
import time
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
            # Skip non-blog posts (pages without markdown_path or not in _d directory)
            markdown_path = info.get("markdown_path", "")
            if not markdown_path or not markdown_path.startswith("_d/"):
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
        return blog_files[:50]  # Limit to 50 posts for compatibility

    except Exception as e:
        logger.error(f"Error getting blog files: {e}")
        return []


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

        # Limit content length to prevent memory issues
        max_content_length = 5000
        content_text = (
            content[:max_content_length] + "..." if len(content) > max_content_length else content
        )
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
            return f"""Random Blog Post:

Title: {blog_post["title"]}
URL: {blog_post["url"]}
Date: {blog_post["date"] or "Unknown"}

Content:
{blog_post["content"]}
"""
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
            # Skip non-blog posts
            markdown_path = info.get("markdown_path", "")
            if not markdown_path or not markdown_path.startswith("_d/"):
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
    """Read a specific blog post by URL"""
    if not url or not isinstance(url, str) or len(url.strip()) == 0:
        return "Error: URL must be a non-empty string"

    try:
        # Try to find the file by URL
        blog_files = await get_blog_files()
        for file_info in blog_files:
            if file_info["html_url"] == url.strip():
                blog_post = await parse_markdown_content(file_info)
                return f"""Blog Post:

Title: {blog_post["title"]}
URL: {blog_post["url"]}
Date: {blog_post["date"] or "Unknown"}

Content:
{blog_post["content"]}
"""

        return "Blog post not found in GitHub repository"

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
            # Skip non-blog posts
            markdown_path = info.get("markdown_path", "")
            if not markdown_path or not markdown_path.startswith("_d/"):
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
            # Skip non-blog posts
            markdown_path = info.get("markdown_path", "")
            if not markdown_path or not markdown_path.startswith("_d/"):
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


if __name__ == "__main__":
    mcp.run()
