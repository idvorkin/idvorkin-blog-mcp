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

# Run the blog MCP server locally (STDIO transport)
serve:
    uv run python blog_mcp_server.py

# Run the blog MCP server with HTTP transport for development
serve-http port="8000":
    @echo "Starting MCP server on HTTP transport at http://localhost:{{port}}"
    uv run python -c "from blog_mcp_server import mcp; mcp.run(transport='http', host='127.0.0.1', port={{port}})"

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