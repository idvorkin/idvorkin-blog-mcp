# Test Modernization for FastMCP 3.0

## Problem

The test suite has gaps and uses outdated FastMCP 2.x patterns:
- `test_multi_repo.py` (15 tests) not included in any `just` command
- `test_server_configuration` uses weak `callable()` check instead of verifying MCP registration
- Tests use `result.content[0].text` instead of FastMCP 3.0's `result.data`
- No way to run tests offline (all tests hit GitHub API)
- No direct function call tests (a key FastMCP 3.0 capability)

## Changes

### 1. Add test_multi_repo.py to justfile

Update `just test`, `just test-all`, `just test-coverage` to include `test_multi_repo.py`.

### 2. Fix registration test in test_unit.py

Replace:
```python
tool = getattr(blog_mcp_server, tool_name)
assert callable(tool)
```

With:
```python
async with MCPTestClient(mcp_server) as client:
    tools = await client.list_tools()
    tool_names = {t.name for t in tools}
    for tool_name in expected_tools:
        assert tool_name in tool_names
```

### 3. Modernize test_utils.py MCPTestClient

Update `call_tool()` to use `result.data` when the result is structured, fall back to `result.content[0].text` for plain string results. This is backwards compatible.

### 4. Add direct function call unit tests

FastMCP 3.0 decorators return the original function. Add pure sync tests:

```python
def test_blog_info_direct():
    result = blog_mcp_server.blog_info()
    assert "idvork.in" in result

async def test_blog_search_direct_empty():
    result = await blog_mcp_server.blog_search("", 5)
    assert "error" in json.loads(result)
```

### 5. Add pytest markers for network tests

Add `conftest.py` with a `network` marker. Tag tests that hit GitHub API. Enable running `pytest -m "not network"` for fast offline iteration.

## Files to modify

- `justfile` — add test_multi_repo.py to test commands
- `test_utils.py` — modernize MCPTestClient.call_tool()
- `test_unit.py` — fix registration test, add direct call tests, add markers
- `conftest.py` (new) — define `network` marker
- `pyproject.toml` — register `network` marker

## Not in scope

- CI/CD (GitHub Actions)
- inline-snapshot
- Reconciling CLAUDE.md "no mocking" claim with actual mocking usage
