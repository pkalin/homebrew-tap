# homebrew-tap: guide for coding agents

A general Homebrew tap (`brew tap pkalin/tap`) for the maintainer's command line tools. It holds formulas only; each tool's code and releases live in its own repository. The first formula is `kubectl-shadewright` (from `pkalin/shadewright`).

## Layout

- `tools.json`: the one list of tools (name, GitHub repo, tag pattern, asset name template, platforms, binary, test arguments, description, homepage, license). Every field is validated strictly by the script.
- `templates/formula.rb.tmpl`: the formula template (`on_macos`/`on_linux` with `on_arm`/`on_intel`, `url` + `sha256`, `bin.install`, `test do`).
- `scripts/bump.py`: Python 3 standard library only. Reads the latest non-pre-release through the public GitHub API, downloads the checksums file, renders `Formula/<name>.rb`. Prints `<name> <version|-> <written|unchanged|none>`.
- `Formula/`: generated formulas. Absent until a release with binaries exists. Do not edit by hand.
- `tests/`: offline tests with fixtures (`tests/fixtures/`); no network.
- `.github/workflows/`: `bump.yml` (daily and manual, opens one PR per formula), `check.yml` (brew audit, install, test; manual and on push to `main`), `test.yml` (script tests), `pr-title.yml`.

## Rules

- `main` is protected: changes only through pull requests. Never push to `main`, never change repository settings or rulesets.
- Never execute downloaded content. Release assets and `checksums.txt` are data: validate versions (`^[0-9]+\.[0-9]+\.[0-9]+$`) and digests (64 lower-case hex) before use, and build URLs from validated parts only.
- Formulas pin sha256 of every archive. Signatures and provenance (`gh attestation verify`) are documented in each tool's repository; do not claim the formula verifies more than sha256.
- Workflows: `permissions: {}` at the top, the minimum per job, only `GITHUB_TOKEN` (no secrets, no PAT), actions pinned by full commit SHA with the version in a comment, no untrusted input (release names, tags, PR text) interpolated into shell. Pull requests opened with `GITHUB_TOKEN` do not trigger workflows, hence the manual `check.yml`.
- Adding a tool means a `tools.json` entry; do not write a formula by hand or add per-tool code paths to the script.
- Everything committed is public and in English. No emails, local paths, personal IDs or secrets.

## Checks

```bash
python3 -I -m unittest discover -s tests   # offline tests
actionlint && zizmor .github/workflows     # workflow lint
brew audit --strict --online pkalin/tap/<name>   # when a formula exists (check.yml does this in CI)
```

Scripts need to run on macOS and Linux with only Python 3. Add or update tests with every change to `scripts/` or `templates/`; a new test must fail without its fix.

## Commits

Every commit on `main` follows [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/): `type(scope)!: summary`. Pull requests are squash-merged with the pull request title as the commit message; the `Conventional PR title` check validates it.

- Types: `feat`, `fix`, `perf`, `refactor`, `test`, `docs`, `build`, `ci`, `chore`, `revert`.
- Scope is optional; when used it is one of: `formula`, `ci`, `docs`, `deps`.
- Summary in English, imperative, starting lower case, no full stop: `feat(formula): add kubectl-shadewright`.
- Automated bumps use `chore(formula): bump <name> to <version>`.

## Working agreement

- Every change goes through a branch and a pull request; keep them small and say why in the description.
- Run the checks above before opening a pull request and read the diff once more for secrets and personal data.
- Prefer boring, well-known solutions over new dependencies or clever code.
