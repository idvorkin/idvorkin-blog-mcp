# Blog MCP Server

A FastMCP server that provides tools for interacting with Igor's blog at [idvork.in](https://idvork.in). Built with FastMCP 2.0 for automatic tool registration and protocol handling.

## 🚀 Live Server

**Production URL**: https://idvorkin-blog-and-repo.fastmcp.app/mcp

- Automatically deploys on push to main branch
- Requires API key for authentication
- Powered by FastMCP Cloud hosting

## Architecture

- **FastMCP 2.0**: High-level Python framework that handles all MCP protocol details
- **GitHub Source**: Reads markdown files directly from the `idvorkin/idvorkin.github.io` repository
- **Simple Tools**: Each tool is just a decorated Python function - no manual protocol implementation
- **Type Safety**: Automatic schema generation from Python type hints

### Sequence Diagrams

#### Recent Blog Posts Flow

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant Server as Blog MCP Server
    participant GitHub as GitHub API
    participant BackLinks as back-links.json

    Client->>Server: recent_blog_posts(limit=5)
    Server->>BackLinks: GET /idvorkin.github.io/master/back-links.json
    BackLinks-->>Server: JSON with all blog metadata
    Server->>Server: Sort posts by last_modified
    Server->>Server: Select top N posts
    Server-->>Client: JSON with recent posts<br/>(title, url, description, date)
```

#### Random Blog Post Flow

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant Server as Blog MCP Server
    participant GitHub as GitHub API
    participant BackLinks as back-links.json

    Client->>Server: random_blog(include_content=true)
    Server->>BackLinks: GET /idvorkin.github.io/master/back-links.json
    BackLinks-->>Server: JSON with all blog metadata
    Server->>Server: Select random post
    alt include_content == true
        Server->>GitHub: GET markdown file from markdown_path
        GitHub-->>Server: Markdown content
        Server->>Server: Extract and format content
    end
    Server-->>Client: Blog post with metadata<br/>(and content if requested)
```

#### Read Blog Post Flow

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant Server as Blog MCP Server
    participant GitHub as GitHub API
    participant BackLinks as back-links.json

    Client->>Server: read_blog_post(url="https://idvork.in/42")
    Server->>BackLinks: GET /idvorkin.github.io/master/back-links.json
    BackLinks-->>Server: JSON with all blog metadata
    Server->>Server: Find post by URL
    Server->>GitHub: GET markdown file from markdown_path
    GitHub-->>Server: Markdown content
    Server->>Server: Extract title and content
    Server-->>Client: Blog post with full content
```

## Features

This MCP server provides 9 tools for blog and repository interaction:

1. **list_repos** - List all available repositories with metadata (paginated, sorted by recent changes)
2. **blog_info** - Get information about the blog
3. **random_blog** - Get a random blog post (with optional content)
4. **read_blog_post** - Read a specific blog post by URL, redirect path, or markdown path
5. **random_blog_url** - Get a random blog post URL
6. **blog_search** - Search blog posts by query (returns JSON)
7. **recent_blog_posts** - Get the most recent blog posts (returns JSON)
8. **all_blog_posts** - Get all blog posts (returns JSON)
9. **get_recent_changes** - Get recent commits and changes from the repository

## Installation

### Using UV (Recommended)

```bash
just install
```

Or manually:

```bash
uv venv
uv pip install -r requirements.txt
```

## Running the Server

### Local Server (STDIO Transport)

```bash
just serve
```

### HTTP Server for Development

```bash
just serve-http [PORT]  # defaults to port 8000
```

## Configuration

### MCP Client Configuration

Add this to your MCP client configuration:

```json
{
  "mcpServers": {
    "blog": {
      "command": "uv",
      "args": ["run", "python", "/path/to/blog_mcp_server.py"],
      "env": {
        "GITHUB_TOKEN": "your_token_here"
      }
    }
  }
}
```

### GitHub Authentication (Recommended)

For better performance and to avoid rate limiting, it's highly recommended to use a GitHub Personal Access Token:

#### Why Use a Token?

- **Unauthenticated**: 60 requests/hour
- **Authenticated**: 5,000 requests/hour
- **Required for**: Large repository lists, frequent `list_repos` calls, private repositories

#### How to Get a GitHub Token

1. Visit [GitHub Settings > Personal Access Tokens](https://github.com/settings/tokens)
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a descriptive name (e.g., "Blog MCP Server")
4. Select scopes:
   - `public_repo` - For accessing public repositories
   - `repo` - Only if you need access to private repositories
5. Click "Generate token" and copy it immediately (you won't see it again!)

#### Setting the Token

**Option 1: Environment Variable (Local Development)**

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
just serve
```

**Option 2: .env File (Local Development)**

Create a `.env` file in the project root:

```env
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Option 3: MCP Client Configuration**

See the MCP Client Configuration example above.

**Option 4: FastMCP Cloud Deployment**

In your FastMCP Cloud project settings, add an environment variable:
- **Name**: `GITHUB_TOKEN`
- **Value**: Your token

**Security Note**: Never commit your token to git! The `.env` file is already in `.gitignore`.

## Tools Documentation

### list_repos

List all available repositories with metadata, paginated and sorted by recent changes.

**Parameters:**

- `page` (integer, optional): Page number to return (default: 1)
- `per_page` (integer, optional): Number of repositories per page (default: 20, max: 100)

**Returns:** JSON with paginated repository metadata:
- Repository name
- Description (truncated to 200 characters)
- Last commit date
- Last commit hash
- Pagination info (current page, total pages, has next/prev)

**Example:**
```json
{
  "owner": "idvorkin",
  "default_repo": "idvorkin.github.io",
  "repositories": [
    {
      "name": "idvorkin.github.io",
      "description": "My static blog",
      "last_commit_date": "2025-12-01T05:26:39Z",
      "last_commit_hash": "d8912256906e898f6d43e6e6a33044ea055f7b3b"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_count": 82,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

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

Read a specific blog post by URL, redirect path, or markdown path.

**Parameters:**

- `url` (string, required): The URL, redirect path (e.g., "42"), or markdown path (e.g., "_d/42.md")

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

**Returns:** JSON with matching blog posts including titles, URLs, descriptions, and metadata.

### recent_blog_posts

Get the most recent blog posts.

**Parameters:**

- `limit` (integer, optional): Maximum number of posts (default: 20, max: 100)

**Returns:** JSON with recent blog posts sorted by last modified date.

### all_blog_posts

Get all blog posts from the site.

**Parameters:** None

**Returns:** JSON with all blog posts and their metadata.

## Development

### Running Tests

```bash
# Run all tests (unit + E2E)
just test

# Fast tests for pre-commit hooks
just fast-test

# Unit tests only
just test-unit

# E2E tests against local server
just test-e2e

# E2E tests against production
just test-prod

# Tests with coverage
just test-coverage
```

### Using MCP CLI Tools

```bash
# Get blog info
just blog_info

# Get random blog post
just random_blog

# Search blog posts
just blog_search "python" 10

# Get recent posts
just recent_blog_posts 5

# Read specific post
just read_blog_post "https://idvork.in/42"

# Call any tool with custom args
just call TOOL_NAME '{"arg1": "value1"}'

# Call tool against production server
just call-prod TOOL_NAME '{"arg1": "value1"}'
```

## Deployment

### FastMCP Cloud (Recommended)

**Production URL**: https://idvorkin-blog-and-repo.fastmcp.app/mcp

FastMCP Cloud provides zero-configuration deployment with automatic GitHub integration:

#### Setup Process

1. **Create a Project**
   - Visit [fastmcp.cloud](https://fastmcp.cloud) and sign in with GitHub
   - Create a new project and select your repository
   - Configure:
     - **Name**: Project identifier (generates URL like `your-name.fastmcp.app/mcp`)
     - **Entrypoint**: Python file with server (e.g., `blog_mcp_server.py`)
     - **Authentication**: Toggle to restrict access or allow public access

2. **Automatic Deployment**
   - FastMCP Cloud automatically detects dependencies from `requirements.txt` or `pyproject.toml`
   - Deploys immediately after project creation
   - Monitors your repository for changes
   - **Auto-redeploys** on every push to `main` branch
   - Creates **separate preview URLs** for each pull request

3. **Connect to Your Server**
   - Server is immediately accessible at your assigned URL
   - Built-in connection options for Claude, Cursor, and other MCP clients
   - Free during beta period

**Dashboard**: [FastMCP Cloud Dashboard](https://fastmcp.cloud/idvorkin/servers?type=all&search=&selected=idvorkin-blog-mcp)

For more details, see the [FastMCP Cloud Documentation](https://gofastmcp.com/deployment/fastmcp-cloud).

### Google Cloud Run (Alternative)

```bash
# Deploy from source
just deploy PROJECT_ID [REGION]

# Deploy using container
just deploy-container PROJECT_ID [REGION]

# Check deployment status
just deploy-status PROJECT_ID [REGION]

# View deployment logs
just deploy-logs PROJECT_ID [REGION]
```

## Technical Details

- Built with the Model Context Protocol (MCP) framework
- Uses `httpx` for HTTP requests with proper async support
- Implements content extraction from blog posts using regex patterns
- Supports both stdio and HTTP transport modes
- Includes comprehensive error handling and logging

## Performance Optimization

- **Optimized Implementation**: Uses cached `back-links.json` file
  - Single API call to: https://raw.githubusercontent.com/idvorkin/idvorkin.github.io/master/back-links.json
  - Contains all blog metadata (titles, descriptions, URLs, backlinks)
  - 5-minute cache duration for optimal performance
  - Sub-second response times for most operations

## License

MIT License - see LICENSE file for details.
