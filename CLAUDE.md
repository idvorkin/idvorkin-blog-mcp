# Claude Code Instructions

## Project Structure
This is a Blog MCP Server that provides tools for interacting with Igor's blog.

## Important Notes
- Always add `__pycache__/` to .gitignore to prevent Python cache files from being committed
- Never commit Python cache files or temporary build artifacts

## Development Commands
- Run tests: `python -m pytest test_blog_mcp_e2e.py -v`
- Install dependencies: `pip install -r requirements.txt`
- Run the server: `python blog_mcp_server.py`

## Code Style
- Follow PEP 8 Python style guidelines
- Use async/await for HTTP operations
- Include comprehensive error handling and logging