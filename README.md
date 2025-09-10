# Blog MCP Server

A Model Context Protocol (MCP) server that provides tools for interacting with Igor's blog at [idvork.in](https://idvork.in).

## Features

This MCP server provides 5 tools for blog interaction:

1. **blog_info** - Get information about the blog
2. **random_blog** - Get a random blog post (with optional content)
3. **read_blog_post** - Read a specific blog post by URL
4. **random_blog_url** - Get a random blog post URL
5. **blog_search** - Search blog posts by query

## Installation

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python blog_mcp_server.py
```

### Using uv

```bash
uv pip install -r requirements.txt
uv run blog_mcp_server.py
```

## Configuration

### MCP Client Configuration

Add this to your MCP client configuration:

```json
{
  "mcpServers": {
    "blog": {
      "command": "python",
      "args": ["/path/to/blog_mcp_server.py"],
      "env": {}
    }
  }
}
```

### Environment Variables

Copy `.env.example` to `.env` and customize:

- `BLOG_BASE_URL`: Base URL for the blog (default: https://idvork.in)
- `REQUEST_TIMEOUT`: Request timeout in seconds (default: 30)
- `MAX_POSTS`: Maximum number of posts to fetch (default: 50)
- `LOG_LEVEL`: Logging level (default: INFO)

## Tools Documentation

### blog_info

Get information about Igor's blog.

**Parameters:** None

**Returns:** Blog information including URL, description, and available tools.

### random_blog

Get a random blog post from the site.

**Parameters:**
- `include_content` (boolean, optional): Whether to include full content (default: true)

**Returns:** Random blog post with title, URL, date, and content (if requested).

### read_blog_post

Read a specific blog post by URL.

**Parameters:**
- `url` (string, required): The URL of the blog post to read

**Returns:** Blog post content with title, URL, date, and full content.

### random_blog_url

Get a random blog post URL.

**Parameters:** None

**Returns:** A random blog post URL as plain text.

### blog_search

Search blog posts by title or content.

**Parameters:**
- `query` (string, required): Search query to find relevant posts
- `limit` (integer, optional): Maximum number of results (default: 5, max: 20)

**Returns:** List of matching blog posts with titles, URLs, and excerpts.

## Development

### Running Tests

```bash
python -m pytest test_blog_mcp_e2e.py -v
```

Or use the test script:

```bash
./run_tests.sh
```

### Code Quality

Format code:
```bash
black blog_mcp_server.py
isort blog_mcp_server.py
```

Type checking:
```bash
mypy blog_mcp_server.py
```

Linting:
```bash
ruff blog_mcp_server.py
```

## Cloud Deployment

This server supports deployment to FastMCP 2.0 cloud hosting. Configure your FastMCP API key in the environment variables.

## Technical Details

- Built with the Model Context Protocol (MCP) framework
- Uses `httpx` for HTTP requests with proper async support
- Implements content extraction from blog posts using regex patterns
- Supports both stdio and HTTP transport modes
- Includes comprehensive error handling and logging

## License

MIT License - see LICENSE file for details.