# Working rules for AI coding agents

Read SPEC.md first. It is the source of truth for scope, method and priorities.

## Privacy (non-negotiable)

- This repository is public. Never commit a real person's house data, address, name, location more specific than a weather station, or measurements from a real home.
- Real project files live outside the repo or under `private/`, which is git-ignored. Never move anything from `private/` into tracked files, tests, examples or commit messages.
- Commit author: `BrackishEngineer <357033278+BrackishEngineer@users.noreply.github.com>`. Never use any other name or email.

## Engineering rules

- The calculation engine (`core/`) is Python and is the only place load math lives. The interface never re-implements a calculation.
- Port design-load logic from OpenStudio-HPXML (`HPXMLtoOpenStudio/resources/hvac_sizing.rb`). Keep its BSD notice in ported files, cite the source function in a comment, and tag every numeric table value with its origin.
- Never copy values from the Manual J book. Never call the tool "Manual J" or claim ACCA compliance.
- Every equation gets a test with a hand-calculated expected value, with units in variable names or comments (Btu/h, ft2, F, CFM).
- A change to load math is not done until the reference comparison in `validation/` still passes: totals within 2%, components within 5%. If it can't pass, record the gap and its cause in `validation/RESULTS.md`; never loosen the tolerance silently.
- Mark anything unverified `[CONFIRM]` in code comments and docs rather than guessing.

## Working style

- Small commits with plain-language messages saying what changed and why.
- When usage or time runs low, stop at a passing state, commit, and write the next steps in `NEXT.md`.
