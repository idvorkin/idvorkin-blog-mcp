#!/usr/bin/env python3
"""
Blog MCP Server

A Model Context Protocol server that provides tools for interacting with Igor's blog at idvork.in.
This server offers five tools:
- blog_info: Get information about the blog
- random_blog: Get a random blog post
- read_blog_post: Read a specific blog post by URL
- random_blog_url: Get a random blog post URL
- blog_search: Search blog posts
"""

import asyncio
import json
import logging
import os
import random
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool
from pydantic import BaseModel, HttpUrl, validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Server configuration
server = Server("blog-mcp-server")
GITHUB_REPO_URL = "https://api.github.com/repos/idvorkin/idvorkin.github.io"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/master"
BLOG_URL = "https://idvork.in"
ALLOWED_DOMAINS = {"api.github.com", "raw.githubusercontent.com"}


class BlogFetchError(Exception):
    """Raised when blog content cannot be fetched."""
    pass


class BlogParseError(Exception):
    """Raised when blog content cannot be parsed."""
    pass


class InvalidURLError(Exception):
    """Raised when URL is invalid or not allowed."""
    pass


class BlogPost(BaseModel):
    """Model for a blog post."""
    title: str
    url: HttpUrl
    content: Optional[str] = None
    excerpt: Optional[str] = None
    date: Optional[str] = None
    
    @validator('url')
    def validate_url(cls, v):
        """Validate that URL has valid scheme."""
        if isinstance(v, str):
            parsed = urlparse(v)
        else:
            parsed = urlparse(str(v))
        
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"URL scheme {parsed.scheme} not allowed")
        return v


def validate_blog_url(url: str) -> str:
    """Validate that URL belongs to allowed domains and has valid scheme."""
    if not url or not isinstance(url, str):
        raise InvalidURLError("URL must be a non-empty string")
    
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise InvalidURLError(f"Invalid URL format: {e}")
    
    if parsed.netloc not in ALLOWED_DOMAINS:
        raise InvalidURLError(f"Domain {parsed.netloc} not allowed. Allowed domains: {ALLOWED_DOMAINS}")
    
    if parsed.scheme not in {"http", "https"}:
        raise InvalidURLError(f"Scheme {parsed.scheme} not allowed. Only http and https are allowed")
    
    return url


async def fetch_url(url: str) -> str:
    """Fetch content from a validated URL."""
    # Validate URL first
    validated_url = validate_blog_url(url)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(validated_url)
            response.raise_for_status()
            
            # Limit response size to prevent memory issues
            content = response.text
            if len(content) > 1_000_000:  # 1MB limit
                logger.warning(f"Content from {url} is very large ({len(content)} chars), truncating")
                content = content[:1_000_000]
            
            return content
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
            raise BlogFetchError(f"Failed to fetch {url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            raise BlogFetchError(f"Unexpected error fetching {url}: {e}")


async def get_blog_posts() -> list[dict]:
    """Get all blog post files from GitHub repository."""
    try:
        # Get files from the _d directory containing markdown blog posts
        api_url = f"{GITHUB_REPO_URL}/contents/_d"
        content = await fetch_url(api_url)
        
        # Parse JSON response
        files_data = json.loads(content)
        
        # Filter for markdown files
        markdown_files = []
        for file_info in files_data:
            if file_info.get('name', '').endswith('.md') and file_info.get('type') == 'file':
                markdown_files.append({
                    'name': file_info['name'],
                    'path': file_info['path'],
                    'download_url': file_info['download_url'],
                    'html_url': f"{BLOG_URL}/{file_info['name'].replace('.md', '')}"
                })
        
        return markdown_files[:50]  # Limit to 50 posts
        
    except InvalidURLError as e:
        logger.error(f"URL validation error getting blog posts: {e}")
        return []
    except BlogFetchError as e:
        logger.error(f"Fetch error getting blog posts: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error getting blog posts: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting blog posts: {e}")
        return []


async def extract_blog_content_from_file(file_info: dict) -> BlogPost:
    """Extract blog post content from a markdown file."""
    try:
        # Fetch the raw markdown content
        markdown_content = await fetch_url(file_info['download_url'])
        
        # Parse markdown content to extract title and content
        lines = markdown_content.split('\n')
        title = "Untitled"
        content = markdown_content
        date = None
        
        # Look for title in the first few lines
        for line in lines[:10]:
            line = line.strip()
            # Check for markdown title (# Title)
            if line.startswith('# '):
                title = line[2:].strip()
                break
            # Check for yaml frontmatter title
            elif line.startswith('title:'):
                title = line.replace('title:', '').strip().strip('"').strip("'")
                break
        
        # Look for date in yaml frontmatter
        for line in lines[:20]:
            line = line.strip()
            if line.startswith('date:'):
                date = line.replace('date:', '').strip().strip('"').strip("'")
                break
        
        # If no title found from markdown, use filename
        if title == "Untitled":
            title = file_info['name'].replace('.md', '').replace('-', ' ').replace('_', ' ').title()
        
        # Clean up content - remove excessive whitespace
        content = re.sub(r'\n\s*\n', '\n\n', content).strip()
        
        # Limit content length to prevent memory issues
        max_content_length = 5000
        content_text = content[:max_content_length] + "..." if len(content) > max_content_length else content
        excerpt_text = content[:200] + "..." if len(content) > 200 else content
        
        return BlogPost(
            title=title[:200],  # Limit title length
            url=file_info['html_url'],
            content=content_text,
            excerpt=excerpt_text,
            date=date
        )
        
    except InvalidURLError as e:
        logger.error(f"URL validation error for {file_info.get('name', 'unknown')}: {e}")
        return BlogPost(title="Invalid URL", url=file_info.get('html_url', ''), content=f"URL validation error: {str(e)}")
    except BlogFetchError as e:
        logger.error(f"Fetch error for {file_info.get('name', 'unknown')}: {e}")
        return BlogPost(title="Error loading post", url=file_info.get('html_url', ''), content=f"Fetch error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error extracting content from {file_info.get('name', 'unknown')}: {e}")
        return BlogPost(title="Unexpected error", url=file_info.get('html_url', ''), content=f"Unexpected error: {str(e)}")


async def extract_blog_content(url: str) -> BlogPost:
    """Extract blog post content from a URL (backwards compatibility)."""
    try:
        # Try to find the file by URL
        blog_files = await get_blog_posts()
        for file_info in blog_files:
            if file_info['html_url'] == url:
                return await extract_blog_content_from_file(file_info)
        
        # If not found, return error
        return BlogPost(title="Post not found", url=url, content="Blog post not found in GitHub repository")
        
    except Exception as e:
        logger.error(f"Unexpected error extracting content from {url}: {e}")
        return BlogPost(title="Unexpected error", url=url, content=f"Unexpected error: {str(e)}")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="blog_info",
            description="Get information about Igor's blog at idvork.in",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="random_blog",
            description="Get a random blog post from idvork.in",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_content": {
                        "type": "boolean",
                        "description": "Whether to include the full content of the blog post",
                        "default": True
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="read_blog_post",
            description="Read a specific blog post by URL",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the blog post to read",
                    }
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="random_blog_url",
            description="Get a random blog post URL from idvork.in",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="blog_search",
            description="Search blog posts by title or content",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find relevant blog posts",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                    }
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "blog_info":
        return [
            TextContent(
                type="text",
                text=f"""Blog Information:
- URL: {BLOG_URL}
- Name: Igor's Blog  
- Description: Personal blog by Igor Dvorkin covering technology, leadership, and life insights
- Source: Markdown files from GitHub repository (idvorkin/idvorkin.github.io)
- This MCP server provides tools to interact with the blog content by reading markdown files directly from GitHub.

Available tools:
- blog_info: Get this information
- random_blog: Get a random blog post
- read_blog_post: Read a specific post by URL
- random_blog_url: Get a random post URL
- blog_search: Search posts by query
"""
            )
        ]
    
    elif name == "random_blog":
        include_content = arguments.get("include_content", True)
        
        try:
            blog_files = await get_blog_posts()
            if not blog_files:
                return [TextContent(type="text", text="No blog posts found.")]
            
            random_file = random.choice(blog_files)
            
            if include_content:
                blog_post = await extract_blog_content_from_file(random_file)
                return [
                    TextContent(
                        type="text",
                        text=f"""Random Blog Post:

Title: {blog_post.title}
URL: {blog_post.url}
Date: {blog_post.date or 'Unknown'}

Content:
{blog_post.content}
"""
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text",
                        text=f"Random blog post URL: {random_file['html_url']}"
                    )
                ]
                
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting random blog post: {str(e)}")]
    
    elif name == "read_blog_post":
        url = arguments.get("url")
        if not url:
            return [TextContent(type="text", text="Error: URL parameter is required")]
        
        # Validate URL format and type
        if not isinstance(url, str) or len(url.strip()) == 0:
            return [TextContent(type="text", text="Error: URL must be a non-empty string")]
        
        try:
            blog_post = await extract_blog_content(url.strip())
            return [
                TextContent(
                    type="text",
                    text=f"""Blog Post:

Title: {blog_post.title}
URL: {blog_post.url}
Date: {blog_post.date or 'Unknown'}

Content:
{blog_post.content}
"""
                )
            ]
        except InvalidURLError as e:
            return [TextContent(type="text", text=f"Invalid URL: {str(e)}")]
        except (BlogFetchError, BlogParseError) as e:
            return [TextContent(type="text", text=f"Error reading blog post: {str(e)}")]
        except Exception as e:
            logger.error(f"Unexpected error in read_blog_post: {e}")
            return [TextContent(type="text", text="An unexpected error occurred while reading the blog post")]
    
    elif name == "random_blog_url":
        try:
            blog_files = await get_blog_posts()
            if not blog_files:
                return [TextContent(type="text", text="No blog posts found.")]
            
            random_file = random.choice(blog_files)
            return [TextContent(type="text", text=random_file['html_url'])]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting random blog URL: {str(e)}")]
    
    elif name == "blog_search":
        query = arguments.get("query", "")
        limit = arguments.get("limit", 5)
        
        # Validate query parameter
        if not query or not isinstance(query, str) or len(query.strip()) == 0:
            return [TextContent(type="text", text="Error: Search query is required and must be a non-empty string")]
        
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
            blog_files = await get_blog_posts()
            if not blog_files:
                return [TextContent(type="text", text="No blog posts found.")]
            
            # Search through blog posts
            matching_posts = []
            for file_info in blog_files[:20]:  # Limit search to first 20 posts for performance
                try:
                    blog_post = await extract_blog_content_from_file(file_info)
                    # Check if query matches title or content
                    if (query in blog_post.title.lower() or 
                        (blog_post.content and query in blog_post.content.lower())):
                        matching_posts.append(blog_post)
                        
                    if len(matching_posts) >= limit:
                        break
                        
                except Exception as e:
                    logger.warning(f"Error processing {file_info.get('name', 'unknown')} for search: {e}")
                    continue
            
            if not matching_posts:
                return [TextContent(type="text", text=f"No blog posts found matching '{query}'")]
            
            result_text = f"Found {len(matching_posts)} blog posts matching '{query}':\n\n"
            for i, post in enumerate(matching_posts, 1):
                result_text += f"{i}. {post.title}\n"
                result_text += f"   URL: {post.url}\n"
                result_text += f"   Excerpt: {post.excerpt}\n\n"
            
            return [TextContent(type="text", text=result_text)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error searching blog posts: {str(e)}")]
    
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Main entry point for the server."""
    # Initialize the server
    options = InitializationOptions(
        server_name="blog-mcp-server",
        server_version="0.1.0",
        capabilities=server.get_capabilities(
            notification_options=None,
            experimental_capabilities={},
        ),
    )
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            options,
        )


if __name__ == "__main__":
    asyncio.run(main())