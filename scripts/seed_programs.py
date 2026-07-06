"""Seed one program row per in-scope reregulation program.

Idempotent: safe to re-run. Upserts all programs, then prints the full table.

Programs in scope (10 total):
  prog_ut_sandbox      — Utah Legal Services Innovation Sandbox
  prog_az_abs          — Arizona Alternative Business Structures
  prog_az_lp           — Arizona Legal Paraprofessional Program
  prog_ut_lpp          — Utah Licensed Paralegal Practitioner Program
  prog_co_llp          — Colorado Limited License Professional Program
  prog_mn_lp           — Minnesota Legal Paraprofessional Program
  prog_wa_lllt         — Washington Limited License Legal Technician Program (sunset)
  prog_tx_alp          — Texas Licensed Legal Paraprofessionals and LCCAs (paused)
  prog_ca_lda          — California Legal Document Assistant Program
  prog_wa_entity_pilot — Washington Entity Regulation Pilot Project (resolves both
                         IAALS's "WA ABS" and "WA sandbox" listings — one program)

D.C. Rule 5.4(b) (prog_dc_rule54) was removed from scope 2026-07-06 — a permissive
ethics rule with no registration requirement has no roster or providers to ever track,
structurally, unlike the other zero-provider programs. See docs/sampling_frame.md §4
and validation/dc_rule54.md for the full reasoning.

Usage:
    uv run python scripts/seed_programs.py
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.enums import ProgramStatus, ProgramType
from models.schema import Program
from pipeline.db import RegistryStore

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"

# ── fixed seed timestamp ──────────────────────────────────────────────────────
# Pinned so the seed is deterministic / idempotent across runs.
_SEED_TS = datetime.datetime(2026, 6, 29, 0, 0, 0, tzinfo=datetime.UTC)
_V = "0.1.0"

# ── program definitions ───────────────────────────────────────────────────────

PROGRAMS: list[Program] = [
    # ── 1. Utah Sandbox ───────────────────────────────────────────────────────
    Program(
        program_id="prog_ut_sandbox",
        jurisdiction="UT",
        program_name="Utah Legal Services Innovation Sandbox",
        program_type=ProgramType.sandbox,
        regulator="Utah Office of Legal Services Innovation",
        regulator_url="https://utahinnovationoffice.org",
        authorizing_rule=(
            "Utah Supreme Court Standing Order 15 (Aug. 14, 2020); Phase 2 amended"
            " Standing Order 15 (2024)"
        ),
        launch_date=datetime.date(2020, 8, 14),
        program_status=ProgramStatus.active,
        sunset_date=datetime.date(2027, 8, 14),
        allows_nonlawyer_ownership=True,
        allows_upl_waiver=True,
        allows_software_provider=True,
        source_url="https://utahinnovationoffice.org/authorized-entities/",
        retrieved_at=_SEED_TS,
        scraper_version=_V,
    ),
    # ── 2. Arizona ABS ────────────────────────────────────────────────────────
    Program(
        program_id="prog_az_abs",
        jurisdiction="AZ",
        program_name="Arizona Alternative Business Structures",
        program_type=ProgramType.abs,
        regulator="Arizona Supreme Court",
        regulator_url="https://www.azcourts.gov/cld/Alternative-Business-Structure",
        authorizing_rule=(
            "Ariz. Ct. Admin. Code (ACJA) § 7-209; Ariz. R. Sup. Ct. 33.1 (eff. Jan. 1, 2021)"
        ),
        launch_date=datetime.date(2021, 1, 1),
        program_status=ProgramStatus.active,
        sunset_date=None,
        allows_nonlawyer_ownership=True,
        allows_upl_waiver=False,
        allows_software_provider=True,
        source_url="https://www.azcourts.gov/cld/Alternative-Business-Structure",
        retrieved_at=_SEED_TS,
        scraper_version=_V,
    ),
    # ── 3. Arizona Legal Paraprofessional ─────────────────────────────────────
    Program(
        program_id="prog_az_lp",
        jurisdiction="AZ",
        program_name="Arizona Legal Paraprofessional Program",
        program_type=ProgramType.alp_license,
        regulator="Arizona Supreme Court",
        regulator_url="https://www.azcourts.gov/cld/Legal-Paraprofessional",
        authorizing_rule=(
            "Ariz. Ct. Admin. Code (ACJA) § 7-210; Ariz. R. Sup. Ct. 33.1 (eff. Jan. 1, 2022)"
        ),
        launch_date=datetime.date(2022, 1, 1),
        program_status=ProgramStatus.active,
        sunset_date=None,
        allows_nonlawyer_ownership=False,
        allows_upl_waiver=True,
        allows_software_provider=False,
        source_url="https://www.azcourts.gov/cld/Legal-Paraprofessional/Directory",
        retrieved_at=_SEED_TS,
        scraper_version=_V,
    ),
    # ── 4. Utah Licensed Paralegal Practitioner ───────────────────────────────
    Program(
        program_id="prog_ut_lpp",
        jurisdiction="UT",
        program_name="Utah Licensed Paralegal Practitioner Program",
        program_type=ProgramType.alp_license,
        regulator="Utah State Bar",
        regulator_url="https://www.utahbar.org/licensed-paralegal-practitioner/",
        authorizing_rule=(
            "Utah Rules Governing Licensed Paralegal Practitioners,"
            " Rule 14-802 (eff. 2018); practice expanded by subsequent amendments"
        ),
        launch_date=datetime.date(2019, 1, 1),
        program_status=ProgramStatus.active,
        sunset_date=None,
        allows_nonlawyer_ownership=False,
        allows_upl_waiver=True,
        allows_software_provider=False,
        source_url="https://www.utahbar.org/licensed-paralegal-practitioner/",
        retrieved_at=_SEED_TS,
        scraper_version=_V,
    ),
    # ── 5. Colorado Limited Licensed Professional ─────────────────────────────
    Program(
        program_id="prog_co_llp",
        jurisdiction="CO",
        program_name="Colorado Limited Licensed Professional Program",
        program_type=ProgramType.alp_license,
        regulator="Colorado Office of Attorney Regulation Counsel",
        regulator_url="https://www.coloradolegalregulation.com/",
        authorizing_rule=("C.R.C.P. Chapter 20 Rule 220 (eff. Jan. 1, 2023)"),
        launch_date=datetime.date(2023, 1, 1),
        program_status=ProgramStatus.active,
        sunset_date=None,
        allows_nonlawyer_ownership=False,
        allows_upl_waiver=True,
        allows_software_provider=False,
        source_url=("https://www.coloradolegalregulation.com/PDF/LLP/Admitted%20LLP%20Roster.pdf"),
        retrieved_at=_SEED_TS,
        scraper_version=_V,
    ),
    # ── 6. Minnesota Legal Paraprofessional ──────────────────────────────────
    Program(
        program_id="prog_mn_lp",
        jurisdiction="MN",
        program_name="Minnesota Legal Paraprofessional Program",
        program_type=ProgramType.paraprofessional_pilot,
        regulator="Minnesota Supreme Court",
        regulator_url="https://mncourts.gov/courts/supremecourt/committees/LPP.aspx",
        authorizing_rule=(
            "Minn. Stat. § 480.0591; Minn. R. Gen. Prac. 301–319"
            " (pilot eff. 2021; permanent eff. Jan. 1, 2025)"
        ),
        launch_date=datetime.date(2021, 1, 1),
        program_status=ProgramStatus.active,
        sunset_date=None,
        allows_nonlawyer_ownership=False,
        allows_upl_waiver=True,
        allows_software_provider=False,
        source_url=(
            "https://mncourts.gov/_media/migration/appellate/supreme-court"
            "/Roster-of-Approved-Legal-Paraprofessionals.pdf"
        ),
        retrieved_at=_SEED_TS,
        scraper_version=_V,
    ),
    # ── 7. Washington LLLT (sunset) ───────────────────────────────────────────
    Program(
        program_id="prog_wa_lllt",
        jurisdiction="WA",
        program_name="Washington Limited License Legal Technician Program",
        program_type=ProgramType.alp_license,
        regulator="Washington State Bar Association",
        regulator_url=(
            "https://www.wsba.org/for-legal-professionals"
            "/join-the-legal-profession-in-wa/limited-license-legal-technicians"
        ),
        authorizing_rule=(
            "Wash. APR 28 (eff. 2012); Rules for Limited License Legal Technicians"
            " (eff. 2015); sunset eff. July 31, 2021 (WA Sup. Ct. Order, June 2020)"
        ),
        launch_date=datetime.date(2015, 1, 1),
        program_status=ProgramStatus.sunset,
        sunset_date=datetime.date(2021, 7, 31),
        allows_nonlawyer_ownership=False,
        allows_upl_waiver=True,
        allows_software_provider=False,
        source_url=(
            "https://www.mywsba.org/PersonifyEbusiness/LegalDirectory.aspx"
            "?ShowSearchResults=TRUE&LicenseType=LLLT"
        ),
        retrieved_at=_SEED_TS,
        scraper_version=_V,
    ),
    # ── 8. Texas LLPCA (paused) ───────────────────────────────────────────────
    Program(
        program_id="prog_tx_alp",
        jurisdiction="TX",
        program_name=(
            "Texas Licensed Legal Paraprofessionals and Licensed Court-Access Assistants"
        ),
        program_type=ProgramType.alp_license,
        regulator="State Bar of Texas",
        regulator_url="https://www.texasbar.com/paraprofessionals/",
        authorizing_rule=(
            "Texas Rules Governing Licensed Legal Paraprofessionals and Licensed"
            " Court-Access Assistants, Misc. Docket No. 24-9050 (prelim. approval"
            " Aug. 6, 2024); effective date delayed by Misc. Docket No. 24-9095"
            " (Nov. 4, 2024) pending further Supreme Court order"
        ),
        launch_date=None,
        program_status=ProgramStatus.paused,
        sunset_date=None,
        allows_nonlawyer_ownership=False,
        allows_upl_waiver=True,
        allows_software_provider=False,
        source_url="https://www.texasbar.com/paraprofessionals/",
        retrieved_at=_SEED_TS,
        scraper_version=_V,
    ),
    # ── 9. California LDA ─────────────────────────────────────────────────────
    Program(
        program_id="prog_ca_lda",
        jurisdiction="CA",
        program_name="California Legal Document Assistant Program",
        program_type=ProgramType.document_preparer,
        regulator="California County Clerks (county-level registration)",
        regulator_url=(
            "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
            "?sectionNum=6400.&lawCode=BPC"
        ),
        authorizing_rule=(
            "Cal. Bus. & Prof. Code § 6400 et seq. (Stats. 1999, c. 711);"
            " registration with county clerk and $25,000 bond required per county"
        ),
        launch_date=datetime.date(1999, 1, 1),
        program_status=ProgramStatus.active,
        sunset_date=None,
        allows_nonlawyer_ownership=False,
        allows_upl_waiver=False,
        allows_software_provider=False,
        source_url=(
            "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
            "?sectionNum=6400.&lawCode=BPC"
        ),
        retrieved_at=_SEED_TS,
        scraper_version=_V,
    ),
    # ── 10. Washington Entity Regulation Pilot Project ───────────────────────
    # Resolves BOTH the IAALS "WA ABS" and "WA sandbox" listings as one program
    # (docs/sampling_frame.md §6) — same precedent as prog_ut_sandbox absorbing
    # UT's ABS listing. Do not add a second WA program row for either model type.
    Program(
        program_id="prog_wa_entity_pilot",
        jurisdiction="WA",
        program_name="Washington Entity Regulation Pilot Project",
        program_type=ProgramType.sandbox,
        regulator="Washington State Bar Association / Practice of Law Board",
        regulator_url="https://www.wsba.org/about-wsba/entity-regulation-pilot",
        authorizing_rule="Washington Supreme Court Order No. 25700-B-721 (Dec. 5, 2024)",
        launch_date=None,  # no entity yet granted authority as of this release
        program_status=ProgramStatus.active,
        # Order specifies the pilot ends 10 years after the FIRST entity is
        # authorized (not a fixed calendar date); unset until that happens.
        sunset_date=None,
        allows_nonlawyer_ownership=True,
        allows_upl_waiver=True,
        allows_software_provider=False,
        source_url="https://www.wsba.org/about-wsba/entity-regulation-pilot/applicants",
        retrieved_at=_SEED_TS,
        scraper_version=_V,
    ),
]

# ── runner ────────────────────────────────────────────────────────────────────


def main() -> None:
    _DB.parent.mkdir(parents=True, exist_ok=True)

    with RegistryStore(_DB) as store:
        store.init_schema()
        for prog in PROGRAMS:
            store.upsert_program(prog)
            print(f"  upserted: {prog.program_id}")

    print(f"\n{len(PROGRAMS)} programs seeded.\n")

    # Print summary table
    _print_table()


def _print_table() -> None:
    import duckdb

    con = duckdb.connect(str(_DB), read_only=True)
    rows = con.execute("""
        SELECT program_id, jurisdiction, program_type, program_status,
               launch_date, sunset_date,
               allows_nonlawyer_ownership, allows_upl_waiver, allows_software_provider
        FROM program
        ORDER BY launch_date NULLS LAST, program_id
    """).fetchall()
    con.close()

    hdr = (
        f"{'program_id':<20} {'jx':2} {'type':<24} {'status':<8}"
        f" {'launch':>10} {'sunset':>10}  own  upl  sw"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        pid, jx, ptype, pstatus, launch, sunset, own, upl, sw = r
        launch_s = str(launch) if launch else "TBD"
        sunset_s = str(sunset) if sunset else "—"
        print(
            f"{pid:<20} {jx:2} {ptype:<24} {pstatus:<8}"
            f" {launch_s:>10} {sunset_s:>10}"
            f"  {'Y' if own else 'N':3} {'Y' if upl else 'N':3} {'Y' if sw else 'N':3}"
        )


if __name__ == "__main__":
    main()
