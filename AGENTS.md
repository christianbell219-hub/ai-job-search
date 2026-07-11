# AGENTS.md

## Cursor Cloud specific instructions

This repo is a **Claude Code-driven job application assistant template** — there is **no web server, GUI, or build step**. The "product" is the set of Claude Code skills/commands under `.claude/` and `.agents/`, plus three runnable, testable components:

- **Python tools** (`salary_lookup.py`, `tools/*.py`) — standard library only; tests in `tests/`.
- **Six Bun/TypeScript job-portal CLIs** under `.agents/skills/<tool>/cli/` (`freehire-search`, `linkedin-search`, and four Denmark portals).
- **LaTeX documents** — `cv/main_example.tex` (compile with `lualatex`) and `cover_letters/cover_example.tex` (compile with `xelatex`).

The Claude Code orchestrator itself (`claude`) is **not runnable here** — it needs an Anthropic API key/subscription. Test the three components above directly instead. Standard commands live in `README.md`, `SETUP.md`, `CONTRIBUTING.md`, and `.github/workflows/ci.yml`; don't duplicate them.

### Non-obvious caveats

- **Bun is not on the default non-interactive PATH.** The installer added `~/.bun/bin` to `~/.bashrc`, but scripts that don't source it must call `"$HOME/.bun/bin/bun"` explicitly (the update script does this).
- **LaTeX needs a newer `moderncv` than Ubuntu's TeX Live ships.** The templates use `\firstnamestyle`/`\lastnamestyle`, added after moderncv v2.3.1 (the apt version). Current `moderncv` (v2.6.1+) and its dependency `fontawesome6` are installed into `~/texmf` (`TEXMFHOME`) from CTAN during setup and persist in the VM snapshot — do **not** expect the apt `texlive-*` packages alone to compile the CV. If a future TeX error mentions `\firstnamestyle` undefined or `fontawesome6.sty` not found, re-install those two from CTAN into `~/texmf` and run `texhash ~/texmf`.
- **Compile the CV twice** so moderncv's page/last-page references settle; CI asserts the CV is exactly 2 pages and the cover letter exactly 1 page (upstream repo only).
- **`salary_data.json` is gitignored personal data** and absent by default. `salary_lookup.py` exits 1 with a helpful message when it's missing; `/apply` skips salary benchmarking gracefully. Create a small `{"metadata":{...},"companies":[...]}` file to exercise the tool.
- **CI runs no live portal requests** by design (ToS + flakiness); the CLIs are only typechecked and unit-tested in CI. Live `search`/`detail` queries need network. `jobnet-search` has no unit tests (expected).
- **`openpyxl`** (optional, for `tools/convert_salary_excel.py`) and `pdftotext`/poppler (optional, for the `/apply` ATS check) are the only optional extras; everything else degrades gracefully without them.

### Lint / test / run

- Lint + guards: `python3 tools/lint_skills.py` and `python3 tools/security_guards.py`.
- Python tests: `python3 -m unittest discover -s tests -t . -v`.
- Per-CLI (from `.agents/skills/<tool>/cli/`): `bun run typecheck` and `bun test`.
- Live CLI demo: `bun run src/cli.ts search -q "python engineer" --limit 5 --format table` (in `freehire-search/cli`).
- Compile docs: `cd cv && lualatex -interaction=nonstopmode main_example.tex` and `cd cover_letters && xelatex -interaction=nonstopmode cover_example.tex`.
