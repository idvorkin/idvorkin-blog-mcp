#!/usr/bin/env python3
"""
pytest configuration and shared fixtures.

Defines custom markers used across the test suite and provides
shared fixtures for MCP server testing with global state isolation.
"""

import copy

import pytest

import blog_mcp_server
from test_utils import BlogAssertions, MCPTestClient  # noqa: F401


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "network: marks tests that make real network calls to the GitHub API "
        "(deselect with '-m \"not network\"' for offline runs)",
    )


# ---------------------------------------------------------------------------
# Shared fixtures – used by test_unit.py, test_multi_repo.py, and test_e2e.py
# ---------------------------------------------------------------------------


@pytest.fixture
def mcp_server():
    """Provide the FastMCP server instance for testing."""
    return blog_mcp_server.mcp


@pytest.fixture
def assertions():
    """Provide assertions helper."""
    return BlogAssertions()


# ---------------------------------------------------------------------------
# Global state isolation – prevents leakage between tests
# ---------------------------------------------------------------------------

_GLOBAL_NAMES = [
    "_available_repos",
    "_repo_default_branches",
    "_repo_caches",
    "_repo_cache_timestamps",
    "_list_repos_cache",
    "_list_repos_cache_time",
]


@pytest.fixture(autouse=True)
def _isolate_global_state():
    """Save and restore module-level globals so tests cannot leak state."""
    saved = {}
    for name in _GLOBAL_NAMES:
        val = getattr(blog_mcp_server, name)
        saved[name] = copy.deepcopy(val) if val is not None else val

    yield

    for name, val in saved.items():
        setattr(blog_mcp_server, name, val)
