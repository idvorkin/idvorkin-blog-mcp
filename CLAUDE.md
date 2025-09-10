# Claude Code Instructions

## Project Structure
This is a Blog MCP Server built with FastMCP that provides tools for interacting with Igor's blog.

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

## Development Commands
- Run tests: `python -m pytest test_blog_mcp_e2e.py -v`
- Install dependencies: `pip install -r requirements.txt` 
- Run the server: `python blog_mcp_server.py`

## Code Style
- Follow PEP 8 Python style guidelines
- Use async/await for HTTP operations
- Include comprehensive error handling and logging
- Keep tools simple - just decorated functions that return strings