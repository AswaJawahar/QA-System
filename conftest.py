"""Shared pytest configuration.

Having this file in the project root also puts the root on sys.path, so tests can `import app`.

Tests marked `live_llm` call the Gemini API. They are slow, use the daily free-tier quota, and their
output varies between runs, so they are skipped unless RUN_LIVE_LLM_TESTS=1 is set. CI never sets it:
the CI pipeline runs only the deterministic tests.
"""
import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "live_llm: calls the live LLM API (opt in with RUN_LIVE_LLM_TESTS=1)")


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_LIVE_LLM_TESTS") == "1":
        return
    skip_live = pytest.mark.skip(reason="live LLM test; set RUN_LIVE_LLM_TESTS=1 to run")
    for item in items:
        if "live_llm" in item.keywords:
            item.add_marker(skip_live)
