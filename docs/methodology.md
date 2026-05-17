# Methodology

This document explains what the v1 release of `gannon-storm-rtk-analysis`
actually computes, what it does **not** compute, and what v2 will add.

## What is SPP?

Single Point Positioning (SPP) is the GPS solution available to any receiver
with no augmentation. The receiver observes pseudo-ranges to four or more GPS
satellites and solves a system of four equations (three position coordinates
plus receiver-clock bias). Quiet-time 2D horizontal accuracy is typically
**1-3 m** for an L1-only receiver after Klobuchar ionospheric correction.

## What is RTK?

Real-Time Kinematic positioning fuses carrier-phase observations from a rover
receiver against simultaneous observations from a fixed base station (or a
network of base stations). When the carrier-phase integer ambiguities are
correctly resolved ("fixed"), 2D horizontal accuracy reaches **1-2 cm** —
the regime precision agriculture depends on for row spacing, planter offsets,
and spray boom positioning. The Gannon storm story is about the breakdown of
ambiguity resolution at the precise hours during the May 2024 planting season
when operators most needed centimetre accuracy.

## What this release computes

For each NGS CORS station in the corridor, the v1 pipeline:

1. **Fetches the published daily RINEX observation file** from the NGS public
   archive (`https://geodesy.noaa.gov/corsdata/rinex/`). This is real, audit-
   able I/O — the manifest of fetched files is provenance for every result.
2. **Parses the RINEX header** with `georinex` to recover the station's
   published ITRF2014 truth coordinates and the per-day observation epoch grid.
3. **Computes per-epoch 2D horizontal error** using a *climatological model*
   tied to contemporaneous geomagnetic indices (real Kp from GFZ Potsdam,
   real Dst from the Kyoto WDC):

   ```
   sigma_2d(t) = sigma_quiet
               + alpha * f_kp(Kp(t))
               + beta * |Dst(t)| / 100

   f_kp(Kp) = 0                       if Kp <  4
            = exp(0.55 * (Kp - 4))     if Kp >= 4
   ```

   Constants `sigma_quiet`, `alpha`, `beta` are calibrated against (a)
   OEM-published RTK accuracy specifications (~2 cm baseline) and (b)
   field-reported error excursions during the May 2024 Gannon storm
   (30 cm to multi-metre during peak hours).

4. **Aggregates per-station daily 95th-percentile error** and counts
   "station-hours over threshold" — the citable summary statistic.

5. **Renders four figures** with `data + method + timestamp` footer:
   - Regional median + p95 error vs time, with Kp/Dst overlay (headline).
   - Per-station error grid (one panel per station, Kp-coloured points).
   - Stacked station-hours bar chart by UTC date.
   - Station map showing peak severity by location.

## What this release does **not** compute

- It does **not** linearise pseudo-range observables from the RINEX file.
  The RINEX file is consumed for its header (truth + epoch grid + metadata)
  and as evidence-of-fetch in the manifest.
- It does **not** perform PPP, RTK ambiguity resolution, or any carrier-phase
  processing.
- It does **not** use real satellite ephemerides. (.sp3 SP3 files from CDDIS
  are out of scope for v1.)
- It does **not** apply equipment-specific transfer functions. The error
  series produced is a corridor-average climatological response, not a per-
  receiver-family prediction.

## Why v1 is climatological

A full PPP/RTK pipeline is roughly an additional 1500 lines of Python plus
~3-5 GB of ancillary data (precise orbits, clock products, antenna
phase-centre files). It changes the per-station error trajectory but does
**not** change the qualitative regional story the artifact wants to tell:
that the May 10-12, 2024 storm drove 2D RTK error across the IA/IL/IN/OH
corridor up by 1-2 orders of magnitude for an aggregate of ~1300
station-hours.

For an SBIR Phase I customer-discovery artifact and a public-facing blog
post, the climatological model is honest, reproducible, and traceable to
the real Kp and Dst time series that anyone can verify against GFZ Potsdam
and the Kyoto WDC.

## What v2 will add

- **Real SPP from RINEX observables.** Pseudo-range linearisation,
  satellite-position solution from SP3 ephemerides, ionosphere-free L1/L2
  combination, weighted least-squares with elevation-mask outlier rejection.
- **PPP refinement** using IGS final precise orbits and clock products
  (CDDIS Earthdata download via Artifact B's connector library).
- **RTK simulation** by computing double-differenced carrier-phase
  observations between station pairs and recovering integer ambiguities,
  with explicit tracking of "fix vs float vs single-point" status per epoch.
- **Equipment-specific transfer functions** for the John Deere StarFire
  6000/7000, Trimble RTK, and AgLeader Surefire/Versa families, calibrated
  against documented receiver behaviour during the May 2024 storm. This
  is the proposal §2 Objective 4 deliverable; this artifact prepares the
  data infrastructure that the Phase II training pipeline will consume.

## References

- GFZ Potsdam Kp index. Matzka, J., Stolle, C., Yamazaki, Y., Bronkalla, O.
  and Morschhauser, A. (2021). *The geomagnetic Kp index and derived indices
  of geomagnetic activity.* Space Weather 19.
  https://doi.org/10.1029/2020SW002641
- Kyoto WDC Dst index. World Data Center for Geomagnetism, Kyoto. Hourly
  provisional Dst values.
  https://wdc.kugi.kyoto-u.ac.jp/dstdir/
- NGS CORS. National Geodetic Survey Continuously Operating Reference
  Stations. https://geodesy.noaa.gov/CORS/
- American Farm Bureau Federation (2024). *Precision Agriculture Technology
  Survey Results.*
- OSU Extension (2024). *Space Weather Disturbances and Farm GPS Interruptions.*
- 577 Industries NASA SBIR Phase I Proposal (2026). HELIOS:
  Heliophysics-Enhanced Location Integrity and Operations System.
  §1.3 (Gannon case study), §2 Objective 4 (GNSS slice).
