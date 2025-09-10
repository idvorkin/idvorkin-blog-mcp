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
- Install dependencies: `just install` or `pip install -r requirements.txt` 
- Run fast tests: `just fast-test` (syntax validation, used by pre-commit)
- Run all available tests: `just test` 
- Run full test suite: `python -m pytest test_blog_mcp_e2e.py -v`
- Run the server: `just serve` or `python blog_mcp_server.py`
- List all commands: `just` (default command)

## Testing Strategy
- **Unit Tests**: Mock GitHub API responses for isolated testing
- **E2E Tests**: Can rely on GitHub API being available (idvorkin/idvorkin.github.io repo)
- **GitHub Dependency**: Tests assume GitHub API is accessible and the blog repository exists
- **Network Tests**: Some tests verify actual GitHub API integration for real-world validation

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