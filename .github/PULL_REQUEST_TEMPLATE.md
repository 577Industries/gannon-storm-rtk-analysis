## Summary

<!-- 1-3 sentences: what does this PR do and why. -->

## Related

- HELIOS master plan: <https://github.com/577Industries/helios-program/blob/main/plan/master-plan.md>
- Closes #
- Methodology disclosure: `docs/methodology.md` (v1 climatological boundary)

## Quality

- [ ] Tests added or updated
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `mypy --strict` passes (or `# type: ignore[...]` added with a justification)
- [ ] `pytest --cov` coverage threshold maintained
- [ ] CHANGELOG.md entry added under `[Unreleased]`
- [ ] Conventional-commit message in PR title (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`)
- [ ] Notebooks re-runnable from cold cache (`make all`)
- [ ] Result figures regenerated (`results/figures/`)
- [ ] Quantitative table updated (`results/quantitative.md`)
- [ ] Per-figure data/method/timestamp footer present

## Backwards compatibility

<!-- Any breaking changes to public API, JSON Schema, on-disk format, env vars? If yes, document the migration path. -->

## Provenance

- [ ] Any new data flow emits a `helios_provenance.HeliosModelOutputRecord` (or downstream equivalent) per the [provenance spec](https://github.com/577Industries/helios-provenance-spec).
