"""Test suite for domain exceptions."""

import pytest

from pl_agent.core.errors import (
    AdapterError,
    BreedingLoopError,
    DataIntegrityError,
    PalNotFoundError,
    ParseError,
    PlAgentError,
)


class TestPalNotFoundError:
    def test_basic(self):
        e = PalNotFoundError("Anubis")
        assert e.pal_id == "Anubis"
        assert "Anubis" in str(e)

    def test_is_pl_agent_error(self):
        assert issubclass(PalNotFoundError, PlAgentError)


class TestBreedingLoopError:
    def test_chain_formatting(self):
        e = BreedingLoopError(["A", "B", "C"])
        assert "A → B → C" in str(e)
        assert e.chain == ["A", "B", "C"]

    def test_single_node(self):
        e = BreedingLoopError(["X"])
        assert "X" in str(e)


class TestDataIntegrityError:
    def test_basic(self):
        e = DataIntegrityError("missing field: combi_rank")
        assert "missing field" in str(e)
        assert issubclass(DataIntegrityError, PlAgentError)


class TestParseError:
    def test_basic(self):
        e = ParseError("Anubis", "combi_rank")
        assert "combi_rank" in str(e)
        assert e.pal_id == "Anubis"
        assert e.field == "combi_rank"

    def test_is_pl_agent_error(self):
        assert issubclass(ParseError, PlAgentError)


class TestAdapterError:
    def test_basic(self):
        e = AdapterError("paldb.cc", "connection timeout")
        assert "connection timeout" in str(e)
        assert "[paldb.cc]" in str(e)
        assert e.source == "paldb.cc"
        assert issubclass(AdapterError, PlAgentError)


class TestPlAgentError:
    def test_is_base_exception(self):
        assert issubclass(PlAgentError, Exception)
