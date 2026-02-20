# list_open_prs MCP Tool

## Purpose

New MCP tool to list open pull requests across repos, with a date filter.

## API

```python
@mcp.tool
async def list_open_prs(
    repo: Optional[str] = None,
    since_days: int = 7,
) -> str:
    """List open pull requests, optionally filtered by repo and recency.

    Parameters:
    - repo: Specific repo name, or None for all configured repos
    - since_days: Only include PRs updated in the last N days (default: 7)
    """
```

## Return format

```json
{
  "count": 3,
  "since_days": 7,
  "pull_requests": [
    {
      "repo": "idvorkin.github.io",
      "number": 42,
      "title": "Fix typo in blog post",
      "author": "dependabot[bot]",
      "state": "open",
      "created_at": "2026-02-18T10:00:00Z",
      "updated_at": "2026-02-19T15:30:00Z",
      "url": "https://github.com/idvorkin/idvorkin.github.io/pull/42"
    }
  ]
}
```

## Implementation

- Use GitHub API: `GET /repos/{owner}/{repo}/pulls?state=open&sort=updated&direction=desc`
- When `repo=None`, iterate all repos from `get_repo_list()`
- Filter by `since_days` using `updated_at` timestamp
- Respect `GITHUB_TOKEN` for auth (required for wildcard repo queries)
- Use existing `httpx.AsyncClient` patterns with semaphore for parallel fetches
- Cap at 100 PRs per repo via `per_page=100`

## Files to modify

- `blog_mcp_server.py` — add `list_open_prs` tool function
- `test_unit.py` — add unit tests (mocked + direct call)
- `test_e2e.py` — add E2E test
- `CLAUDE.md` — add tool to tool list documentation

## Validation

- Empty result returns `{"count": 0, "since_days": 7, "pull_requests": []}`
- Invalid `since_days` (negative/zero) clamped to 1
- Invalid repo returns error message
