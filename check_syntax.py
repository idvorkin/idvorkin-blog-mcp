#!/usr/bin/env python3
"""
Syntax-only validation that doesn't require dependencies.
"""

import ast
import sys

def check_file_syntax(filename):
    """Check if a Python file has valid syntax."""
    try:
        with open(filename, 'r') as f:
            source = f.read()
        
        # Parse the AST to check syntax
        ast.parse(source, filename=filename)
        print(f"✅ {filename}: Valid syntax")
        return True
    except SyntaxError as e:
        print(f"❌ {filename}: Syntax error at line {e.lineno}: {e.msg}")
        return False
    except Exception as e:
        print(f"❌ {filename}: Error checking syntax: {e}")
        return False

def main():
    """Check syntax of all Python files."""
    files_to_check = [
        'blog_mcp_server.py',
        'test_blog_mcp_e2e.py',
        'run_simple_tests.py'
    ]
    
    print("🔍 Checking Python syntax...\n")
    
    passed = 0
    total = len(files_to_check)
    
    for filename in files_to_check:
        if check_file_syntax(filename):
            passed += 1
    
    print(f"\n📊 Syntax Check Results: {passed}/{total} files have valid syntax")
    
    if passed == total:
        print("🎉 All files have valid syntax!")
        return 0
    else:
        print("💥 Some files have syntax errors!")
        return 1

if __name__ == "__main__":
    sys.exit(main())