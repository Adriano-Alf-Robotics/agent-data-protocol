# Contributing to ADP

Thank you for your interest in contributing to the Agent Data Protocol!
This guide will help you get started.

## Development setup

ADP requires Python 3.11+ and uses [uv](https://docs.astral.sh/uv/) as
package manager.

```bash
git clone https://github.com/AdrianoDalPastro/agent-data-protocol.git
cd agent-data-protocol
uv sync --all-extras
```

## Running tests

The test suite must stay green before any commit:

```bash
uv run pytest -q          # all 244 tests
uv run pytest -v -k test_name  # single test
```

## Code style

- No formatter is enforced; follow the existing code style.
- Public API identifiers in English.
- Docstrings: English for user-facing modules, Italian is acceptable for
  internal modules and tests.
- No new runtime dependencies in `src/adp/` core without discussion.
  Optional imports use `try/except ImportError` fallback.

## Making changes

1. **Fork and branch.** Create a feature branch from `main`.
2. **Write tests first.** TDD is strongly preferred: red, green, refactor.
3. **Keep commits focused.** One logical change per commit.
4. **Run the full suite** before pushing: `uv run pytest -q`.
5. **Open a pull request** against `main` with a clear description of
   what changed and why.

## What to work on

- Check open issues for bugs and feature requests.
- The [Roadmap](README.md#roadmap) lists planned features.
- Documentation improvements are always welcome.

## Design documents

For non-trivial features, write a design spec before implementation:

- Spec: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Plan: `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`

Follow existing documents as reference for structure and level of detail.

## Benchmarks

If your change touches encoder, decoder, or session logic, re-run the
benchmarks and commit updated results if numbers shift more than ~2%:

```bash
uv run --with toon-py --with tiktoken python -m benchmarks.bench_comprehensive
```

## License

By contributing, you agree that your contributions will be licensed under
the MIT License.
