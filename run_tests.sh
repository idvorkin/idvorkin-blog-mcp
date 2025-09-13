#!/bin/bash

# Blog MCP Server Test Runner
# Runs the comprehensive end-to-end test suite

set -e  # Exit on any error

echo "🧪 Blog MCP Server Test Suite"
echo "============================="

# Check if we're in the right directory
if [[ ! -f "blog_mcp_server.py" ]]; then
    echo "❌ Error: blog_mcp_server.py not found. Please run this script from the mcp-blog-server directory."
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed or not in PATH"
    exit 1
fi

# Check if pip is available
if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
    echo "❌ Error: pip is not installed or not in PATH"
    exit 1
fi

echo "🔧 Setting up test environment..."

# Install dependencies if requirements.txt exists
if [[ -f "requirements.txt" ]]; then
    echo "📦 Installing dependencies from requirements.txt..."
    python3 -m pip install -r requirements.txt --quiet
else
    echo "📦 Installing core dependencies..."
    python3 -m pip install pytest pytest-asyncio pytest-httpx mcp httpx pydantic --quiet
fi

echo "✅ Dependencies installed"

# Run code quality checks if tools are available
echo "🔍 Running code quality checks..."

if command -v ruff &> /dev/null; then
    echo "   Running ruff linting..."
    ruff check blog_mcp_server.py || echo "   ⚠️  Ruff found some issues"
else
    echo "   ⚠️  ruff not available, skipping linting"
fi

if command -v black &> /dev/null; then
    echo "   Checking code formatting with black..."
    black --check blog_mcp_server.py --quiet || echo "   ⚠️  Code formatting issues found"
else
    echo "   ⚠️  black not available, skipping formatting check"
fi

if command -v mypy &> /dev/null; then
    echo "   Running type checking with mypy..."
    mypy blog_mcp_server.py --ignore-missing-imports --no-strict-optional || echo "   ⚠️  Type checking issues found"
else
    echo "   ⚠️  mypy not available, skipping type checking"
fi

echo "🧪 Running tests..."

# Run the test suite
python3 -m pytest test_blog_mcp_e2e.py -v --tb=short --asyncio-mode=auto

TEST_EXIT_CODE=$?

echo ""
if [[ $TEST_EXIT_CODE -eq 0 ]]; then
    echo "✅ All tests passed! The Blog MCP Server is working correctly."
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Configure your MCP client with the server"
    echo "   2. Run: python3 blog_mcp_server.py"
    echo "   3. Test the tools in your MCP client"
else
    echo "❌ Some tests failed. Please check the output above for details."
    echo ""
    echo "🔧 Troubleshooting:"
    echo "   1. Ensure all dependencies are installed"
    echo "   2. Check internet connectivity for integration tests"
    echo "   3. Review the error messages above"
fi

exit $TEST_EXIT_CODE