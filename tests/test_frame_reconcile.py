"""Regression tests for completeness/frame_reconcile.py and its collaborators.

No network calls: the IAALS parser is exercised against a saved fixture
(tests/fixtures/iaals_regulatory_models_snap1.html), fetched and pinned on
2026-07-01 per the user-confirmed URL in completeness/inventory_fetch.py.
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path

import pytest

from completeness.frame_reconcile import reconcile
from completeness.inventory_fetch import IaalsRegulatoryModelsFetcher
from completeness.ledger import merge_ledger
from completeness.models import ResidualGapRow
from completeness.us_states import resolve_usps
from models.enums import ProgramStatus, ProgramType
from models.schema import Program

_FIXTURE = Path(__file__).parent / "fixtures" / "iaals_regulatory_models_snap1.html"
_SOURCE_URL = "https://iaals.du.edu/projects/unlocking-legal-regulation/knowledge-center"


@pytest.fixture
def iaals_rows(tmp_path):
    fetcher = IaalsRegulatoryModelsFetcher(raw_dir=tmp_path)
    return fetcher.parse(_FIXTURE.read_bytes())


def _fake_program(program_id: str, jurisdiction: str, program_type: ProgramType) -> Program:
    return Program(
        program_id=program_id,
        jurisdiction=jurisdiction,
        program_name=f"Fake {program_id}",
        program_type=program_type,
        regulator="Fake Regulator",
        regulator_url="https://example.com",
        authorizing_rule="Fake Rule 1",
        program_status=ProgramStatus.active,
        allows_nonlawyer_ownership=False,
        allows_upl_waiver=False,
        allows_software_provider=False,
        source_url="https://example.com",
        retrieved_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        scraper_version="0.1.0",
    )


# ── IAALS parser ──────────────────────────────────────────────────────────────


class TestIaalsParser:
    def test_row_count(self, iaals_rows):
        assert len(iaals_rows) == 54

    def test_domestic_row_count(self, iaals_rows):
        domestic = [r for r in iaals_rows if r.region == "Domestic"]
        assert len(domestic) == 39

    def test_international_rows_excluded_from_domestic(self, iaals_rows):
        intl = [r for r in iaals_rows if r.region == "International"]
        assert len(intl) == 15
        assert all(r.jurisdiction is None for r in intl)

    def test_known_implemented_rows_present(self, iaals_rows):
        domestic = {
            (r.model_type_raw, r.status_bucket, r.jurisdiction_raw): r.jurisdiction
            for r in iaals_rows
            if r.region == "Domestic"
        }
        assert domestic[("Regulatory Sandbox", "Implemented Programs", "Utah")] == "UT"
        assert domestic[("Regulatory Sandbox", "Implemented Programs", "Washington")] == "WA"
        assert (
            domestic[
                ("Alternative Business Structures", "Implemented Programs", "Washington, D.C.")
            ]
            == "DC"
        )
        assert (
            domestic[("Alternative Business Structures", "Implemented Programs", "Puerto Rico")]
            == "PR"
        )
        assert (
            domestic[
                (
                    "Community-Based Justice Worker Models",
                    "Implemented Programs",
                    "Utah (through its Sandbox)",
                )
            ]
            == "UT"
        )

    def test_model_type_mapping(self, iaals_rows):
        by_raw = {r.model_type_raw: r.model_type for r in iaals_rows}
        assert by_raw["Regulatory Sandbox"] == ProgramType.sandbox
        assert by_raw["Alternative Business Structures"] == ProgramType.abs
        assert by_raw["Allied Legal Professionals"] == ProgramType.alp_license
        assert (
            by_raw["Community-Based Justice Worker Models"] == ProgramType.community_justice_worker
        )

    def test_unmapped_domestic_name_surfaced_not_dropped(self, iaals_rows):
        # "United Kingdom" appears under a Community-Based Justice Worker Models
        # bucket with no preceding "International" marker (see parser docstring);
        # it must show up as an unmapped domestic row, never silently vanish.
        uk_rows = [r for r in iaals_rows if r.jurisdiction_raw == "United Kingdom"]
        assert len(uk_rows) == 1
        assert uk_rows[0].region == "Domestic"
        assert uk_rows[0].jurisdiction is None

    def test_zero_rows_raises(self, tmp_path):
        fetcher = IaalsRegulatoryModelsFetcher(raw_dir=tmp_path)
        with pytest.raises(ValueError, match="matched zero rows"):
            fetcher.parse(b"<html><body><h2>Something Else</h2></body></html>")

    def test_jurisdiction_without_bucket_context_raises(self, tmp_path):
        fetcher = IaalsRegulatoryModelsFetcher(raw_dir=tmp_path)
        html = (
            b"<html><body>"
            b"<h2>Regulatory Models</h2>"
            b"<h3>Regulatory Sandbox</h3>"
            b"<h4>Utah</h4>"
            b"</body></html>"
        )
        with pytest.raises(ValueError, match="without a model type"):
            fetcher.parse(html)


# ── us_states ─────────────────────────────────────────────────────────────────


class TestResolveUsps:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Utah", "UT"),
            ("Washington, D.C.", "DC"),
            ("Puerto Rico", "PR"),
            ("Utah (through its Sandbox)", "UT"),
            ("Alberta, Canada", None),
            ("United Kingdom", None),
        ],
    )
    def test_resolve(self, name, expected):
        assert resolve_usps(name) == expected


# ── reconcile() ───────────────────────────────────────────────────────────────


class TestReconcile:
    def test_gap_detection_against_seeded_programs(self, iaals_rows):
        # Mirrors the real seeded program table (scripts/seed_programs.py) as
        # of 2026-07-01: prog_ut_sandbox (UT/sandbox), prog_az_abs (AZ/abs),
        # prog_dc_rule54 (DC/abs) are the only rows IAALS's Implemented-Programs
        # buckets can match against for the three in-scope model types.
        programs = [
            _fake_program("prog_ut_sandbox", "UT", ProgramType.sandbox),
            _fake_program("prog_az_abs", "AZ", ProgramType.abs),
            _fake_program("prog_dc_rule54", "DC", ProgramType.abs),
            # Out of scope for this source — must not affect the mine-not-theirs check.
            _fake_program("prog_az_lp", "AZ", ProgramType.alp_license),
            _fake_program("prog_ca_lda", "CA", ProgramType.document_preparer),
        ]
        gaps, informational, unmapped = reconcile(programs, iaals_rows, _SOURCE_URL)

        gap_keys = {(g.jurisdiction, g.item.split(" — ")[0].split(" (")[0]) for g in gaps}
        # theirs-not-ours: real candidates that should surface.
        assert ("WA", "Regulatory Sandbox") in gap_keys
        assert ("WA", "Alternative Business Structures") in gap_keys
        assert ("PR", "Alternative Business Structures") in gap_keys
        assert ("IN", "Regulatory Sandbox") in gap_keys
        assert ("AK", "Community-Based Justice Worker Models") in gap_keys

        # Matched programs must NOT appear as gaps.
        assert not any(g.item == "Regulatory Sandbox — Utah" for g in gaps)
        assert not any(g.item == "Alternative Business Structures — Arizona" for g in gaps)
        assert not any(g.item == "Alternative Business Structures — Washington, D.C." for g in gaps)
        assert all(g.classification == "unresolved" for g in gaps)
        assert all(g.detected_by == "frame_reconcile" for g in gaps)

        # alp_license / document_preparer programs are out of scope for this
        # source's mine-not-theirs check — they must never produce a gap row.
        assert not any("prog_az_lp" in g.item or "prog_ca_lda" in g.item for g in gaps)

        assert len(unmapped) == 1  # "United Kingdom"
        assert len(informational) > 0

    def test_matched_program_produces_no_gap(self, iaals_rows):
        programs = [_fake_program("prog_ut_sandbox", "UT", ProgramType.sandbox)]
        gaps, _, _ = reconcile(programs, iaals_rows, _SOURCE_URL)
        assert not any(g.item == "Regulatory Sandbox — Utah" for g in gaps)

    def test_no_programs_flags_every_implemented_row(self, iaals_rows):
        gaps, _, _ = reconcile([], iaals_rows, _SOURCE_URL)
        implemented_domestic = [
            r
            for r in iaals_rows
            if r.region == "Domestic"
            and r.status_bucket in {"Implemented Programs", "Programs Being Implemented"}
        ]
        assert len(gaps) == len(implemented_domestic)


# ── ledger merge ──────────────────────────────────────────────────────────────


class TestMergeLedger:
    def _candidate(
        self, item="Regulatory Sandbox — Washington", jurisdiction="WA"
    ) -> ResidualGapRow:
        return ResidualGapRow(
            item=item,
            jurisdiction=jurisdiction,
            classification="unresolved",
            source_url=_SOURCE_URL,
            proposed_action="check it out",
            resolved=False,
            detected_by="frame_reconcile",
            detected_at=datetime.date(2026, 7, 1),
        )

    def test_new_candidate_appended(self, tmp_path):
        path = tmp_path / "residual_gaps.csv"
        count = merge_ledger(path, [self._candidate()])
        assert count == 1
        rows = list(csv.DictReader(path.open()))
        assert rows[0]["classification"] == "unresolved"
        assert rows[0]["resolved"] == "False"

    def test_resolved_row_never_clobbered_on_rerun(self, tmp_path):
        path = tmp_path / "residual_gaps.csv"
        merge_ledger(path, [self._candidate()])

        # Human reviews and resolves the row by hand.
        rows = list(csv.DictReader(path.open()))
        rows[0]["classification"] = "in_frame_missing"
        rows[0]["resolved"] = "True"
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        # Re-running frame_reconcile proposes the *same* candidate again.
        merge_ledger(path, [self._candidate()])

        rows_after = list(csv.DictReader(path.open()))
        assert len(rows_after) == 1
        assert rows_after[0]["classification"] == "in_frame_missing"
        assert rows_after[0]["resolved"] == "True"

    def test_new_key_appended_alongside_existing(self, tmp_path):
        path = tmp_path / "residual_gaps.csv"
        merge_ledger(path, [self._candidate()])
        other = self._candidate(
            item="Alternative Business Structures — Puerto Rico", jurisdiction="PR"
        )
        count = merge_ledger(path, [other])
        assert count == 2
