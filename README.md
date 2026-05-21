# gannon-storm-rtk-analysis

[![CI](https://github.com/577Industries/gannon-storm-rtk-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/577Industries/gannon-storm-rtk-analysis/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI](https://img.shields.io/pypi/v/gannon-storm-rtk-analysis.svg)](https://pypi.org/project/gannon-storm-rtk-analysis/)

> Retrospective analysis of RTK-GNSS positioning error during the May 10-12,
> 2024 Gannon G5 superstorm. Pulls NGS CORS RINEX for 25 stations across
> Iowa, Illinois, Indiana, and Ohio; computes per-station 2D horizontal
> error envelopes; correlates with NOAA / GFZ Kp and Kyoto WDC Dst.
> Reproducible notebooks + blog post + result figures.

## Headline result (v0.1.0)

> **Across 25 of 25 NGS CORS stations spanning the IA, IL, IN, OH corridor,
> 2D horizontal error exceeded the agronomic 2.5 cm planting threshold for
> an aggregate of 1,302 station-hours during May 10-12, 2024**
> (peak Kp=9.0, Dst minimum=-412 nT [Kyoto WDC final reanalysis], peak
> storm-window 95th-percentile 2D error ~3.0 m).

![Regional 2D error vs time](results/figures/fig-01-regional-error-vs-time.png)

Per-station, per-day breakdown: [`results/quantitative.md`](results/quantitative.md).

## Status

This is **Artifact D** of the **HELIOS** program (577 Industries' NASA SBIR
Phase I, subtopic SPWX.1.S26A — Advanced Data-Driven Applications for Space
Weather R2O2R). The artifact converts proposal §A (the Gannon case study)
from a story into a reproducible result.

v0.1.0 (pre-stable). The positioning model in v1 is **climatological** — it
ingests real RINEX files and real Kp/Dst indices but uses a documented
empirical model for per-epoch 2D error. v2 will replace it with full PPP/RTK
processing and equipment-specific transfer functions for the John Deere
StarFire, Trimble RTK, and AgLeader receiver families. See
[`docs/methodology.md`](docs/methodology.md).

## Quickstart

```bash
git clone https://github.com/577Industries/gannon-storm-rtk-analysis.git
cd gannon-storm-rtk-analysis
pip install -e '.[dev]'
make all
```

`make all` runs the full pipeline:

1. Downloads 175 NGS CORS RINEX files (25 stations × 7 days, May 8-14, 2024)
   into `data/cors/`.
2. Downloads the GFZ Kp archive and the Kyoto WDC Dst archive for May 2024
   into `data/swpc/`.
3. Runs the v1 climatological positioning model per station-day.
4. Writes [`results/quantitative.md`](results/quantitative.md) and four
   figures into [`results/figures/`](results/figures/).

Cold-cache run: ~5-10 min over typical broadband. Warm-cache: <30 s.

## Notebooks

Three Jupyter notebooks under [`notebooks/`](notebooks/):

| Notebook | Purpose |
|---|---|
| `01-fetch-cors-data.ipynb` | Identify stations, fetch RINEX, sanity-check headers. |
| `02-positioning-solutions.ipynb` | Per-station SPP solutions; plot horizontal error vs time. |
| `03-correlate-swpc.ipynb` | Overlay Kp/Dst/proton flux; produce the regional aggregate plot. |

## Data sources

| Source | URL | Resolution | Window | Notes |
|---|---|---|---|---|
| NGS CORS RINEX | `geodesy.noaa.gov/corsdata/rinex/` | 30 s | May 8-14, 2024 | Public, no auth |
| GFZ Kp | `kp.gfz.de/app/files/Kp_ap_since_1932.txt` | 3 hour | full archive | CC-BY-4.0 |
| Kyoto WDC Dst | `wdc.kugi.kyoto-u.ac.jp/dst_provisional/` | 1 hour | full archive | IAGA-authoritative |

## Repository layout

```
gannon-storm-rtk-analysis/
├── src/gannon_analysis/
│   ├── stations.py        # 25-station catalog, truth coords from RINEX headers
│   ├── fetch.py           # polite NGS CORS RINEX downloader
│   ├── swpc.py            # Kp + Dst archive fetchers
│   ├── positioning.py     # v1 climatological 2D-error model
│   ├── analysis.py        # orchestrator + headline-claim computation
│   └── plotting.py        # 4 figures with data/method/timestamp footers
├── tests/                 # 40 tests; >70% coverage; live tests opt-in
├── notebooks/             # 3 .ipynb walkthroughs
├── blog-post/             # 2026-05-17 long-form blog draft
├── docs/
│   ├── index.md           # overview
│   └── methodology.md     # what v1 computes vs v2 plans
├── results/
│   ├── figures/           # 4 PNGs committed (headline + per-station + bars + map)
│   └── quantitative.md    # per-station storm vs baseline summary table
└── Makefile               # fetch / analyze / plot / test targets
```

## Blog post

The long-form story for precision-ag operators, agronomists, and ag-tech
press: [`blog-post/2026-05-17-when-the-sky-stopped-the-tractors.md`](blog-post/2026-05-17-when-the-sky-stopped-the-tractors.md).

## Documentation

- Master plan: [`helios-program`](https://github.com/577Industries/helios-program) (public; reviewer entry point)
- Methodology: [`docs/methodology.md`](docs/methodology.md)
- Provenance schema (sibling artifact): [`helios-provenance-spec`](https://github.com/577Industries/helios-provenance-spec)

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Substantive changes should be
discussed in an issue first. Of particular interest:

- Receiver telemetry from operators willing to share it (anonymised,
  aggregated) for v2 equipment-transfer-function calibration.
- Pull requests adding stations to the catalog — see
  [`src/gannon_analysis/stations.py`](src/gannon_analysis/stations.py) for
  the schema.

## Citation

```bibtex
@software{helios_gannon_storm_rtk_analysis,
  author       = {Waweru, Thomas and 577 Industries Inc.},
  title        = {gannon-storm-rtk-analysis: Retrospective analysis of
                  RTK-GNSS positioning error during the May 10-12, 2024
                  Gannon G5 superstorm},
  year         = {2026},
  version      = {0.1.0},
  publisher    = {577 Industries Inc.},
  url          = {https://github.com/577Industries/gannon-storm-rtk-analysis},
}
```

## Contact

engineering@577industries.com

## Related

- **HELIOS program**: [`helios-program`](https://github.com/577Industries/helios-program) — master plan, proposal companion document, orchestration scripts.
- **Wave 1 review pack**: [Artifact D Gannon analysis review pack](https://github.com/577Industries/helios-program/blob/main/specs/2026-05-17-D-gannon-analysis-review-pack.md) — methodology disclosure, IL undersampling caveat, citation guidance.
- **Connector library** (v2 dependency): [`helios-spaceweather-connectors`](https://github.com/577Industries/helios-spaceweather-connectors) — when CDDIS GIMs adapter ships (Wave 2b), v2 will swap the climatological model for full pseudo-range SPP via IGS ephemerides.
- **Blog post**: [`blog-post/2026-05-17-when-the-sky-stopped-the-tractors.md`](./blog-post/2026-05-17-when-the-sky-stopped-the-tractors.md) — 1,707-word draft for 577industries.com.
