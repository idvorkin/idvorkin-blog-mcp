# Multi-Repository Setup Guide

This guide explains how to deploy and configure the Blog MCP Server to work with multiple repositories under the `idvorkin` GitHub organization.

## Overview

The Blog MCP Server now supports configuration via environment variables, allowing you to:
- Deploy separate instances for different repositories
- Use the same codebase across multiple repos
- Maintain independent configurations for each deployment

## Architecture Decision

**Chosen Approach**: Multiple Independent Deployments

Each repository gets its own MCP server instance with isolated configuration:
- ✅ Clear separation of concerns
- ✅ Independent scaling and monitoring
- ✅ Simple caching (no cross-repo cache conflicts)
- ✅ Easy to understand and maintain

**Alternative (Not Implemented)**: Single server with repo parameter
- ❌ Complex caching strategy
- ❌ Mixed concerns in single deployment
- ❌ More complex API surface

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_REPO_OWNER` | No | `idvorkin` | GitHub organization/user name |
| `GITHUB_REPO_NAME` | No | `idvorkin.github.io` | Repository name |
| `GITHUB_REPO_BRANCH` | No | `master` | Branch to read from |
| `BLOG_URL` | No | `https://idvork.in` | Base URL for posts |
| `BACKLINKS_PATH` | No | `back-links.json` | Metadata file path |

## Repository Requirements

### Minimum Requirements

To work with the MCP server, a repository needs:
1. Markdown files in standard directories (`_d/`, `_posts/`, or `td/`)
2. Publicly accessible on GitHub

### Recommended: back-links.json

For optimal performance and full feature support, include a `back-links.json` file:

```json
{
  "redirects": {
    "/short": "/full-path"
  },
  "url_info": {
    "/path": {
      "title": "Post Title",
      "description": "Post description",
      "markdown_path": "_d/file.md",
      "last_modified": "2025-01-01T00:00:00Z",
      "doc_size": 5000
    }
  }
}
```

**Without back-links.json:**
- ⚠️ Search functionality limited (requires API calls for each file)
- ⚠️ Recent posts may not sort correctly
- ✅ Basic read/random post operations still work

## Deployment Scenarios

### Scenario 1: Blog Repository (Current)

**Repository**: `idvorkin/idvorkin.github.io`
**Environment**: Default (no variables needed)

```bash
# No configuration needed - uses defaults
```

**Features**:
- Full back-links.json support
- All tools fully functional
- 5-minute cache duration

### Scenario 2: Additional Repository (e.g., Tech Lead Notes)

**Repository**: `idvorkin/techlead`
**Deployment**: New FastMCP Cloud instance

**Configuration**:
```bash
GITHUB_REPO_OWNER=idvorkin
GITHUB_REPO_NAME=techlead
GITHUB_REPO_BRANCH=main
BLOG_URL=https://techlead.idvork.in
BACKLINKS_PATH=metadata.json
```

**Deployment Steps**:
1. Create new FastMCP Cloud project: `idvorkin-techlead-mcp`
2. Configure environment variables in project settings
3. Deploy from main branch
4. Test with MCP client

### Scenario 3: Private/Personal Notes

**Repository**: `idvorkin/notes` (private)
**Deployment**: Self-hosted or Google Cloud Run

**Configuration**:
```bash
GITHUB_REPO_OWNER=idvorkin
GITHUB_REPO_NAME=notes
GITHUB_REPO_BRANCH=main
BLOG_URL=https://notes.idvork.in
# Add GitHub token if private repo
GITHUB_TOKEN=ghp_xxxxx
```

**Note**: Private repos require GitHub personal access token with repo read permissions.

## Testing Multi-Repo Setup

### Local Testing

1. **Start server with custom config**:
   ```bash
   export GITHUB_REPO_OWNER=idvorkin
   export GITHUB_REPO_NAME=techlead
   export BLOG_URL=https://example.com
   just serve-http 8000
   ```

2. **Test blog_info**:
   ```bash
   just call-local blog_info '{}'
   ```

3. **Verify configuration**:
   Check that the output shows your configured repo and URLs

### Production Testing

```bash
# Test against deployed instance
MCP_SERVER_ENDPOINT=https://your-instance.fastmcp.app/mcp \
  just call-prod blog_info '{}'
```

## Feature Availability Matrix

| Feature | With back-links.json | Without back-links.json |
|---------|---------------------|------------------------|
| `blog_info` | ✅ Full info | ✅ Basic info |
| `read_blog_post` | ✅ Fast (cached) | ✅ Works (API call) |
| `random_blog` | ✅ Fast | ⚠️ Slower (needs listing) |
| `blog_search` | ✅ Fast search | ⚠️ Very slow/limited |
| `recent_blog_posts` | ✅ Accurate sorting | ❌ No sort data |
| `all_blog_posts` | ✅ Full metadata | ⚠️ Basic list only |
| `get_recent_changes` | ✅ Works | ✅ Works |

## Migration Guide

### Migrating Existing Repo to MCP

1. **Option A: Add back-links.json** (Recommended)
   - Create script to generate back-links.json from your repo
   - Include: titles, descriptions, paths, timestamps
   - Regenerate on content changes (CI/CD hook)

2. **Option B: Use without back-links.json**
   - Deploy with default configuration
   - Accept limited search/recent functionality
   - Consider adding back-links.json later

### Example: Generating back-links.json

```python
import json
import os
from pathlib import Path

def generate_backlinks(repo_path: str):
    backlinks = {"redirects": {}, "url_info": {}}

    for md_file in Path(repo_path).glob("_d/*.md"):
        # Extract metadata from markdown
        title = extract_title(md_file)
        description = extract_description(md_file)

        url = f"/{md_file.stem}"
        backlinks["url_info"][url] = {
            "title": title,
            "description": description,
            "markdown_path": str(md_file.relative_to(repo_path)),
            "last_modified": get_file_mtime(md_file)
        }

    with open(f"{repo_path}/back-links.json", "w") as f:
        json.dump(backlinks, f, indent=2)
```

## Best Practices

### 1. Separate Deployments for Production

- Don't share a single instance across repos
- Each repo gets dedicated resources
- Easier to monitor and debug

### 2. Cache Configuration

- Default 5-minute cache works for most cases
- Adjust `CACHE_DURATION` if your repo updates more/less frequently
- Consider cache invalidation strategy

### 3. Monitoring

Monitor these metrics per deployment:
- Response times (should be <100ms with cache)
- Cache hit rate (should be >90%)
- GitHub API rate limits
- Error rates

### 4. Documentation

Document for each repo:
- Which MCP instance serves it
- Environment variable configuration
- Whether back-links.json exists
- Update frequency and cache settings

## Troubleshooting

### Issue: "No blog posts found"

**Causes**:
- back-links.json missing and repo structure different
- Wrong `BACKLINKS_PATH` configured
- Repository not publicly accessible

**Solutions**:
1. Verify repo is public or token configured
2. Check markdown files in `_d/`, `_posts/`, or `td/` directories
3. Generate back-links.json for the repo

### Issue: Search returns no results

**Causes**:
- back-links.json missing
- Search query doesn't match titles/descriptions
- Metadata file has wrong structure

**Solutions**:
1. Add back-links.json with proper structure
2. Check query is in title/description fields
3. Validate JSON structure matches expected format

### Issue: Recent posts not sorted

**Causes**:
- Missing `last_modified` field in back-links.json
- Incorrect timestamp format

**Solutions**:
1. Add `last_modified` with ISO 8601 format
2. Use: `YYYY-MM-DDTHH:MM:SS±HH:MM`

## Example Deployments

### Example 1: Blog + Tech Lead Notes

```bash
# Blog instance (default)
# URL: https://idvorkin-blog-mcp.fastmcp.app/mcp
# Config: defaults

# Tech Lead instance
# URL: https://idvorkin-techlead-mcp.fastmcp.app/mcp
GITHUB_REPO_NAME=techlead
BLOG_URL=https://techlead.idvork.in
```

### Example 2: Multi-Branch Setup

```bash
# Production blog
GITHUB_REPO_BRANCH=master
BLOG_URL=https://idvork.in

# Staging blog
GITHUB_REPO_BRANCH=staging
BLOG_URL=https://staging.idvork.in
```

## Future Enhancements

Potential improvements for multi-repo support:

1. **Automatic back-links.json generation**
   - Server could generate metadata on first run
   - Cache and update periodically

2. **Webhook integration**
   - Invalidate cache on repo push
   - Real-time content updates

3. **Cross-repo search**
   - Federated search across multiple instances
   - Requires coordination layer

4. **Repository discovery**
   - Auto-detect repos under organization
   - Dynamic instance creation

## Support

For questions or issues:
- Open issue: https://github.com/idvorkin/idvorkin-blog-mcp/issues
- Review documentation: README.md and CLAUDE.md
