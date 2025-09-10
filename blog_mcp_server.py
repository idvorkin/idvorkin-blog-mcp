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
import logging
import os
import random
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool
from pydantic import BaseModel, HttpUrl

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Server configuration
server = Server("blog-mcp-server")
BASE_URL = "https://idvork.in"


class BlogPost(BaseModel):
    """Model for a blog post."""
    title: str
    url: HttpUrl
    content: Optional[str] = None
    excerpt: Optional[str] = None
    date: Optional[str] = None


async def fetch_url(url: str) -> str:
    """Fetch content from a URL."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise


async def get_blog_posts() -> list[str]:
    """Get all blog post URLs from the sitemap or archive."""
    try:
        # Try to get from sitemap first
        sitemap_url = urljoin(BASE_URL, "/sitemap.xml")
        content = await fetch_url(sitemap_url)
        
        # Extract URLs from sitemap
        urls = re.findall(r'<loc>(.*?)</loc>', content)
        # Filter for blog posts (assuming they contain certain patterns)
        blog_urls = [url for url in urls if any(pattern in url for pattern in ['/posts/', '/blog/', '/articles/'])]
        
        if blog_urls:
            return blog_urls
            
        # Fallback: try to scrape main page for blog links
        main_content = await fetch_url(BASE_URL)
        # Look for blog post links
        links = re.findall(r'href="([^"]*)"', main_content)
        blog_urls = [urljoin(BASE_URL, link) for link in links 
                    if any(pattern in link for pattern in ['/posts/', '/blog/', '/articles/'])]
        
        return blog_urls[:50]  # Limit to 50 posts
        
    except Exception as e:
        logger.error(f"Error getting blog posts: {e}")
        return []


async def extract_blog_content(url: str) -> BlogPost:
    """Extract blog post content from a URL."""
    try:
        content = await fetch_url(url)
        
        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else "Untitled"
        
        # Extract main content (looking for common blog content containers)
        content_patterns = [
            r'<article[^>]*>(.*?)</article>',
            r'<main[^>]*>(.*?)</main>',
            r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*post[^"]*"[^>]*>(.*?)</div>',
        ]
        
        post_content = ""
        for pattern in content_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                post_content = match.group(1)
                break
        
        # Clean up HTML tags for readable text
        text_content = re.sub(r'<[^>]+>', '', post_content)
        text_content = re.sub(r'\s+', ' ', text_content).strip()
        
        # Extract date if possible
        date_match = re.search(r'<time[^>]*datetime="([^"]*)"', content, re.IGNORECASE)
        date = date_match.group(1) if date_match else None
        
        return BlogPost(
            title=title,
            url=url,
            content=text_content[:2000] + "..." if len(text_content) > 2000 else text_content,
            excerpt=text_content[:200] + "..." if len(text_content) > 200 else text_content,
            date=date
        )
        
    except Exception as e:
        logger.error(f"Error extracting content from {url}: {e}")
        return BlogPost(title="Error loading post", url=url, content=f"Error: {str(e)}")


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
- URL: {BASE_URL}
- Name: Igor's Blog
- Description: Personal blog by Igor Dvorkin covering technology, leadership, and life insights
- This MCP server provides tools to interact with the blog content including reading posts, searching, and getting random posts.

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
            blog_urls = await get_blog_posts()
            if not blog_urls:
                return [TextContent(type="text", text="No blog posts found.")]
            
            random_url = random.choice(blog_urls)
            
            if include_content:
                blog_post = await extract_blog_content(random_url)
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
                        text=f"Random blog post URL: {random_url}"
                    )
                ]
                
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting random blog post: {str(e)}")]
    
    elif name == "read_blog_post":
        url = arguments.get("url")
        if not url:
            return [TextContent(type="text", text="Error: URL parameter is required")]
        
        try:
            blog_post = await extract_blog_content(url)
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
        except Exception as e:
            return [TextContent(type="text", text=f"Error reading blog post: {str(e)}")]
    
    elif name == "random_blog_url":
        try:
            blog_urls = await get_blog_posts()
            if not blog_urls:
                return [TextContent(type="text", text="No blog posts found.")]
            
            random_url = random.choice(blog_urls)
            return [TextContent(type="text", text=random_url)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting random blog URL: {str(e)}")]
    
    elif name == "blog_search":
        query = arguments.get("query", "").lower()
        limit = arguments.get("limit", 5)
        
        if not query:
            return [TextContent(type="text", text="Error: Search query is required")]
        
        try:
            blog_urls = await get_blog_posts()
            if not blog_urls:
                return [TextContent(type="text", text="No blog posts found.")]
            
            # Search through blog posts
            matching_posts = []
            for url in blog_urls[:20]:  # Limit search to first 20 posts for performance
                try:
                    blog_post = await extract_blog_content(url)
                    # Check if query matches title or content
                    if (query in blog_post.title.lower() or 
                        (blog_post.content and query in blog_post.content.lower())):
                        matching_posts.append(blog_post)
                        
                    if len(matching_posts) >= limit:
                        break
                        
                except Exception as e:
                    logger.warning(f"Error processing {url} for search: {e}")
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