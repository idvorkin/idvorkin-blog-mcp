# Claude Code Instructions

## Project Structure

This is a Blog MCP Server built with FastMCP that provides tools for interacting with Igor's blog.

## Configuration

The server supports multi-repository access via environment variables. See `.env.example` for all configuration options.

### Multi-Repository Support

Configure repository access using these environment variables:

- **GITHUB_REPO_OWNER**: GitHub username or organization (default: `idvorkin`)
- **GITHUB_REPOS**: Repository specification
  - Single repo: `"idvorkin.github.io"`
  - Multiple repos: `"repo1,repo2,repo3"` (comma-separated)
  - All repos: `"*"` (wildcard - enables access to all public repos)
- **DEFAULT_REPO**: Default repository when none specified (default: `idvorkin.github.io`)
  - This is the blog repo used for all tools when no `repo` parameter is provided
- **BACKLINKS_PATH**: Path to back-links.json in each repo (default: `back-links.json`)
- **BLOG_URL**: Public blog URL (default: `https://idvork.in`)

### Recommended Configuration

For Igor's setup (blog as default, access to all repos):

```bash
GITHUB_REPO_OWNER=idvorkin
GITHUB_REPOS=*
DEFAULT_REPO=idvorkin.github.io
BLOG_URL=https://idvork.in
```

This configuration:
- Sets `idvorkin.github.io` as the default blog repository
- Enables searching across all repositories under the `idvorkin` account
- All tools default to the blog repo unless explicitly given a different repo parameter

### Using Multi-Repo Features

All tools accept an optional `repo` parameter:
- `blog_search("python", repo="my-other-repo")` - Search in specific repo
- `blog_search("python")` - Defaults to DEFAULT_REPO (idvorkin.github.io)
- `list_repos()` - Shows all available repositories

## FastMCP Architecture

- Uses `@mcp.tool` decorators to automatically expose functions as MCP tools
- FastMCP handles all protocol details, parameter validation, and schema generation
- Tools are simple async/sync Python functions that return strings
- No manual protocol implementation needed

## Important Notes

- Always add `__pycache__/` to .gitignore to prevent Python cache files from being committed
- Never commit Python cache files or temporary build artifacts
- Tools should return strings (FastMCP handles JSON conversion automatically)
- Use type hints for automatic schema generation

## Performance Optimization

- **Use back-links.json**: Instead of fetching individual files via GitHub API (108+ calls), use the pre-built `back-links.json` file at https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/master/back-links.json
- **Single API call**: This file contains all blog metadata (titles, descriptions, URLs, backlinks) needed for all tools
- **Cache the data**: Cache the back-links.json response to avoid repeated network calls
- **Reduces latency**: Eliminates 10-20 second response times caused by multiple GitHub API calls

## JSON Data Structure

The back-links.json file contains rich metadata for each blog post. Key functions now return JSON data:

### Top-Level Structure

The back-links.json file has two main sections:

```json
{
  "redirects": {
    "/fortytwo": "/42",
    "/forty-two": "/42",
    "/7habits": "/7-habits",
    // ... mapping of redirect paths to target paths
  },
  "url_info": {
    "/42": { /* post metadata */ },
    "/about": { /* post metadata */ },
    // ... one entry per blog post path
  }
}
```

**Important**:
- The `redirects` field at the top level contains all URL redirects (e.g., `/fortytwo` -> `/42`)
- The `redirect_url` field inside each `url_info` entry is currently always empty
- When handling redirects, check the top-level `redirects` field first

### Available Data Fields

Each blog post in the `url_info` section includes:

- **title**: Post title
- **url**: Full blog URL (https://idvork.in/...)
- **description**: Post excerpt/description
- **last_modified**: ISO timestamp of last modification
- **doc_size**: Document size in characters
- **markdown_path**: Path to source markdown file (_d/filename.md)
- **file_path**: Path to generated HTML file (_site/filename.html)
- **redirect_url**: Currently always empty (use top-level `redirects` instead)
- **incoming_links**: Array of paths that link to this post
- **outgoing_links**: Array of paths this post links to

### JSON Functions

- **blog_search(query, limit)**: Returns JSON with matching posts
- **recent_blog_posts(limit)**: Returns JSON with most recent posts
- **all_blog_posts()**: Returns JSON with all blog posts

### Example JSON Response

```json
{
  "count": 5,
  "limit": 5,
  "posts": [
    {
      "title": "What I wish I knew at 42",
      "url": "https://idvork.in/42",
      "description": "You survived young kids, marriage, house...",
      "last_modified": "2025-07-20T19:13:52-07:00",
      "doc_size": 20000,
      "markdown_path": "_d/42.md",
      "file_path": "_site/42.html",
      "redirect_url": ""
    }
  ]
}
```

### Using JSON Data

The JSON format enables:
- **Programmatic processing**: Easy to parse and filter data
- **Rich metadata**: Access to links, timestamps, and file paths
- **Structured queries**: Filter by date, size, or link relationships
- **Integration**: Easy to integrate with other tools and systems

## Development Commands

- Install dependencies: `just install`
- Run fast tests: `just fast-test` (syntax validation, used by pre-commit)
- Run all available tests: `just test`
- Run full test suite: `python -m pytest test_blog_mcp_e2e.py -v`
- Run the server locally: `just serve` (STDIO transport)
- Run server with HTTP: `just serve-http [PORT]` (defaults to port 8000)
- List all commands: `just` (default command)

## Deployment

### FastMCP Cloud (Automatic)

- **Live URL**: https://idvorkin-blog-mcp.fastmcp.app/mcp
- **Auto-deployment**: Automatically deploys on push to main branch
- **Authentication**: Requires API key for access

### Manual Deployment Commands

- Deploy to Google Cloud Run: `just deploy PROJECT_ID [REGION]`
- Deploy using container: `just deploy-container PROJECT_ID [REGION]`
- Check deployment status: `just deploy-status PROJECT_ID [REGION]`
- View deployment logs: `just deploy-logs PROJECT_ID [REGION]`

## Testing Strategy

- **Unit Tests (`test_unit.py`)**: Use real GitHub API calls (no mocking) since the API is fast and data is stable
- **E2E Tests (`test_e2e.py`)**: Test against deployed endpoints (local or production)
- **GitHub Dependency**: Both test suites rely on GitHub API being available and the idvorkin/idvorkin.github.io repo existing
- **Simplicity over isolation**: We prefer simple, readable tests that use real data over complex mocked tests

## Chop Conventions Setup

This repo follows [idvorkin/chop-conventions](https://github.com/idvorkin/chop-conventions) for development best practices:

- **Comprehensive .gitignore**: Covers Python, Node.js, multiple IDEs, security patterns, and more
- **Pre-commit hooks**: Automated code formatting and linting with Ruff, Biome, Prettier, and Dasel
- **Justfile**: Standardized command runner for common tasks
- **Chat transcript exclusion**: `.specstory/**` files are ignored
- **Development workflow**: Specifications + Verification approach for AI-assisted coding

## Code Style

- Follow PEP 8 Python style guidelines
- Use async/await for HTTP operations
- Include comprehensive error handling and logging
- Keep tools simple - just decorated functions that return strings
