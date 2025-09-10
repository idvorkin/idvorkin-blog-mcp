#!/usr/bin/env python3
"""
Simple test runner that works without pytest for basic validation.
Tests syntax, imports, and basic functionality.
"""

import asyncio
import sys
import traceback
from unittest.mock import AsyncMock, patch

def run_test(test_name, test_func):
    """Run a single test and report results."""
    try:
        if asyncio.iscoroutinefunction(test_func):
            result = asyncio.run(test_func())
        else:
            result = test_func()
        
        print(f"✅ {test_name}: PASSED")
        return True
    except Exception as e:
        print(f"❌ {test_name}: FAILED")
        print(f"   Error: {str(e)}")
        print(f"   {traceback.format_exc()}")
        return False

def test_imports():
    """Test that all modules can be imported."""
    try:
        import blog_mcp_server
        from blog_mcp_server import (
            blog_info,
            random_blog,
            read_blog_post,
            random_blog_url,
            blog_search,
            mcp
        )
        return True
    except ImportError as e:
        raise Exception(f"Import error: {e}")

def test_blog_info():
    """Test blog_info function."""
    from blog_mcp_server import blog_info
    result = blog_info()
    assert "Igor's Blog" in result
    assert "idvork.in" in result
    return True

async def test_basic_functionality():
    """Test basic functionality with mocks."""
    from blog_mcp_server import get_blog_files, parse_markdown_content
    
    # Mock GitHub API response
    mock_response = '[{"name": "test.md", "type": "file", "download_url": "https://example.com/test.md"}]'
    
    with patch('blog_mcp_server.fetch_url', return_value=mock_response):
        files = await get_blog_files()
        assert len(files) > 0
        assert 'html_url' in files[0]
    
    # Test markdown parsing
    file_info = {
        'name': 'test.md',
        'download_url': 'https://example.com/test.md',
        'html_url': 'https://idvork.in/test'
    }
    mock_markdown = "# Test Title\n\nTest content"
    
    with patch('blog_mcp_server.fetch_url', return_value=mock_markdown):
        result = await parse_markdown_content(file_info)
        assert result['title'] == 'Test Title'
        assert 'Test content' in result['content']
    
    return True

def main():
    """Run all tests."""
    print("🧪 Running simple validation tests...\n")
    
    tests = [
        ("Module imports", test_imports),
        ("Blog info function", test_blog_info),
        ("Basic functionality", test_basic_functionality),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        if run_test(test_name, test_func):
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())