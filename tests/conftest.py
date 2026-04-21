"""Shared pytest fixtures for the Rosetta test suite."""
import os
import sys
import types as _types
from unittest.mock import MagicMock, patch

import pytest
import swisseph as swe


# ---------------------------------------------------------------------------
# DB stub — installed before any src.core imports occur.
#
# If PostgreSQL credentials are not configured (typical in a local dev
# environment without Supabase), we pre-install a fake src.db.db_access
# module whose load_static_from_db() returns an empty StaticLookup.
# The _init_static_db() setattr loop still copies all UPPERCASE constants
# from src.core.constants onto the instance, so GLYPHS, SIGNS, ASPECTS etc.
# are correctly available via static_db.  DB-populated dicts (signs, objects,
# aspects, sabian_symbols, …) will be empty — tests that actually exercise
# those fields will fail, which is expected without a live database.
# ---------------------------------------------------------------------------
def pytest_configure(config):
    """Install a no-op DB stub when PostgreSQL credentials are absent."""
    if os.environ.get("PGUSER") and os.environ.get("PGDATABASE"):
        return  # Real DB configured — let normal initialisation run

    # Provide dummy values so _init_static_db() passes the env-var check
    os.environ.setdefault("PGUSER", "_pytest_no_db_")
    os.environ.setdefault("PGDATABASE", "_pytest_no_db_")

    # Pre-install a fake src.db.db_access in sys.modules so that when
    # static_models.py imports it and calls load_static_from_db(), the
    # stub is invoked rather than a real psycopg2 connection attempt.
    _fake_db_access = _types.ModuleType("src.db.db_access")
    _fake_db_access.__spec__ = None
    _fake_db_access.CONN_PARAMS = {}
    _fake_db_access.is_db_configured = lambda: False

    def _stub_load_static_from_db():
        """Return an empty StaticLookup for test environments without a DB."""
        # static_models is partially constructed at this point (all dataclasses
        # are defined, but static_db has not yet been assigned).
        from src.core.static_models import StaticLookup  # noqa: PLC0415
        return StaticLookup()

    _fake_db_access.load_static_from_db = _stub_load_static_from_db
    sys.modules.setdefault("src.db.db_access", _fake_db_access)


# ---------------------------------------------------------------------------
# Ephemeris setup — session-scoped, autouse so every test gets it for free.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def ephe_path():
    """Point pyswisseph at the local ephemeris directory once per session."""
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ephe"))
    path = path.replace("\\", "/")
    os.environ["SE_EPHE_PATH"] = path
    swe.set_ephe_path(path)
    return path


# ---------------------------------------------------------------------------
# Reusable chart — session-scoped because calculate_chart is expensive.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def sample_chart(ephe_path):
    """Return an AstrologicalChart for a known date/location.

    Uses 1990-06-15 14:30 EST, New York City.  Session-scoped —
    do NOT mutate the returned object.
    """
    from src.core.calc_v2 import calculate_chart

    _df, _asp, _plot, chart = calculate_chart(
        year=1990, month=6, day=15, hour=14, minute=30,
        tz_offset=-5, lat=40.7128, lon=-74.0060,
        tz_name="America/New_York",
        include_aspects=True,
        display_name="Sample",
    )
    return chart


# ---------------------------------------------------------------------------
# static_db — convenience alias so tests can use it as a fixture param.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def static_db():
    """Return the singleton StaticDB lookup tables."""
    from src.core.models_v2 import static_db as _sdb
    return _sdb


# ---------------------------------------------------------------------------
# Render result — session-scoped (expensive matplotlib call).
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def render_result(sample_chart):
    """Return a RenderResult from render_chart(sample_chart).

    draw_center_earth is patched out because it reads NiceGUI state.
    Session-scoped — do NOT mutate the returned object.
    """
    with patch("src.rendering.drawing_v2.draw_center_earth"):
        from src.rendering.drawing_v2 import render_chart
        return render_chart(sample_chart)


# ---------------------------------------------------------------------------
# Mock Supabase client — function-scoped so each test gets a fresh mock.
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_supabase_client():
    """Return a pre-wired MagicMock mimicking a Supabase client.

    Chains .table().upsert/select/delete/insert...execute() work out of the box.
    Callers should set ``mock_client.table().select().eq().execute.return_value``
    etc. to customise per-test.
    """
    client = MagicMock(name="SupabaseClient")
    # Default: every chained method returns the same builder so chains keep working
    builder = client.table.return_value
    for method in ("upsert", "select", "delete", "insert", "update",
                    "eq", "neq", "order", "limit"):
        getattr(builder, method).return_value = builder
    # Default execute returns empty data
    builder.execute.return_value = MagicMock(data=[])
    return client


# ---------------------------------------------------------------------------
# Auto-clear profile caches between DB tests.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clear_supabase_caches():
    """Clear supabase_profiles TTL caches before and after each test."""
    try:
        from src.db.supabase_profiles import _clear_profile_caches
        _clear_profile_caches()
    except ImportError:
        pass
    yield
    try:
        from src.db.supabase_profiles import _clear_profile_caches
        _clear_profile_caches()
    except ImportError:
        pass
