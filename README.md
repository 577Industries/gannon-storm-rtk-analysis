# gannon-storm-rtk-analysis

[![CI](https://github.com/577Industries/gannon-storm-rtk-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/577Industries/gannon-storm-rtk-analysis/actions/workflows/ci.yml) [![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI](https://img.shields.io/pypi/v/gannon-storm-rtk-analysis.svg)](https://pypi.org/project/gannon-storm-rtk-analysis/)

> Retrospective analysis of RTK-GNSS positioning error during the May 10-12, 2024 Gannon G5 superstorm. Pulls NGS CORS RINEX for Iowa, Illinois, Indiana, and Ohio; computes per-station positioning error envelopes and correlates with NOAA SWPC indices and proton flux. Reproducible notebooks + blog post + result figures.

## Status

This repository is part of the **HELIOS** program — a NASA SBIR Phase I effort by
577 Industries Inc. supporting subtopic SPWX.1.S26A (Advanced Data-Driven
Applications for Space Weather R2O2R). See proposal §1.3 (Gannon case study) + §2 Obj. 4 (GNSS slice) of the proposal.

**Initial scaffolding committed 2026-05-17. Implementation in progress.**
Open issues to comment on the design or propose contributions.

## Quickstart

```bash
pip install gannon-storm-rtk-analysis
```

```python
import gannon_analysis
print(gannon_analysis.__version__)
```

## Documentation

- **Master plan**: see [`helios-program`](https://github.com/577Industries/helios-program) (private; internal team)
- **Specification**: docs published at the project's docs site when available
- **Provenance**: every output traces to its upstream model and transformation chain
  via [`helios-provenance-spec`](https://github.com/577Industries/helios-provenance-spec)

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Substantive changes should be discussed in an issue first.

## Citation

```bibtex
@software{helios_gannon_storm_rtk_analysis,
  author       = {Waweru, Thomas and 577 Industries Inc.},
  title        = { gannon-storm-rtk-analysis: Retrospective analysis of RTK-GNSS positioning error during the May 10-12, 2024 Gannon G5 superstorm },
  year         = {2026},
  publisher    = {577 Industries Inc.},
  url          = {https://github.com/577Industries/gannon-storm-rtk-analysis},
}
```
