# GTA VI launch-day Twitch CCU forecaster — v31

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/AndryXSad/gta6-twitch-ccu-forecast-01-v31/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/AndryXSad/gta6-twitch-ccu-forecast-01-v31/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

A make.fun `gta6-twitch-ccu-forecast-01` entry. It forecasts, for each of
hours 2–24 of Grand Theft Auto VI's release day (2026-11-19 UTC), five
quantiles (5%, 25%, 50%, 75%, 95%) of the concurrent Twitch viewers in the
"Grand Theft Auto VI" category, from the first hour's print and the
launch-day curves of past big game launches shipped inside each case.

## Status — NOT submittable

This round found a combine cell that beats v30 on the cached member rows
(practice **0.117532**, LOO-large **0.208604**, LOO-mega **0.210005**,
median-only **0.182041**), but the `main.py` in this repo does **not**
reproduce the cached member rows: its Y5/Z0/Y1 members differ from the
cached rows by up to ~0.21 in log-median, so the direct grade of this
file is practice **0.122963**, LOO **0.220231 / 0.223201** — worse than
v30 (0.118710 / 0.209744 / 0.211400). The member-construction gap is
documented in `DESIGN.md` for the next round. Do not submit this entry;
v30 remains the best verified fallback.

## How it works

`main.py` (Python 3.13, standard library only, no network) builds four
member predictors in log space from the 37 comparable past launches:

1. **Y5** — tier-filtered per-hour OLS on `[lnV1, g12]` blended
   (0.5/0.2/0.3) with console-only and all-launch one-factor shape views.
   `g12` is the "unlock momentum" feature: lnV1 minus log viewers 12 hours
   before release day.
2. **Z0** — the same construction with the naive early-access filter
   (launches whose notes contain "early access" are excluded).
3. **Y1** — the same construction, naive filter, features `[lnV1, lnPREM]`.
4. **Clone** — whole-library shape views, sample-sd spreads, and a
   weighted-mean blend (0.6 OLS / 0.2 console-shape / 0.2 all-shape) whose
   spread is 0.81× the weighted mean of the view spreads.

The **log-median is chosen per hour band**:

| band | hours | median source | ramp |
| ---- | ----- | ------------- | ---- |
| early | 2–6 | Y1 log-median | 0.00 → +0.045 |
| mid | 7–14 | 0.6·Y5 + 0.4·clone | 0.00 → −0.14 |
| late | 15–24 | median of Y5 / Z0 / Y1 log-medians | 0.00 → +0.05 |

On top of that, a **size-dependent shift**: the median runs high on big
launches, so above lnV1 11.5 the median is pulled down by 0.04 per log
unit of size, in every band, and a **deeper, size-indexed disagreement
shift** `mu += (0.60 + 0.20 * max(0, lnV1 - 11.5)) * sd` of the four
member log-medians (late band base 0.45). When the members disagree, the
median sits systematically low — shifting it up buys practice AND LOO.

The **v31 lever resolves the v30 spread–size tension**: instead of
growing the spread with size directly (which bought LOO at the cost of
practice, monotonically), size now grows the spread **only through the
disagreement** — `spread *= 1 + 1.25 * size * sd(member medians)` — plus
a small lower-side-only size slope (`sig_lo *= 1 + 0.05 * size`). Big
launches disagree more, so their spreads widen exactly where the members
already disagree, and the practice cases (which are smoother than the
LOO launches) pay almost nothing for it.

The **log-spread** is 0.975× the 3-way weighted mean of the member spreads
(45% Y5 + 35% Z0 + 20% clone), widened by a **disagreement factor**
`1 + 0.85 * sd(member medians)`, shaped per band with separate
lower/upper scales: early (0.90, 1.10), mid (1.10, 0.80), late
(0.95, 0.85), narrowed across the late band (spread scale 0.975 → 0.84
from hour 15 to hour 24), and finally **capped at 0.315**. Quantiles are
lognormal.

## Results

On the cached v29 member rows, the packaged cell scores practice
**0.117532** (p00 0.1070 / p01 0.1366 / p02 0.0778 / p03 0.1488),
LOO-large **0.208604**, LOO-mega **0.210005**, median-only practice
**0.182041** — better than v30 (0.118710 / 0.209744 / 0.211400 /
0.184501) on all four. But the direct grade of this `main.py` does not
reproduce those numbers (see Status above), because the member
reconstruction is incomplete. See `DESIGN.md` for the full reasoning
record, the member diagnosis, and the honest caveats. Not submitted:
the owner's rule is to submit only a candidate that reaches the top 10,
and this file does not even beat v30 in direct grade.

## Run it

```sh
MAKEFUN_INPUT_DIR=<dir with *.in> MAKEFUN_OUTPUT_DIR=<dir> python3 main.py
```

Each `*.in` case produces a matching `*.out`:
`{"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]}]}` for h = 2..24.
