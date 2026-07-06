"""Name normalization — deterministic, version-locked. See spec §3.2."""

from __future__ import annotations

import re
import unicodedata

# Dotted forms (p.c., l.l.c.) need lookaround instead of \b because \b
# doesn't fire after a trailing dot (non-word char → non-word char is not a boundary).
_SUFFIX_DOTTED = re.compile(
    r"(?<!\w)(pllc|l\.l\.c\.|l\.l\.p\.|p\.c\.|llc|llp|ltd|inc|co|pc)(?!\w)",
    re.IGNORECASE,
)
_SUFFIX_CLEAN = re.compile(
    r"\b(pllc|llc|llp|ltd|inc|co|pc)\b",
    re.IGNORECASE,
)

NORMALIZE_VERSION = "1"


def normalize_name(name: str) -> str:
    """Return a deterministic normalized form of a provider legal name.

    Steps (per spec §3.2):
    1. Strip Unicode accents, lowercase.
    2. Substitute & → and before punctuation is removed.
    3. Remove corporate suffixes (dotted forms, e.g. p.c., l.l.c.).
    4. Strip remaining punctuation, collapse whitespace.
    5. Remove corporate suffixes again (clean forms remaining after step 4).
    6. Drop leading "the".
    """
    # 1 — unicode + lowercase
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.lower()

    # 2 — & → and (before punctuation stripping destroys the ampersand)
    name = re.sub(r"\s*&\s*", " and ", name)

    # 3 — suffixes while punctuation is still intact (catches p.c., l.l.c.)
    name = _SUFFIX_DOTTED.sub(" ", name)

    # 4 — strip punctuation, collapse whitespace
    name = re.sub(r"[^\w\s]", " ", name)
    name = " ".join(name.split())

    # 5 — suffixes again for clean forms left after punctuation stripping
    name = _SUFFIX_CLEAN.sub(" ", name)
    name = " ".join(name.split())

    # 6 — leading "the"
    name = re.sub(r"^the\s+", "", name)
    name = " ".join(name.split())

    return name
