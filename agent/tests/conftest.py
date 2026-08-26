"""`get_settings()` is `@lru_cache`d — correct for a real single CLI process,
but it means later tests in the same pytest process would otherwise see a
stale, cached `Settings` object from an earlier test's environment. Clear it
before every test so each one observes its own env vars.
"""

import pytest

from datasentinel_agent.config.settings import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
