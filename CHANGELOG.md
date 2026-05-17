# Changelog

All notable changes to this project are documented here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-17

### Added
- Reproducible retrospective of the May 10-12, 2024 Gannon G5 superstorm across **25 NGS CORS stations** in the IA/IL/IN/OH corridor.
- 25-station catalog with ITRF2014 truth coordinates derived from real day-131 RINEX headers.
- Fetchers: NGS CORS RINEX (175 real files cached for May 8-14 2024), GFZ Potsdam Kp (CC-BY-4.0), Kyoto WDC Dst.
- v1 positioning model is **climatological/empirical**, transparently disclosed in `docs/methodology.md` and the blog post. v2 will swap in full pseudo-range SPP via `helios-spaceweather-connectors` CDDIS adapter.
- **Headline**: 1,302 station-hours over the 2.5 cm planting threshold; 95th-percentile peak 3.0 m; ~150× quiet-period baseline.
- 40 tests at 80% line+branch coverage; `mypy --strict`, `ruff` clean.
- 1,707-word blog post draft: `blog-post/2026-05-17-when-the-sky-stopped-the-tractors.md`.
- 4 result figures committed (`results/figures/`) + per-station quantitative table (`results/quantitative.md`).

See [GitHub releases](https://github.com/577Industries/gannon-storm-rtk-analysis/releases/tag/v0.1.0) for the canonical release notes.
