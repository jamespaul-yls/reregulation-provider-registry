"""Scraper for D.C. Rules of Professional Conduct Rule 5.4(b).

Source: https://www.dcbar.org/For-Lawyers/Legal-Ethics/Rules-of-Professional-Conduct/Law-Firms-and-Associations/Professional-Independence-of-a-Lawyer
Fetch strategy: StaticFetcher — static HTML rule page.

Background:
  D.C. Rule 5.4(b) (eff. Jan. 1, 1991) allows nonlawyer ownership of law firms whose
  sole purpose is providing legal services, making DC the first U.S. jurisdiction to
  permit ABS-style nonlawyer ownership. Unlike the ABA Model Rule 5.4, DC's version
  explicitly permits a "partnership or other form of organization in which a financial
  interest is held or managerial authority is exercised by an individual nonlawyer who
  performs professional services which assist the organization in providing legal services
  to clients" — subject to four conditions (sole legal-services purpose; all owners bound
  by RPC; lawyer accountability; written statement of conditions).

Why provider count is zero:
  Rule 5.4(b) is a permissive ethics rule, not an authorization program. There is no
  registration requirement, no application process, and no roster maintained by the DC
  Court of Appeals or DC Bar. Entities may operate under Rule 5.4(b) without notifying
  any regulator. A v2 effort could survey secondary sources (NALP, press, litigation) to
  enumerate known Rule 5.4(b) firms, but no authoritative roster exists.

The statute page is snapshotted to detect future rule amendments.
"""

from __future__ import annotations

from models.schema import Provider, SourceSnapshot
from scrapers.base import BaseScraper
from scrapers.fetchers import StaticFetcher

_RULE_URL = (
    "https://www.dcbar.org/For-Lawyers/Legal-Ethics/Rules-of-Professional-Conduct"
    "/Law-Firms-and-Associations/Professional-Independence-of-a-Lawyer"
)


class DcRule54Scraper(BaseScraper):
    version = "0.1.0"
    program_id = "prog_dc_rule54"
    source_url = _RULE_URL
    default_fetcher_class = StaticFetcher

    def parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        # No registration roster exists for DC Rule 5.4(b) — the rule is permissive, not
        # a licensing scheme. Firms may self-organize under Rule 5.4(b) with no notice to
        # any regulator. Return empty list; extend if a secondary-source roster is built.
        return []
