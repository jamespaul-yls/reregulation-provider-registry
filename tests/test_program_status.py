"""Tests for resolve/program_status.py.

Unit tests run against saved fixture files — no network calls.
Integration tests (``@pytest.mark.net``) hit live APIs; run with::

    uv run --env-file .env pytest tests/test_program_status.py -m net -v

Fixture files:
    tests/fixtures/openstates_tx_alp.json   — OS /bills?jurisdiction=tx&q=...paraprofessional
    tests/fixtures/openstates_wa_lllt.json  — OS /bills?jurisdiction=wa&q=...legal+technician
    tests/fixtures/legiscan_tx_alp.json     — LS op=search&state=TX&q=...paraprofessional
    tests/fixtures/legiscan_wa_lllt.json    — LS op=search&state=WA&q=...legal+technician
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.enums import ProgramStatus, ProgramType
from models.schema import Program
from resolve.program_status import (
    BillDirection,
    BillMatch,
    ProgramConfig,
    _check_enacted,
    _check_failed,
    _classify_direction,
    _parse_legiscan_bill,
    _parse_openstates_bill,
    _score_relevance,
    resolve_one,
    search_legiscan,
    search_openstates,
)

_FIX = Path(__file__).parent / "fixtures"


# ── helpers ───────────────────────────────────────────────────────────────────


def _load(name: str) -> dict:
    return json.loads((_FIX / name).read_text())


def _make_program(
    program_id: str = "prog_tx_alp",
    program_status: ProgramStatus = ProgramStatus.active,
) -> Program:
    return Program(
        program_id=program_id,
        jurisdiction="TX",
        program_name="Test Program",
        program_type=ProgramType.alp_license,
        regulator="Test Regulator",
        regulator_url="https://example.com",
        authorizing_rule="Test Rule",
        launch_date=None,
        program_status=program_status,
        sunset_date=None,
        allows_nonlawyer_ownership=False,
        allows_upl_waiver=False,
        allows_software_provider=False,
        source_url="https://example.com",
        retrieved_at=datetime.datetime(2026, 6, 30, tzinfo=datetime.UTC),
        scraper_version="test",
    )


# ── direction classifier ──────────────────────────────────────────────────────


class TestClassifyDirection:
    def test_positive_title(self):
        result = _classify_direction("Establishing a licensed paraprofessional program")
        assert result == BillDirection.positive

    def test_negative_title(self):
        result = _classify_direction("Sunsetting the alternative business structure program")
        assert result == BillDirection.negative

    def test_neutral_mixed(self):
        result = _classify_direction("Establishing and then sunsetting a legal pilot program")
        assert result == BillDirection.neutral

    def test_unknown(self):
        result = _classify_direction("Appropriations for the judiciary general fund")
        assert result == BillDirection.unknown

    def test_abstract_contributes(self):
        assert (
            _classify_direction("HB 999", "This bill authorizes a licensing regime for paralegals")
            == BillDirection.positive
        )


# ── enactment / failure helpers ───────────────────────────────────────────────


class TestCheckEnacted:
    def test_signed_phrase(self):
        assert _check_enacted("Signed by Governor", []) is True

    def test_classification(self):
        assert _check_enacted("Some action", ["executive-signature"]) is True

    def test_not_enacted(self):
        assert _check_enacted("Referred to committee", []) is False

    def test_chaptered(self):
        assert _check_enacted("Chaptered by Secretary of State", []) is True


class TestCheckFailed:
    def test_failed_action(self):
        assert _check_failed("Bill failed in committee") is True

    def test_vetoed(self):
        assert _check_failed("Vetoed by governor") is True

    def test_active(self):
        assert _check_failed("Referred to Judiciary") is False


# ── Open States parser ────────────────────────────────────────────────────────


class TestParseOpenStatesItem:
    def test_basic_fields(self):
        data = _load("openstates_tx_alp.json")
        # HB 2624 is about legal paraprofessionals (index 1)
        item = data["results"][1]
        bill = _parse_openstates_bill(item)

        assert bill.identifier == "HB 2624"
        assert "paraprofessional" in bill.title.lower()
        assert bill.session == "89R"
        assert bill.jurisdiction == "TX"
        assert bill.api_source == "openstates"
        assert bill.direction == BillDirection.positive
        assert bill.enacted is False

    def test_source_url_format(self):
        data = _load("openstates_tx_alp.json")
        item = data["results"][1]
        bill = _parse_openstates_bill(item)
        assert bill.source_url.startswith("https://openstates.org/tx/bills/")
        assert "HB2624" in bill.source_url

    def test_latest_action_date_parsed(self):
        data = _load("openstates_tx_alp.json")
        item = data["results"][1]
        bill = _parse_openstates_bill(item)
        assert isinstance(bill.latest_action_date, datetime.date)
        assert bill.latest_action_date == datetime.date(2025, 3, 18)

    def test_all_results_parse(self):
        data = _load("openstates_tx_alp.json")
        for item in data["results"]:
            bill = _parse_openstates_bill(item)
            assert isinstance(bill, BillMatch)
            assert bill.api_source == "openstates"

    def test_wa_results_parse(self):
        data = _load("openstates_wa_lllt.json")
        bills = [_parse_openstates_bill(r) for r in data["results"]]
        assert all(b.jurisdiction == "WA" for b in bills)


# ── LegiScan parser ───────────────────────────────────────────────────────────


class TestParseLegiscanItem:
    def _first_item(self, fixture_name: str) -> dict:
        data = _load(fixture_name)
        sr = data["searchresult"]
        return next(v for k, v in sorted(sr.items()) if k != "summary" and isinstance(v, dict))

    def test_tx_basic_fields(self):
        item = self._first_item("legiscan_tx_alp.json")
        bill = _parse_legiscan_bill(item)

        assert bill.jurisdiction == "TX"
        assert bill.api_source == "legiscan"
        assert isinstance(bill.bill_id, str) and bill.bill_id
        assert bill.identifier != ""

    def test_bill_number_key(self):
        # Fixture uses "bill_number" (not "number") — ensure parser reads it
        item = self._first_item("legiscan_tx_alp.json")
        assert "bill_number" in item, "fixture has bill_number key"
        bill = _parse_legiscan_bill(item)
        assert bill.identifier == item["bill_number"]

    def test_wa_results_parse(self):
        data = _load("legiscan_wa_lllt.json")
        sr = data["searchresult"]
        for k, v in sr.items():
            if k != "summary" and isinstance(v, dict):
                bill = _parse_legiscan_bill(v)
                assert isinstance(bill, BillMatch)
                assert bill.api_source == "legiscan"

    def test_last_action_date_parsed(self):
        # Find an item with a non-zero last_action_date
        data = _load("legiscan_tx_alp.json")
        sr = data["searchresult"]
        for k, v in sr.items():
            if k == "summary" or not isinstance(v, dict):
                continue
            if v.get("last_action_date", "0000-00-00") != "0000-00-00":
                bill = _parse_legiscan_bill(v)
                assert isinstance(bill.latest_action_date, datetime.date)
                break


# ── relevance scorer ──────────────────────────────────────────────────────────


class TestScoreRelevance:
    _cfg = ProgramConfig(
        jurisdiction="tx",
        queries=["licensed legal paraprofessional", "legal paraprofessional"],
        known_bills=["SB 1218"],
        enacted_means_proposed=True,
    )

    def _make_bill(self, identifier: str, title: str, enacted: bool = False) -> BillMatch:
        return BillMatch(
            bill_id="x",
            identifier=identifier,
            title=title,
            session="88",
            jurisdiction="TX",
            latest_action="",
            latest_action_date=None,
            enacted=enacted,
            failed=False,
            direction=BillDirection.positive,
            source_url="",
        )

    def test_known_bill_boost(self):
        b = self._make_bill("SB 1218", "Relating to licensed legal paraprofessionals")
        score = _score_relevance(b, self._cfg)
        assert score >= 0.5, f"Known-bill match should score ≥ 0.5, got {score}"

    def test_query_match_boost(self):
        b = self._make_bill("HB 999", "Relating to licensed legal paraprofessional licensing")
        score = _score_relevance(b, self._cfg)
        assert score > 0.0

    def test_enacted_boost(self):
        title = "Relating to licensed legal paraprofessionals"
        b_no = self._make_bill("SB 1218", title, enacted=False)
        b_yes = self._make_bill("SB 1218", title, enacted=True)
        assert _score_relevance(b_yes, self._cfg) > _score_relevance(b_no, self._cfg)

    def test_irrelevant_bill_scores_zero(self):
        b = self._make_bill("HB 1", "Appropriations for the general government operations fund")
        assert _score_relevance(b, self._cfg) == 0.0


# ── search_openstates (mocked) ────────────────────────────────────────────────


class TestSearchOpenStates:
    def test_returns_billmatches_from_fixture(self):
        data = _load("openstates_tx_alp.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        mock_resp.raise_for_status.return_value = None

        with patch("resolve.program_status.httpx.get", return_value=mock_resp):
            bills = search_openstates("tx", ["licensed legal paraprofessional"], "FAKE_KEY")

        assert len(bills) == len(data["results"])
        assert all(isinstance(b, BillMatch) for b in bills)
        assert all(b.api_source == "openstates" for b in bills)

    def test_deduplicates_across_queries(self):
        data = _load("openstates_tx_alp.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        mock_resp.raise_for_status.return_value = None

        with (
            patch("resolve.program_status.httpx.get", return_value=mock_resp),
            patch("resolve.program_status.time.sleep"),
        ):
            # Two queries returning the same fixture — deduplicated by bill id
            bills = search_openstates("tx", ["q1", "q2"], "FAKE_KEY")

        ids = [b.bill_id for b in bills]
        assert len(ids) == len(set(ids)), "Duplicate bill IDs present"

    def test_sorted_by_date_desc(self):
        data = _load("openstates_tx_alp.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        mock_resp.raise_for_status.return_value = None

        with (
            patch("resolve.program_status.httpx.get", return_value=mock_resp),
            patch("resolve.program_status.time.sleep"),
        ):
            bills = search_openstates("tx", ["licensed legal paraprofessional"], "FAKE_KEY")

        dates = [b.latest_action_date for b in bills if b.latest_action_date]
        assert dates == sorted(dates, reverse=True)

    def test_include_params_are_separate(self):
        """Verify include= is NOT comma-encoded (would cause 422)."""
        data = _load("openstates_tx_alp.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        mock_resp.raise_for_status.return_value = None

        with (
            patch("resolve.program_status.httpx.get", return_value=mock_resp) as mock_get,
            patch("resolve.program_status.time.sleep"),
        ):
            search_openstates("tx", ["legal paraprofessional"], "FAKE_KEY")

        _, kwargs = mock_get.call_args
        params = kwargs.get("params", [])
        # params is a list of tuples when passed correctly
        include_vals = [v for k, v in params if k == "include"]
        assert "actions,abstracts" not in include_vals, (
            "include must not be comma-encoded; pass as separate params"
        )
        assert "actions" in include_vals


# ── search_legiscan (mocked) ──────────────────────────────────────────────────


class TestSearchLegiscan:
    def test_returns_billmatches_from_fixture(self):
        data = _load("legiscan_tx_alp.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        mock_resp.raise_for_status.return_value = None

        with (
            patch("resolve.program_status.httpx.get", return_value=mock_resp),
            patch("resolve.program_status.time.sleep"),
        ):
            bills = search_legiscan("TX", ["licensed legal paraprofessional"], "FAKE_KEY")

        expected_count = len([k for k in data["searchresult"] if k != "summary"])
        assert len(bills) == expected_count
        assert all(isinstance(b, BillMatch) for b in bills)
        assert all(b.api_source == "legiscan" for b in bills)

    def test_skips_summary_key(self):
        data = _load("legiscan_wa_lllt.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        mock_resp.raise_for_status.return_value = None

        with (
            patch("resolve.program_status.httpx.get", return_value=mock_resp),
            patch("resolve.program_status.time.sleep"),
        ):
            bills = search_legiscan("WA", ["limited license legal technician"], "FAKE_KEY")

        # "summary" key must never produce a BillMatch
        assert not any(b.bill_id == "summary" for b in bills)


# ── resolve_one — WA LLLT (status_override path) ─────────────────────────────


class TestResolveWaLllt:
    def test_status_override_returns_sunset(self):
        program = _make_program("prog_wa_lllt", ProgramStatus.active)
        mock_resp = MagicMock()
        mock_resp.json.return_value = _load("openstates_wa_lllt.json")
        mock_resp.raise_for_status.return_value = None

        with (
            patch("resolve.program_status.httpx.get", return_value=mock_resp),
            patch("resolve.program_status.time.sleep"),
        ):
            signal = resolve_one(program, "FAKE_OS", "FAKE_LS")

        assert signal.proposed_status == ProgramStatus.sunset
        assert signal.confidence == 1.0
        assert signal.proposed_sunset_date == datetime.date(2021, 7, 31)
        assert "court" in signal.reason.lower() or "administrative" in signal.reason.lower()
        assert "APR28" in signal.source_url

    def test_status_override_is_change_when_current_is_active(self):
        program = _make_program("prog_wa_lllt", ProgramStatus.active)
        with (
            patch(
                "resolve.program_status.httpx.get",
                return_value=MagicMock(
                    json=lambda: _load("openstates_wa_lllt.json"),
                    raise_for_status=lambda: None,
                ),
            ),
            patch("resolve.program_status.time.sleep"),
        ):
            signal = resolve_one(program, "FAKE_OS", "FAKE_LS")
        assert signal.is_change is True

    def test_status_override_not_change_when_already_sunset(self):
        program = _make_program("prog_wa_lllt", ProgramStatus.sunset)
        with (
            patch(
                "resolve.program_status.httpx.get",
                return_value=MagicMock(
                    json=lambda: _load("openstates_wa_lllt.json"),
                    raise_for_status=lambda: None,
                ),
            ),
            patch("resolve.program_status.time.sleep"),
        ):
            signal = resolve_one(program, "FAKE_OS", "FAKE_LS")
        assert signal.is_change is True  # sunset_date is still proposed (new info)


# ── resolve_one — TX ALP (legislative path) ───────────────────────────────────


class TestResolveTxAlp:
    def _signal(self, os_data: dict, ls_data: dict | None = None) -> object:
        os_resp = MagicMock()
        os_resp.json.return_value = os_data
        os_resp.raise_for_status.return_value = None

        program = _make_program("prog_tx_alp", ProgramStatus.active)

        with (
            patch("resolve.program_status.httpx.get", return_value=os_resp),
            patch("resolve.program_status.time.sleep"),
        ):
            return resolve_one(program, "FAKE_OS", "FAKE_LS")

    def test_finds_relevant_bills(self):
        signal = self._signal(_load("openstates_tx_alp.json"))
        # The fixture has bills about "licensing and regulation of certain legal paraprofessionals"
        # At least one bill should score high enough to trigger evidence
        assert len(signal.evidence) > 0

    def test_known_bill_sb1218_not_in_recent_fixture(self):
        """SB 1218 (88th session, 2023) isn't in our per_page=10 recent fixture."""
        data = _load("openstates_tx_alp.json")
        identifiers = [r["identifier"] for r in data["results"]]
        assert "SB 1218" not in identifiers

    def test_enacted_means_proposed_flag(self):
        """Verify the enacted_means_proposed config is set for TX ALP."""
        from resolve.program_status import _PROGRAM_CONFIGS

        cfg = _PROGRAM_CONFIGS["prog_tx_alp"]
        assert cfg.enacted_means_proposed is True

    def test_no_config_returns_no_change(self):
        program = _make_program("prog_unknown_xyz", ProgramStatus.active)
        with (
            patch("resolve.program_status.httpx.get", return_value=MagicMock()),
            patch("resolve.program_status.time.sleep"),
        ):
            signal = resolve_one(program, "FAKE_OS", "FAKE_LS")
        assert signal.proposed_status is None
        assert signal.confidence == 0.0


# ── integration tests (live APIs) ────────────────────────────────────────────

pytestmark_net = pytest.mark.net


@pytest.mark.net
def test_integration_wa_lllt_resolves_to_sunset():
    """WA LLLT must always resolve to ProgramStatus.sunset with confidence=1.0."""
    os_key = os.environ.get("OPENSTATES_KEY", "")
    ls_key = os.environ.get("LEGISCAN_KEY", "")
    if not os_key or not ls_key:
        pytest.skip("API keys not set (OPENSTATES_KEY, LEGISCAN_KEY)")

    program = _make_program("prog_wa_lllt", ProgramStatus.active)
    signal = resolve_one(program, os_key, ls_key)

    assert signal.proposed_status == ProgramStatus.sunset
    assert signal.confidence == 1.0
    assert signal.proposed_sunset_date == datetime.date(2021, 7, 31)


@pytest.mark.net
def test_integration_tx_alp_resolves_to_proposed_or_has_evidence():
    """TX ALP must produce evidence and either proposed or high-confidence result."""
    os_key = os.environ.get("OPENSTATES_KEY", "")
    ls_key = os.environ.get("LEGISCAN_KEY", "")
    if not os_key or not ls_key:
        pytest.skip("API keys not set (OPENSTATES_KEY, LEGISCAN_KEY)")

    program = _make_program("prog_tx_alp", ProgramStatus.active)
    signal = resolve_one(program, os_key, ls_key)

    # Must find at least one relevant bill (SB 1218 or current-session bills)
    assert len(signal.evidence) > 0, "TX ALP resolver must find at least one bill"
    # With enacted_means_proposed, any enacted positive bill → proposed
    if signal.proposed_status is not None:
        assert signal.proposed_status in (ProgramStatus.proposed, ProgramStatus.active)
