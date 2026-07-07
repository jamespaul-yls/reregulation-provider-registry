# Use of AI in building this dataset

**Author:** James Paul, Yale Law School

This project was built with AI-assisted coding (Claude Code, Anthropic) working from
specifications and instructions I authored. This note says plainly what that means in
practice, so readers can weigh the dataset on its actual process rather than guess at it.

## What AI did

Wrote scraper and pipeline code against the schema and rules in
`reregulation-registry-v1-spec.md` and `CLAUDE.md`; drafted and copy-edited documentation;
assisted with validation scripts.

## What AI did not do

Decide program scope, resolve ambiguous source-page structures, or sign off on data
accuracy. `CLAUDE.md` requires the assistant to stop and flag any case where a source
deviates from the spec's assumptions rather than guess — those calls, and all coverage/
accuracy judgments, are mine.

## Why this isn't a black box

The process leaves an audit trail, not just a claim of correctness:

- **Spec before code.** `reregulation-registry-v1-spec.md` was written before any scraper.
- **Working rules checked into the repo.** `CLAUDE.md` requires one playbook step at a
  time, a plan before non-trivial edits, and actual output shown (row counts, samples,
  reconciliation numbers) — not just a success message.
- **Every parser has a regression test** run against a saved snapshot fixture
  (`tests/`), independent of whatever the AI claims about its own output.
- **Every data-producing step self-reports coverage and accuracy** against the source's
  own totals, with hand-verified samples, logged in `validation/<source>.md`.
- **Adversarial review passes** are logged separately in `docs/audit/`.
- **Small, single-purpose commits** with conventional messages — see `git log`.

## Accountability

I am the dataset's author and am responsible for the scope decisions, methodology, and
published output. AI accelerated implementation; it did not make the empirical or
methodological judgment calls the dataset embodies.
