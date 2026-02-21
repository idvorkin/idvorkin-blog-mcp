# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Blog MCP Server built with FastMCP that provides tools for interacting with Igor's blog at idvork.in. Single-file server (`blog_mcp_server.py`) that exposes 10 MCP tools for reading, searching, and browsing blog posts across GitHub repositories.

## Development Commands

```bash
just install              # Install dependencies with UV
just fast-test            # Syntax check + unit tests (used by pre-commit)
just test                 # Full test suite (unit + multi-repo + e2e) with parallel execution
just test-unit            # Unit tests only (mix of mocked and real API calls)
just serve                # Run server locally (STDIO transport)
just serve-http [PORT]    # Run server with HTTP transport (default: 8000)
```

Run a single test:
```bash
uv run pytest test_unit.py::TestBlogMCPServer::test_blog_info_tool -v
```

Run tests excluding network calls (for offline development):
```bash
uv run pytest test_unit.py -v -m "not network"
```

E2E tests require a running server:
```bash
just serve-http           # Terminal 1
just test-e2e             # Terminal 2 (defaults to localhost:8000)
just test-prod            # Or test against production
```

## Architecture

**Single-file server**: All MCP tools live in `blog_mcp_server.py`. Each tool is a decorated function (`@mcp.tool`) that FastMCP auto-exposes with schema generation from type hints.

**Data source**: Tools read from a pre-built `back-links.json` file fetched from GitHub raw content (not the GitHub API). This file contains all blog metadata (titles, descriptions, URLs, backlinks, redirects). Cached in-memory with 5-minute TTL.

**Key architectural decisions**:
- `back-links.json` provides all blog metadata in a single HTTP call instead of 100+ GitHub API calls
- The top-level `redirects` field in back-links.json handles URL redirects (the per-entry `redirect_url` field is always empty)
- Blog posts come from three directories: `_d/`, `_posts/`, `td/`
- All tools accept an optional `repo` parameter for multi-repo support; defaults to `DEFAULT_REPO` (idvorkin.github.io)
- Module-level globals (`_repo_caches`, `_repo_default_branches`, etc.) manage per-repo caching

**File layout**:
- `blog_mcp_server.py` — Server and all tool implementations
- `test_unit.py` — Unit tests (mocked + real GitHub API calls, marked with `@pytest.mark.network`)
- `test_multi_repo.py` — Multi-repo and branch detection tests
- `test_e2e.py` — E2E tests against live server endpoints
- `test_utils.py` — `MCPTestClient` wrapper and `BlogAssertions` helpers shared across test files
- `mcp_cli.py` — CLI for calling tools against local/production servers
- `conftest.py` — Registers the `network` pytest marker

## Testing Conventions

- Tests use real GitHub API calls where practical; only mock when testing specific scenarios or avoiding rate limits
- Tests making network calls must be marked `@pytest.mark.network`
- Use `MCPTestClient` (from `test_utils.py`) as async context manager to call tools in tests
- `asyncio_mode = "auto"` in pyproject.toml — async tests run without explicit decorators
- pytest-xdist (`-n auto`) used for parallel test execution

## Configuration

Environment variables (with defaults): `GITHUB_REPO_OWNER` (idvorkin), `GITHUB_REPOS` (* for all), `DEFAULT_REPO` (idvorkin.github.io), `BLOG_URL` (https://idvork.in), `BACKLINKS_PATH` (back-links.json), `GITHUB_TOKEN` (optional, increases rate limit from 60/hr to 5000/hr).

## Pre-commit & Code Style

Pre-commit hooks run Ruff (lint+format), Biome, Prettier (markdown/HTML), and Dasel (YAML/JSON validation). Line length is 100 chars. Use `uv run` prefix for all Python commands.

## Deployment

- **FastMCP Cloud**: Auto-deploys on push to main. Live at https://idvorkin-blog-and-repo.fastmcp.app/mcp
- **Google Cloud Run**: `just deploy PROJECT_ID [REGION]`
