# homebrew-tap

A [Homebrew](https://brew.sh) tap for the command line tools of [pkalin](https://github.com/pkalin). It holds only formulas; the code of each tool stays in its own repository.

| Formula | Tool | Source |
| --- | --- | --- |
| `kubectl-shadewright` | kubectl plugin for the Shadewright Kubernetes operations agent | [pkalin/shadewright](https://github.com/pkalin/shadewright) |

## Install

```bash
brew tap pkalin/tap
brew install pkalin/tap/kubectl-shadewright
kubectl shadewright version
```

Works on macOS and Linux (amd64 and arm64). A formula appears here only once its repository has a release with binaries; until then `brew install` reports that the formula does not exist.

## Verification

Each formula downloads the release archive for your OS and architecture and Homebrew checks its **sha256**, which the formula pins. The digests come from the `checksums.txt` of the release. That protects against a corrupted or swapped download, but not against a compromised release: the checksum file is published by the same workflow as the archive.

Signatures and build provenance are verified with the GitHub CLI, as documented in each tool's repository (for `kubectl-shadewright`, the install page of the Shadewright docs), for example:

```bash
gh attestation verify <archive> --repo pkalin/shadewright
```

## How the formulas are kept current

`tools.json` lists every tool: name, GitHub repository, tag pattern (only matching, non-pre-release, non-draft releases count), archive name template, binary, test arguments, description, homepage and license. `scripts/bump.py` (Python 3, standard library only) reads the latest release through the public GitHub API, downloads `checksums.txt` as text (nothing downloaded is executed), validates versions and digests strictly and renders `Formula/<name>.rb` from `templates/formula.rb.tmpl`. If the latest release has no matching assets, it writes nothing. Never edit a formula by hand: change `tools.json` or the template.

The `Bump formulas` workflow runs daily and on demand, with `GITHUB_TOKEN` only (no secret, no access to other repositories), and opens or updates one pull request per formula on the branch `bump/<name>`. The repository setting "Allow GitHub Actions to create and approve pull requests" must be on.

Pull requests created with `GITHUB_TOKEN` do not trigger other workflows, so the bump job starts `Check formulas` on its branch itself (workflow_dispatch) and assigns the pull request to the repository owner. Merge when it passes: on macOS and Linux runners it taps the repository, runs `brew audit --strict --online`, installs from the formula and runs `brew test`. The same workflow runs on every push to `main` that touches a formula.

## Adding a CLI

1. The tool's repository publishes release archives named by a stable template and a checksums file in the release.
2. Add an entry to `tools.json` (copy `kubectl-shadewright`).
3. Run `python3 scripts/bump.py --tool <name>` to render the formula, or wait for the daily workflow.
4. Open a pull request (`feat(formula): add <name>`), run `Check formulas` on it and have it reviewed.

## Development

```bash
python3 -I -m unittest discover -s tests   # offline tests with fixtures
actionlint && zizmor .github/workflows     # workflow lint
```

See [AGENTS.md](AGENTS.md) for the rules. Licensed under Apache-2.0.
