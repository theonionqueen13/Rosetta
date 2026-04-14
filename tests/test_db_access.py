"""Tests for src.db.db_access — DB access with mocked connection."""
from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest


MODULE = "src.db.db_access"


# ---------------------------------------------------------------------------
# is_db_configured
# ---------------------------------------------------------------------------
class TestIsDbConfigured:
    def test_true_when_configured(self):
        with patch(f"{MODULE}.CONN_PARAMS", {"user": "admin", "dbname": "rosetta", "host": "localhost", "port": 5432, "password": "x"}):
            from src.db.db_access import is_db_configured
            assert is_db_configured() is True

    def test_false_when_no_user(self):
        with patch(f"{MODULE}.CONN_PARAMS", {"user": "", "dbname": "rosetta", "host": "localhost", "port": 5432, "password": ""}):
            from src.db.db_access import is_db_configured
            assert is_db_configured() is False

    def test_false_when_no_dbname(self):
        with patch(f"{MODULE}.CONN_PARAMS", {"user": "admin", "dbname": "", "host": "localhost", "port": 5432, "password": ""}):
            from src.db.db_access import is_db_configured
            assert is_db_configured() is False


# ---------------------------------------------------------------------------
# load_static_from_db
# ---------------------------------------------------------------------------
class TestLoadStaticFromDb:
    """Tests for load_static_from_db with mocked psycopg2."""

    @pytest.fixture()
    def mock_conn(self):
        """Create a mock connection + cursor that returns plausible rows."""
        conn = MagicMock(name="Connection")
        cursor = MagicMock(name="Cursor")
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # We need to provide data for 12 sequential cursor.execute() + iteration calls.
        # Each execute followed by iteration — the cursor is iterable.
        # We'll use side_effect on __iter__ to return different data per query.

        call_count = {"n": 0}
        _HOUSES_ROW = {
            "number": 1,
            "short_meaning": "Self",
            "long_meaning": "The First House",
            "keywords": ["identity"],
            "life_domain": "Self",
            "schematic": None,
            "instructions": "",
        }
        _SIGN_ROW = {
            "name": "Aries",
            "glyph": "♈",
            "sign_index": 1,
            "element": "Fire",
            "modality": "Cardinal",
            "polarity": "Positive",
            "short_meaning": "Initiative",
            "long_meaning": "The Ram",
            "keywords": ["bold"],
            "assoc_with_house": 1,
            "opposite_sign": "Libra",
            "body_part": "Head",
            "gland_organ": "Adrenals",
        }
        _OBJECT_ROW = {
            "name": "Sun",
            "swisseph_id": 0,
            "glyph": "☉",
            "abrev": "Su",
            "short_meaning": "Identity",
            "long_meaning": "Core self",
            "narrative_role": "Character",
            "narrative_interp": "",
            "object_type": "Planet",
            "influence": [],
            "keywords": ["vitality"],
        }
        _ASPECT_ROW = {
            "name": "Conjunction",
            "glyph": "☌",
            "angle": 0,
            "orb": 8,
            "line_color": "#ff0000",
            "line_style": "solid",
            "short_meaning": "Fusion",
            "long_meaning": "Union",
            "sentence_meaning": "merge with",
            "keywords": ["merge"],
            "sign_interval": None,
            "sentence_name": None,
        }
        _AXIS_ROW = {
            "name": "AC-DC",
            "sign1": "Aries",
            "sign2": "Libra",
            "short_meaning": "Self vs Other",
            "long_meaning": "",
            "keywords": [],
            "schematic": None,
            "instructions": "",
        }
        _COMPASS_ROW = {
            "name": "East",
            "definition": "Self-assertion",
            "instructions": "",
        }
        _SHAPE_ROW = {
            "name": "Grand Trine",
            "glyph": "△",
            "nodes": 3,
            "configuration": "trine trine trine",
            "meaning": "Ease and flow",
        }
        _EMPTY = []

        # Map query # → rows
        query_data = [
            [_HOUSES_ROW],              # 1. houses
            [_SIGN_ROW],                # 2. signs
            [_OBJECT_ROW],              # 3. objects
            [_ASPECT_ROW],              # 4. aspects
            [_AXIS_ROW],                # 5. axes
            [_COMPASS_ROW],             # 6. compass_axes
            [_SHAPE_ROW],               # 7. shapes
            _EMPTY,                     # 8. sabian_symbols
            _EMPTY,                     # 9. object_sign_combos
            _EMPTY,                     # 10. object_house_combos
            _EMPTY,                     # 11. ordered_objects (fetchall not iter)
            _EMPTY,                     # 12. house_system_interp
        ]

        def _make_iter():
            idx = call_count["n"]
            call_count["n"] += 1
            if idx < len(query_data):
                return iter(query_data[idx])
            return iter([])

        cursor.__iter__ = lambda self: _make_iter()
        # For ordered_objects query #11, cursor is used as list comprehension
        # The actual code iterates over cursor after execute. We handle that
        # through __iter__. But for fetchall it's separate:
        cursor.fetchall.return_value = []

        with patch(f"{MODULE}._connect", return_value=conn):
            yield conn, cursor

    def test_returns_static_lookup(self, mock_conn):
        from src.db.db_access import load_static_from_db
        from src.core.models_v2 import StaticLookup

        result = load_static_from_db()
        assert isinstance(result, StaticLookup)

    def test_populates_houses(self, mock_conn):
        from src.db.db_access import load_static_from_db

        result = load_static_from_db()
        assert 1 in result.houses
        assert result.houses[1].short_meaning == "Self"

    def test_populates_signs(self, mock_conn):
        from src.db.db_access import load_static_from_db

        result = load_static_from_db()
        assert "Aries" in result.signs
        assert result.signs["Aries"].glyph == "♈"

    def test_closes_connection(self, mock_conn):
        from src.db.db_access import load_static_from_db

        conn, _ = mock_conn
        load_static_from_db()
        conn.close.assert_called_once()


# ---------------------------------------------------------------------------
# get_terms
# ---------------------------------------------------------------------------
class TestGetTerms:
    @pytest.fixture(autouse=True)
    def _reset_cache(self):
        """Reset the module-level _terms_cache before each test."""
        import src.db.db_access as mod
        mod._terms_cache = None
        yield
        mod._terms_cache = None

    def test_returns_list(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [
            {"canonical": "natal", "aliases": [], "factors": [], "intent": "natal",
             "domain": "chart", "description": "Birth chart"},
            {"canonical": "transit", "aliases": [], "factors": [], "intent": "transit",
             "domain": "prediction", "description": "Current transits"},
        ]

        with patch(f"{MODULE}._connect", return_value=mock_conn):
            from src.db.db_access import get_terms
            result = get_terms()
            assert isinstance(result, list)
            assert len(result) == 2

    def test_filtered_by_intent(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [
            {"canonical": "natal", "aliases": [], "factors": [], "intent": "natal",
             "domain": "chart", "description": "Birth chart"},
            {"canonical": "transit", "aliases": [], "factors": [], "intent": "transit",
             "domain": "prediction", "description": "Current transits"},
        ]

        with patch(f"{MODULE}._connect", return_value=mock_conn):
            from src.db.db_access import get_terms
            result = get_terms(intent="natal")
            assert len(result) == 1
            assert result[0]["canonical"] == "natal"

    def test_caches_result(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [
            {"canonical": "natal", "aliases": [], "factors": [], "intent": "natal",
             "domain": "chart", "description": "Birth chart"},
        ]

        with patch(f"{MODULE}._connect", return_value=mock_conn):
            from src.db.db_access import get_terms
            get_terms()
            get_terms()
            # Should only connect once
            assert mock_conn.cursor.return_value.__enter__.call_count == 1

    def test_exception_returns_empty(self):
        with patch(f"{MODULE}._connect", side_effect=Exception("connection failed")):
            from src.db.db_access import get_terms
            result = get_terms()
            assert result == []
