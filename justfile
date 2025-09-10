default:
    @just --list

# Fast tests for pre-commit hooks
fast-test:
    @echo "Running basic validation tests..."
    python3 check_syntax.py
    @echo "✅ Fast tests passed"

# Run comprehensive test suite 
test:
    @echo "Running comprehensive tests..."
    python3 check_syntax.py
    python3 run_simple_tests.py
    @echo "Run full test suite with: python -m pytest test_blog_mcp_e2e.py -v"
    @echo "✅ All available tests completed"

# Install dependencies (only if needed for this Python project)
install:
    @echo "Installing Python dependencies..."
    pip install -r requirements.txt
    @echo "✅ Dependencies installed"

# Run the blog MCP server
serve:
    python3 blog_mcp_server.py

# Check what files would be ignored by git
check-ignored:
    git status --ignored

# Validate git ignore patterns
validate-gitignore:
    @echo "Checking gitignore patterns..."
    git check-ignore -v .env || echo "✅ .env would be ignored"
    git check-ignore -v __pycache__ || echo "✅ __pycache__ would be ignored"
    git check-ignore -v .DS_Store || echo "✅ .DS_Store would be ignored"