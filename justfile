default:
    @just --list

# Fast tests for pre-commit hooks (syntax check only)
fast-test:
    @echo "Running fast tests..."
    uv run python -m py_compile blog_mcp_server.py
    uv run pytest test_unit.py -v --tb=short -q
    @echo "✅ Fast tests passed"

# Run comprehensive test suite
test:
    @echo "Running comprehensive tests..."
    uv run pytest test_unit.py test_multi_repo.py test_e2e.py -v --tb=short -n auto
    @echo "✅ All tests completed"

# Run tests with coverage
test-coverage:
    uv run pytest test_unit.py test_multi_repo.py test_e2e.py -v --cov=blog_mcp_server --cov-report=term-missing -n auto

# Run only unit tests (uses real GitHub API)
test-unit:
    uv run pytest test_unit.py -v --tb=short -n auto

# Run only integration tests (real API calls)
test-integration:
    uv run pytest test_unit.py -v --tb=short

# Run E2E tests against local server (start server first with 'just serve-http')
test-e2e url="http://localhost:8000/mcp":
    @echo "🏠 Running E2E tests against server: {{url}}"
    @echo "   Make sure server is running"
    MCP_SERVER_ENDPOINT="{{url}}" uv run pytest test_e2e.py -v --tb=short -n auto

# Run E2E tests against production server
test-prod:
    @echo "🌐 Running E2E tests against PRODUCTION server..."
    MCP_SERVER_ENDPOINT="https://idvorkin-blog-mcp.fastmcp.app/mcp" uv run pytest test_e2e.py -v --tb=short -n auto

# Run E2E tests against production server (sequential for debugging)
test-prod-sequential:
    @echo "🌐 Running E2E tests against PRODUCTION server (sequential)..."
    MCP_SERVER_ENDPOINT="https://idvorkin-blog-mcp.fastmcp.app/mcp" uv run pytest test_e2e.py -v --tb=short

# Run all tests (unit + E2E) in parallel
test-all:
    @echo "🚀 Running ALL tests in parallel..."
    uv run pytest test_unit.py test_multi_repo.py test_e2e.py -v --tb=short -n auto
    @echo "✅ All tests completed"

# Performance test with timing
test-perf:
    @echo "⏱️ Running performance tests with timing..."
    time uv run pytest test_e2e.py -v --tb=short -n auto --durations=10
    @echo "✅ Performance test completed"

# Install dependencies with UV
install:
    @echo "Setting up UV environment..."
    uv venv
    uv pip install -r requirements.txt
    @echo "✅ Dependencies installed with UV"

# Run the blog MCP server locally (STDIO transport)
serve:
    uv run python blog_mcp_server.py

# Run the blog MCP server with HTTP transport for development
serve-http port="8000":
    @echo "Starting MCP server on HTTP transport at http://localhost:{{port}}"
    @echo "Use MCP_SERVER_ENDPOINT=http://localhost:{{port}}/mcp for tool commands"
    uv run python -c "from blog_mcp_server import mcp; mcp.run(transport='http', host='127.0.0.1', port={{port}})"

# Read a specific blog post by URL (requires server running)
read_blog_post url:
    @echo "📖 Reading blog post: {{url}}"
    @uv run python mcp_cli.py read_blog_post '{"url":"{{url}}"}'

# Search blog posts (requires server running)
blog_search query limit="5":
    @echo "🔍 Searching for: {{query}} (limit: {{limit}})"
    @uv run python mcp_cli.py blog_search '{"query":"{{query}}","limit":{{limit}}}'

# Get recent blog posts (requires server running)
recent_blog_posts limit="5":
    @echo "📰 Getting {{limit}} recent posts..."
    @uv run python mcp_cli.py recent_blog_posts '{"limit":{{limit}}}'

# Get random blog post with content (requires server running)
random_blog:
    @echo "🎲 Getting random blog post..."
    @uv run python mcp_cli.py random_blog '{"include_content":true}'

# Get random blog URL only (requires server running)
random_blog_url:
    @echo "🎲 Getting random blog URL..."
    @uv run python mcp_cli.py random_blog_url

# Get blog info (requires server running)
blog_info:
    @echo "ℹ️ Getting blog info..."
    @uv run python mcp_cli.py blog_info

# Get all blog posts (requires server running)
all_blog_posts:
    @echo "📚 Getting all blog posts..."
    @uv run python mcp_cli.py all_blog_posts

# Generic tool caller for any MCP tool with JSON arguments (requires server running)
call tool args="{}":
    @echo "🔧 Calling tool: {{tool}} with args: {{args}}"
    @uv run python mcp_cli.py {{tool}} '{{args}}'

# Call tool against production server
call-prod tool args="{}":
    @echo "🌐 Calling {{tool}} on PRODUCTION server"
    @MCP_SERVER_ENDPOINT="https://idvorkin-blog-mcp.fastmcp.app/mcp" uv run python mcp_cli.py {{tool}} '{{args}}'

# Call tool against local server (explicit)
call-local tool args="{}":
    @echo "🏠 Calling {{tool}} on LOCAL server"
    @MCP_SERVER_ENDPOINT="http://localhost:8000/mcp" uv run python mcp_cli.py {{tool}} '{{args}}'

# Deploy to Google Cloud Run (requires gcloud CLI setup)
deploy project_id="" region="us-central1":
    #!/usr/bin/env bash
    set -euo pipefail

    if [ -z "{{project_id}}" ]; then
        echo "Error: PROJECT_ID required. Usage: just deploy PROJECT_ID [REGION]"
        exit 1
    fi

    echo "🚀 Deploying MCP server to Google Cloud Run..."
    echo "📦 Project: {{project_id}}"
    echo "🌍 Region: {{region}}"

    # Set project
    gcloud config set project {{project_id}}

    # Create Dockerfile if it doesn't exist
    if [ ! -f Dockerfile ]; then
        echo "📄 Creating Dockerfile..."
        cat > Dockerfile << 'EOF'
    FROM python:3.13-slim
    COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
    COPY . /app
    WORKDIR /app
    ENV PYTHONUNBUFFERED=1
    RUN uv sync
    EXPOSE $PORT
    CMD ["uv", "run", "python", "-c", "import os; from blog_mcp_server import mcp; mcp.run(transport='http', host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))"]
    EOF
    fi

    # Deploy from source
    gcloud run deploy blog-mcp-server \
        --source . \
        --region={{region}} \
        --allow-unauthenticated \
        --port=8080 \
        --memory=1Gi \
        --cpu=1 \
        --min-instances=0 \
        --max-instances=10

    echo "✅ Deployment complete!"
    echo "🌐 Your MCP server is now available at the URL shown above"

# Build and deploy using container image (alternative deployment method)
deploy-container project_id="" region="us-central1":
    #!/usr/bin/env bash
    set -euo pipefail

    if [ -z "{{project_id}}" ]; then
        echo "Error: PROJECT_ID required. Usage: just deploy-container PROJECT_ID [REGION]"
        exit 1
    fi

    echo "🐳 Building and deploying container to Google Cloud Run..."

    # Set project
    gcloud config set project {{project_id}}

    # Create Artifact Registry repository (ignore if exists)
    gcloud artifacts repositories create blog-mcp-servers \
        --repository-format=docker \
        --location={{region}} || true

    # Build and push image
    IMAGE_NAME="{{region}}-docker.pkg.dev/{{project_id}}/blog-mcp-servers/blog-mcp-server:latest"

    gcloud builds submit \
        --region={{region}} \
        --tag $IMAGE_NAME

    # Deploy to Cloud Run
    gcloud run deploy blog-mcp-server \
        --image $IMAGE_NAME \
        --region={{region}} \
        --allow-unauthenticated \
        --port=8080 \
        --memory=1Gi \
        --cpu=1 \
        --min-instances=0 \
        --max-instances=10

    echo "✅ Container deployment complete!"

# Check deployment status
deploy-status project_id="" region="us-central1":
    @echo "📊 Checking deployment status..."
    gcloud run services list --region={{region}} --filter="metadata.name:blog-mcp-server"
    @echo ""
    @echo "📋 Service details:"
    gcloud run services describe blog-mcp-server --region={{region}} --format="value(status.url)"

# View deployment logs
deploy-logs project_id="" region="us-central1":
    gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=blog-mcp-server" \
        --project={{project_id}} \
        --limit=50 \
        --format="table(timestamp,textPayload)"

# Check what files would be ignored by git
check-ignored:
    git status --ignored

# Validate git ignore patterns
validate-gitignore:
    @echo "Checking gitignore patterns..."
    git check-ignore -v .env || echo "✅ .env would be ignored"
    git check-ignore -v __pycache__ || echo "✅ __pycache__ would be ignored"
    git check-ignore -v .DS_Store || echo "✅ .DS_Store would be ignored"