#!/usr/bin/env python3
"""
Common test utilities and fixtures for Blog MCP Server tests.
"""

from typing import Any, Dict, Optional

import pytest
from fastmcp import Client


def extract_content_text(result) -> str:
    """
    Extract text content from MCP tool result.

    Prefers result.data (FastMCP 3.0 feature) when it is a string,
    falls back to result.content[0].text for compatibility.

    Args:
        result: The tool call result from MCP client

    Returns:
        The extracted text content as a string
    """
    # FastMCP 3.0: result.data is the structured return value.
    # For string-returning tools it is the plain string directly.
    if hasattr(result, 'data') and isinstance(result.data, str):
        return result.data

    if not result.content:
        return ""

    content = result.content[0]
    return content.text if hasattr(content, 'text') else str(content)


class MCPTestClient:
    """Wrapper for MCP Client with common test utilities."""

    def __init__(self, endpoint_or_server):
        """
        Initialize test client with either an endpoint URL or server instance.

        Args:
            endpoint_or_server: Either a URL string or FastMCP server instance
        """
        self.client = Client(endpoint_or_server)

    async def __aenter__(self):
        """Enter async context."""
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *args):
        """Exit async context."""
        return await self.client.__aexit__(*args)

    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        """
        Call an MCP tool and return extracted text content.

        Args:
            tool_name: Name of the tool to call
            arguments: Optional arguments for the tool

        Returns:
            The extracted text content from the tool result
        """
        if arguments is None:
            arguments = {}

        result = await self.client.call_tool(tool_name, arguments)
        return extract_content_text(result)

    async def ping(self):
        """Ping the server."""
        return await self.client.ping()

    async def list_tools(self):
        """List available tools."""
        return await self.client.list_tools()


class BlogAssertions:
    """Common assertions for blog MCP tests."""

    @staticmethod
    def assert_blog_info(content: str):
        """Assert standard blog info content."""
        assert "Blog Information:" in content
        assert "Owner: idvorkin" in content
        assert "idvork.in" in content
        assert "Available tools:" in content

    @staticmethod
    def assert_valid_url(content: str):
        """Assert content contains a valid URL."""
        assert content.startswith("https://") or content.startswith("http://")
        assert "idvork.in" in content or "github.com" in content

    @staticmethod
    def assert_random_blog_post(content: str, with_content: bool = False):
        """Assert random blog post format."""
        assert (
            "Random Blog Post:" in content or
            "Random blog post URL:" in content
        )

        if with_content:
            assert "Title:" in content
            assert "URL:" in content
            assert "Content:" in content
        else:
            assert (
                "Title:" in content or
                "URL:" in content or
                "https://" in content
            )

    @staticmethod
    def assert_error_message(content: str, error_text: str):
        """Assert error message is present."""
        assert error_text in content