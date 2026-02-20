#!/usr/bin/env python3
"""
pytest configuration and shared fixtures.

Defines custom markers used across the test suite.
"""

import pytest


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "network: marks tests that make real network calls to the GitHub API "
        "(deselect with '-m \"not network\"' for offline runs)"
    )
