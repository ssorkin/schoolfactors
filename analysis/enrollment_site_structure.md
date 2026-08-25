# /enrollment family — structure and scope of work

Plan of record for the county-centric restructure (2026-08-25), grounded in
`enrollment_findings_groundwork.md` (F1–F7) and the reviewer feedback. Six
pages, three deployable phases.

**Status: all three phases implemented 2026-08-25** (same session). Notable
deltas from plan: the inline remote-share sparkline in the findings section
was cut (rendered as visual noise); validation stats are exposed via shared
helpers in `quality/checks.py` (`doc_validation_stats`,
`popest_control_stats`, `lausd_regression_stats`) so the DQ report and
`validation.json` cannot disagree; county boundaries are dissolved from the
K-8 district partition by administrative county (no new TIGER acquisition);
the findings block is prerendered into the landing HTML via a minimal
`+page.server.js` (full index stays client-fetched).

## Page family

```
/enrollment                      county-centric landing: thesis, findings, county map
/enrollment/county/[cds]         primary analytic surface (exists; promoted)
/enrollment/district/[cds]       local-market page (exists; trimmed & renamed)
/enrollment/districts            statewide district map (demoted landing map)
/enrollment/programs             remote-program dataset + nonlocality table (new)
/enrollment/methodology          + "How we check the model" section (extended)
```

Terminology everywhere: **"net enrollment balance (modeled)"** is the formal
noun; "net importer/exporter" is interpretive shorthand on a second line.
URL hash keys (`m`, `b`, `y`) stay stable.

## 1. /enrollment (landing)

Order of the page:

1. **Thesis lede** (~3 sentences): enrollment does not map onto the
   geography of children — interdistrict attendance, charter draw, and a
   growing remote sector; the state is the only boundary where the
   accounting closes (the LAUSD-only lesson, stated explicitly).
2. **"What the statewide accounting shows"** — 4–5 takeaways rendered from
   a computed `findings` export block (never hand-written numbers):
   - F4: remote sector 81k → 238k seats (1.3% → 4.1%) 2009→2024, grew every
     window; small inline share-of-state sparkline.
   - F1/F5: most districts (68% within survey margin) and counties (42/58
     within ±2%) are near balance.
   - F2: 87 persistent importers vs 30 persistent exporters across three
     non-overlapping windows.
   - F3/F6: administrative vs. physical — a district can administer 10–50×
     its resident base (Maricopa 51×); the model separates the two.
   - Nets-not-pairs principle, linking to methodology §"why nets".
3. **County choropleth** (new FlowMap mode or component): county net
   balance, remote-attribution share, alignment share, resident change;
   vintage slider kept; **no grade-band toggle**. Click → county page.
4. Search box (districts + counties), links to /enrollment/districts,
   /programs, /methodology.

Compat shim: if the incoming hash carries the old district-map params,
client-redirect to `/enrollment/districts` with the same hash.

## 2. /enrollment/county/[cds]

Structure unchanged (it already carries the analytic load). Deltas:
subtitle "Where the county's public enrollment is administratively
counted"; headline restructured metric-first ("Net enrollment balance:
+X% · modeled net importer"); one persistent model badge replaces repeated
MethodNotes (keep only the ChannelStack allocation note); Similar-Student
line on NetImportChart behind a default-off toggle; link from the remote
tables to /programs.

## 3. /enrollment/district/[cds]

Subtitle "Movement within the local public-school market". Same badge and
note-trimming treatment (keep ChannelStack note + one-line NeighborList
note). Perf overlay default off. New: **nonlocality stat line** when the
district's window-matched ratio ≥ 1.5 ("administers N× its resident base"),
upgrading the qualitative authorizer warning; links to /programs.

## 4. /enrollment/districts

The current landing map verbatim minus the lede: full metric switcher,
band toggle, year slider, legend, "reading this map" bullets. One-line
intro pointing back to landing and county pages.

## 5. /enrollment/programs  (new)

1. Intro: the remote sector, and the three classification routes ranked by
   epistemic strength — SBE NCB determination (strongest), CDE virtual flag
   (known lower bound, see known_issues), arithmetic backstop (ours).
2. **Program table** (FacetFilter reuse): program (school link), authorizer
   district + county, window-mean seats, basis, footprint size, enrollment
   trend sparkline, Similar Student %ile. Facets: basis, county. Row
   drill-in: balanced county-of-residence distribution (labeled "balanced
   estimate", not sortable, per no-illustrative-allocations discipline).
3. **Nonlocality table** (F6): administered seats ÷ resident children,
   window-matched; ranked, res ≥ 200 floor; distribution context line
   (median 0.95) so the tail reads as the exception. Table, not choropleth.

## 6. /enrollment/methodology

- §5 gains the why-statewide boundary paragraph.
- New section **"How we check the model"**: closure invariant (this build's
  value), ACS-vs-popest ratios, matched-pair stability across vintages
  (LA→Orange 13 vintages), LAUSD regression anchor, District of Choice
  validation (69% adjacent, direction agreement) with a small figure;
  Placer worked example — the model declines to call alignment "students".
  Check values come from an exported `validation.json`, not prose claims.

## Pipeline scope (export/flows)

1. County rows in the index get net_rate, spark series, remote share,
   alignment share, res_chg (landing choropleth).
2. `findings` block in index export: F1 shares, F2 counts, F4 series by
   kind + top counties, F5 pairs + flow/alignment split, F6 distribution +
   top entries **window-matched**, F7 anchor.
3. `programs.json`: per-program rows (series, basis, footprint, balanced
   shares) + nonlocality table.
4. `validation.json` from quality checks for the methodology figures.

## Phases (each deployable)

- **A — rename & trim** (site only): terminology, badges, subtitles, perf
  toggles, why-statewide paragraph. Small.
- **B — landing pivot**: county metrics + findings block in export; new
  landing; /enrollment/districts; redirect shim. Medium; the findings
  template copy is the careful part (house style: accounting language,
  never behavioral claims).
- **C — new surfaces**: programs.json + /programs; validation.json +
  methodology section; district nonlocality stat line. Medium.

Out of scope, permanently: pairwise district flow estimates.
