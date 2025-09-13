default:
    @just --list

# Fast tests for pre-commit hooks (syntax check only)
fast-test:
    @echo "Running fast tests..."
    uv run python -m py_compile blog_mcp_server.py
    uv run pytest test_blog_mcp_e2e.py -v -k "not test_real_" --tb=short -q
    @echo "✅ Fast tests passed"

# Run comprehensive test suite
test:
    @echo "Running comprehensive tests..."
    uv run pytest test_blog_mcp_e2e.py -v --tb=short
    @echo "✅ All tests completed"

# Run tests with coverage
test-coverage:
    uv run pytest test_blog_mcp_e2e.py -v --cov=blog_mcp_server --cov-report=term-missing

# Run only unit tests (mocked)
test-unit:
    uv run pytest test_blog_mcp_e2e.py -v -k "not test_real_" --tb=short

# Run only integration tests (real API calls)
test-integration:
    uv run pytest test_blog_mcp_e2e.py -v -k "test_real_" --tb=short

# Install dependencies with UV
install:
    @echo "Setting up UV environment..."
    uv venv
    uv pip install -r requirements.txt
    @echo "✅ Dependencies installed with UV"

# Run the blog MCP server
serve:
    uv run python blog_mcp_server.py

# Check what files would be ignored by git
check-ignored:
    git status --ignored

# Validate git ignore patterns
validate-gitignore:
    @echo "Checking gitignore patterns..."
    git check-ignore -v .env || echo "✅ .env would be ignored"
    git check-ignore -v __pycache__ || echo "✅ __pycache__ would be ignored"
    git check-ignore -v .DS_Store || echo "✅ .DS_Store would be ignored"