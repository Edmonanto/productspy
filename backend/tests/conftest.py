

import pytest as _pytest


@_pytest.fixture(autouse=True)
def _clear_winner_caches():
    """The winners router caches picks in memory; tests must not see each other's data."""
    from app.routers import winners as _w
    _w._picks_cache.clear()
    _w._preview_cache.clear()
    yield
