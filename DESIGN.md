# v31 — design record

## What v31 is

v31 starts from the v30 packaged cell and pushes in the direction the
last eight rounds all pointed: the median is the bottleneck, and the
disagreement shift is the only lever that keeps buying practice AND LOO
at the same time. v31 deepens that shift (0.60 + 0.20·size, late band
0.45), steepens the size pull-down (−0.04), the mid ramp (−0.14), the
early ramp (+0.045), the disagreement factor (k = 0.85), and the late
spread ramp (→ 0.84), tilts the mid median toward Y5 (0.6/0.4), and —
the new idea — routes the spread's size growth **through the
disagreement** instead of through raw size.

## Status — the packaged cell is real, the file is not

On the cached v29 member rows the packaged cell scores practice
**0.117532**, LOO-large **0.208604**, LOO-mega **0.210005**,
median-only **0.182041** — better than v30 (0.118710 / 0.209744 /
0.211400 / 0.184501) on all four, with LOO margins ~8× the v30
packaged cell's. But the `main.py` in this repo does **not** reproduce
the cached member rows (see "The member gap" below), so its direct
grade is practice **0.122963**, LOO **0.220231 / 0.223201** — worse
than v30. **This entry is not submittable and must not replace v30
(or v26, the submitted entry).** The combine cell is preserved here
for the next round, which should start from the member diagnosis
below — fixing the members is worth more than any further combine
tuning.

## Calibration (how the combine was validated)

Scoring the v30 cell from the cached rows reproduces v30 exactly
(0.118710 / 0.209744 / 0.211400) only with two conventions that were
ambiguous in the prose spec: the late spread ramp **replaces** the
0.975 base factor in the late band (it does not multiply on top), and
the disagreement sd is the **population** sd (ddof=0), not the sample
sd. Both are implemented that way in `main.py`.

## The search (all through `combine` on the cached v29 rows)

A cell passes only if it beats v30 on practice AND both LOO gates.

* **Phase 1 — idea 1 (deeper shift / slopes / ramps / k).** 576 cells
  (shift_base 0.40/0.45/0.50 × shift_slope 0.10/0.125/0.15 × k 0.80/0.85
  × mid ramp −0.12/−0.125 × early ramp 0.03/0.035 × late shift 0.35/0.40
  × late spread end 0.90/0.88 × size shift −0.02/−0.025). **212 cells
  passed all three gates.** Best practice 0.118159, but its LOO
  margins were thin; the best-margin cells sat near shift 0.5, slope
  0.15, k 0.85, mid −0.125, early 0.035, size −0.025.
* **Phase 2 — idea 2 (median levers).** On the phase-1 anchor: mid
  weight 0.4/0.5/0.6, late-4 median, early mix (0.5·Y1+0.5·Z0), band
  offsets. **mid_w = 0.6 passed with much better LOO margins**
  (+0.000458/+0.000496 at practice 0.118404); the early offset −0.01
  also passed (0.118294). late-4 and early-mix failed LOO. The
  mid-weight tilt (0.6·Y5 + 0.4·clone) is packaged. No other median
  source change passed both gates — the v30 conclusion stands, with
  this one exception.
* **Phase 3 — idea 3, wild (the spread–size tension).** v30 found a
  plain size slope on the spread buys LOO at the cost of practice,
  monotonically. Three routings were tried on the anchor: plain
  size-slope (a = 0.05/0.10/0.20), **W1 lower-side-only** size slope
  (a = 0.05/0.10/0.20/0.30), and **W5 size × disagreement interaction**
  `spread *= 1 + a·size·sd` (a = 0.5/1.0/2.0). W5 a = 1.0 passed with
  margins +0.001008/+0.001100 at practice 0.118533; W1 a = 0.1 passed
  at 0.118558 with margins +0.000750/+0.000826; plain a = 0.05 passed
  at 0.118638. **W5 resolves the tension**: size grows the spread
  only where the members already disagree, so the smooth practice
  cases pay almost nothing while the rough LOO launches get the width
  they need. W5 + W1 are both packaged.
* **Phase 4 — combining the winners.** 216 cells (mid_w 0.55/0.60/0.65
  × W5 0.5/1.0/1.5 × W1 0/0.05/0.10 × mid −0.125/−0.13 × size
  −0.025/−0.03 × early 0.03/0.035). **176 passed.** Best practice
  0.118198 (margins +0.000680/+0.000729); best margin 0.118666
  (+0.002350/+0.002483).
* **Phase 5 — pushing deeper with the W5 headroom.** 1,024 cells
  (shift 0.50/0.55 × slope 0.15/0.175 × k 0.85/0.90 × mid −0.13/−0.135
  × size −0.03/−0.035 × early 0.035/0.04 × late shift 0.35/0.40 × late
  spread 0.88/0.86 × four (mid_w, W5, W1) combos). Best practice
  **0.117946** (0.55/0.175/0.85/−0.135/−0.035/0.04/0.40/0.86/0.6/1.0/
  0.05), LOO 0.208469/0.209960, per-case 0.1074/0.1366/0.0780/0.1497 —
  better than v30 on three of four cases (p01 slightly worse, 0.1366
  vs 0.1355).
* **Phase 6 — micro-refinement + one deeper probe.** 33 cells around
  the phase-5 best, plus (0.60, 0.20, −0.14, −0.04, 0.045, 0.45, 0.84,
  W5 1.25). The deeper probe won again: **packaged cell practice
  0.117532, LOO 0.208604/0.210005, median-only 0.182041**, per-case
  0.1070/0.1366/0.0778/0.1488. The frontier had not flattened, but the
  parameters were getting extreme (shift 0.60 + slope 0.20 extrapolate
  to (0.60 + 0.20·2.7) ≈ 1.14·sd at the final lnV1 ~ 14.2), so the
  search stopped here rather than chase further depth on 4 practice
  cases.

## The member gap (why this file does not reproduce the sweep)

`main.py` was written from the v30 prose spec before any harness
existed. Its **clone member reproduces the cached rows almost
exactly** (practice sig max diff 0.00014; mu max diff 0.019, only at
p00, +0.006…+0.019 across hours) — so the OLS view (3-feature,
±2.5 window, median recenter, spread ×0.8, sample sd) and the shape
sig formula are right. But **Y5/Z0/Y1 do not reproduce**: practice mu
max diff 0.214 (y5), 0.206 (z0), 0.190 (y1); sig max diff 0.185 /
0.171 / 0.171. The direct grade of this file is therefore 0.122963 /
0.220231 / 0.223201 (the v30 cell on these same members scores
0.123498, so the member error — not the combine — dominates).

Tested and ruled out (each against the cached rows): per-member OLS
features ([lnV1,g12] / [lnV1,lnPREM]); OLS window (±1.5/±2.0/±2.5/
±3.0/nearest-15/20/whole); OLS recentering (median/mean/none); OLS
library filter (EA-filtered vs full); shape template (median/mean);
(c,s) fit (OLS/moment/no-intercept); per-hour OLS shape view; mix
weights (grids + least-squares fits, including 2-view blends and
no-EA-filter shapes); sd conventions (ddof=0/1); EA filter variants
(tier/naive/hyphen/union); size clamp (on/off); library composition
(37 launches, all g12 present — verified; case files byte-identical
across v28–v31).

The sharpest facts for the next round:

* The y5 **sig cannot be fit by any fixed weights** on the validated
  view sigs (least-squares max residual 0.42 over 943 rows) — so the
  y5/z0/y1 shape views differ **structurally**, not just in weights.
  The same holds for the mu: member-difference tests (z0−y1, y5−clone)
  fail with max errors 0.52 / 1.20.
* The y5 mu error pattern: negative early and late for p01/p03
  (−0.06…−0.09), negative throughout for p02 growing to −0.21 at
  h21, flipping positive late for p00 (+0.04…+0.10 at h16–h24). The
  error grows with hour on p02 — consistent with the shape amplitude
  (s) prediction being too small for big targets and too big for p00.
  A least-squares recovery of the true (c, s) shape predictions gives
  s_all = 1.51/0.82/0.51/0.82 (p00–p03) vs this file's 1.85/0.73/
  0.15/0.72, and s_con = 1.28/0.81/0.85/0.83 vs 1.12/0.95/0.86/0.96.
* The clone's mu error is confined to p00 (+0.006…+0.019, all hours)
  and zero (≤0.001) on p01–p03 — a small systematic bias at the
  low-lnV1 end that the next round should also explain.
* v30's DESIGN.md records that v30's own members matched the cached
  rows to 0.0000 after the Y1 fix ([lnV1, lnPREM] shape features) —
  so the construction exists and is reproducible; this round's
  reconstruction of it is missing a detail in the shape views that
  the prose spec does not state.

## Results

* Cached-row sweep, packaged cell: practice **0.117532**, LOO-large
  **0.208604**, LOO-mega **0.210005**, median-only **0.182041** — beats
  v30 on all four (practice −0.001178, LOO −0.001140/−0.001395,
  median-only −0.002460).
* Direct grade of this `main.py` (local, exact RULES pinball logic):
  practice **0.122963** (p00 0.1046 / p01 0.1363 / p02 0.0972 /
  p03 0.1538), LOO-large **0.220231**, LOO-mega **0.223201**,
  median-only **0.194397** — does NOT beat v30. One local direct
  grade used (this candidate); no official main-agent grade was
  requested because the member gap was already known to fail it.

## Honest caveats

1. **Selection bias.** Every parameter was chosen on the same four
   practice launches and the same 37-launch LOO that all previous
   rounds selected on. The sweep margins are real on those rows but
   partly selection noise, and the packaged cell's parameters are
   more extreme than v30's (shift 0.60 + slope 0.20).
2. **The practice board is flooded.** As of 17 Nov ~21:08 WIB, 198
   entries score below 0.122315 — the top is dominated by replay /
   memorization entries (67 entries at exactly 1e-06). Even the sweep
   cell at 0.117532 would sit around rank #200 on the practice board,
   nowhere near the top 10 the owner now requires for submission. The
   final rewards honest generalization, not memorized practice curves.
3. **Extrapolation.** The final launch (lnV1 ~ 14+) sits beyond the
   library's largest launch (13.68). The size shift (−0.04·size), the
   size-indexed disagreement shift (0.60 + 0.20·size), and the W5
   interaction (1 + 1.25·size·sd) all extrapolate hardest exactly
   there, and no gate in this repo can validate them at that size.
4. **0.100 is practically unreachable honestly.** The median is the
   bottleneck (best median-only practice on the cached rows is now
   0.182041), the per-hour OLS residual sd is 0.35–0.45 log, and the
   practice answers are 2–2.5× rougher than the comparables.
5. **Not submitted.** The owner's rule (17 Nov ~21:21 WIB) is to submit
   only a candidate that reaches the top 10. This file does not even
   beat v30 in direct grade. v30 remains the best verified fallback;
   v26 remains the submitted entry under Force_Last.
