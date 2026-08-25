# Statewide findings groundwork — /enrollment restructure

Empirical pass over the flow-model outputs (2026-08-25) to determine which
candidate "what we learned statewide" takeaways the data actually supports,
ahead of the county-centric landing-page restructure. All numbers from
`data/parquet/analysis/*` at vintage 2024 (ACS window 2020–2024, m = 4.67%)
unless noted. Script: session scratchpad `findings_analysis.py` /
`findings_refine.py`; the shipping version of these numbers must be computed
in `enrollment_export.py` as a `findings` block, never hand-copied.

## Verified findings

**F1 — Most districts are near balance.** Of 938 districts with a modeled
net, 68% are within their own survey margin of zero (73% among the 622 with
≥500 resident children). 61% of resident public-school children live in a
district with |net| ≤ 5%. Supports the "mostly balanced" takeaway with
either framing (count or resident-weighted).

**F2 — Persistent imbalances exist; the apparent asymmetry was a
small-district artifact.** Across three non-overlapping windows (2010–14,
2015–19, 2020–24; 933 districts present in all three), 87 districts were
significant net importers in all three and 30 significant net exporters —
but *(correction, 2026-08-25, found while building the balance table)* the
87 is dominated by micro-districts (a handful of resident children, schools
serving far wider areas: +500%-style rates the survey cannot support).
Requiring the map's ±15pp reliability gate in every window, the base is 368
districts and the counts are 22 persistent importers vs 24 persistent
exporters — no asymmetry. The shipped findings and the landing copy use the
gated numbers; do not write the asymmetry claim.

**F3 — "Giant importers dissolve when virtual is removed" holds only in the
tail; reframe as administrative vs. physical.** Among districts with ≥500
residents, 66 have a naive rate (virtual programs left in physical
geography) above +25%, but 42 of them remain above +25% after modeling —
genuine physical importers. The dramatic cases are tiny authorizers:
Acton-Agua Dulce (naive +896% → modeled −15%), Lucerne Valley (+822% → −9%),
Helendale (+697% → −25%); below the floor, Maricopa Unified administers
~16.7k seats against 313 resident children (51×), Dehesa, Oro Grande, etc.
The correct takeaway merges this with F6: administrative enrollment can be
10–50× a district's resident base, and the model's job is separating
administrative bookkeeping from physical attendance.

**F4 — The remote sector tripled and is now 4.1% of statewide enrollment.**
Remote pool (virtual + nonclassroom): 81k seats = 1.3% (2009) → 154k = 2.5%
(2017) → 238k = 4.1% (2024); grew every single window, including
post-pandemic while statewide enrollment fell. Kinds at 2024: NCB
determinations 117.5k across 226 programs, CDE virtual flag 108.7k across
107, ratio-backstop 12.0k across 26. Concentration: 46 authorizing counties;
top 5 (San Diego, LA, San Bernardino, Riverside, Kern) hold 54% of remote
seats; the top 10 *programs* hold only 23% — a many-program sector with
concentrated authorizers, not a few-program story.

**F5 — Counties are mostly balanced; the exceptions decompose cleanly.**
42 of 58 counties are within ±2%. Gross county residual splits 56% matched
adjacent flow / 44% survey-administrative alignment (not students). Largest
stable matched pairs: LA→Orange (~3.5k), San Bernardino→Riverside (~3.3k),
Santa Clara→Alameda (~2.1k); top 5 pairs carry 59% of all matched
cross-county flow (70 pairs total). Placer (+12.2%, entirely alignment) is
the marquee *validation* case: the model refuses to call it students —
verified this session that Horizon Charter IS classified (ncb, 1.8k seats;
its directory class charter_bm is overridden by the NCB match), so the
residual is the documented ACS growth-lag, not a classification miss.

**F6 — Nonlocality ratio (admin enrollment ÷ resident children) works as
predicted.** Median 0.95, IQR 0.85–1.12, so ~1 for ordinary districts; 65
districts >1.5, 16 >3, 4 >10. Top: Maricopa 51×, New Jerusalem 21×, Lucerne
Valley 11.4×, Acton-Agua Dulce 10.8×, Newcastle 10.0×. Among large districts
(≥5k residents): West Covina 1.73, Walnut Valley 1.69, Beaumont 1.63 —
mostly virtual-authorizing hosts. Ranked table is clean; a choropleth would
be dominated by the 10× tail, confirming the table-not-map decision.
Implementation note: this pass used spring-2026 seats against the 2020–24
resident window — the export version must window-match (window-mean admin
seats over the same springs as the ACS window). *Shipped (2026-08-25): the
window-matched export gives median 0.99, Maricopa 40.5×, New Jerusalem
17.6×, 16 districts >3×, 2 >10× — same shape, slightly tamer tail.*

**F7 — LAUSD anchor.** 2020–24: net −13.0k (−2.3% of 565.6k residents),
consistent with the published LAUSD story's magnitude.

## Consequences for the build

- `findings` block in the index export: F1 shares, F2 counts, F4 series
  (pool by kind + share of state), F5 pair list + flow/alignment split, F6
  distribution + top entries, F7 anchor. Landing takeaways template from it.
- Landing copy: lead with F4 (growth) and F1/F5 (mostly balanced), then
  F3/F6 (administrative vs. physical, with Maricopa/Acton-Agua Dulce as the
  named examples), close with the nets-not-pairs principle.
- Reviewer conjecture "apparent giant importers disappear once virtual is
  removed" is NOT supported as stated (42/66 persist) — do not write it.
  The administrative/physical separation framing is supported.
- Placer belongs in the validation panel (model declines to invent
  students), not in a "findings" bullet.
- /enrollment/programs page: F4 kinds/counts are the filter facets; F6 is
  the ranked nonlocality table on the same page.
