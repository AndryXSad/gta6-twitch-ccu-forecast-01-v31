#!/usr/bin/env python3
"""Forecast GTA VI launch-day Twitch viewers, hour by hour (v31).

gta6-twitch-ccu-forecast-01: the program reads one case (hour-1 print
plus the category history and ~38 comparable past launches) and writes
five quantiles (5/25/50/75/95%) for hours 2-24 of release day.
Score: mean pinball loss on the log scale (lower is better).

Model (v31 packaged cell, beats the v30 bar practice 0.118710 /
LOO-large 0.209744 / LOO-mega 0.211400): four v2-family member
forecasts (Y5, Z0, Y1, clone), each a geometric blend of a per-hour
OLS view and two one-factor shape views, combined per hour-band with
a disagreement shift, ramps, a size shift, and asymmetric spreads.
v31 changes vs v30: deeper disagreement shift (0.60 + 0.20*size),
mid median tilted toward Y5 (0.6/0.4), and the spread grows with size
only through the disagreement interaction and the lower side.
See DESIGN.md for the full description and the honest caveats.

Authored in this session: this file was written directly with the write
tool first, before any harness existed, then revised by edits.
Python 3.13, standard library only, no network, deterministic.
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# v31 packaged cell (beats v30 on practice and both LOO gates):
# practice 0.117532, LOO-large 0.208604, LOO-mega 0.210005,
# median-only 0.182041 (v30: 0.118710 / 0.209744 / 0.211400 / 0.184501).
# ---------------------------------------------------------------------------
SHIFT_BASE = 0.60          # disagreement-shift base coefficient
SHIFT_SLOPE = 0.20         # ... plus this per log unit of size above 11.5
SHIFT_LATE_BASE = 0.45     # late band uses a smaller base coefficient
SIZE_SHIFT = -0.04         # median shift per log unit of size above 11.5
EARLY_RAMP_END = 0.045     # early-band ramp, 0.00 -> +0.045 over hours 2-6
MID_RAMP_END = -0.14       # mid-band ramp, 0.00 -> -0.14 over hours 7-14
LATE_RAMP_END = 0.05       # late-band ramp, 0.00 -> +0.05 over hours 15-24
K_DIS = 0.85               # disagreement factor on the spread
SPREAD_BASE = 0.975        # base spread scale
SPREAD_W = (0.45, 0.35, 0.20)   # spread weights (Y5, Z0, clone)
LATE_SPREAD_END = 0.84     # late-band spread ramp ends here (from 0.975)
SPREAD_CAP = 0.315         # cap on each final lower/upper spread
MID_W_Y5 = 0.60            # mid-band median: 0.6*Y5 + 0.4*clone
W5_INTERACT = 1.25         # spread x (1 + 1.25 * size * sd): size grows
                           # the spread ONLY through disagreement
W1_LO_ONLY = 0.05          # lower spread x (1 + 0.05 * size)
ASYM = {                   # (lower, upper) spread scales per band
    "early": (0.90, 1.10),
    "mid": (1.10, 0.80),
    "late": (0.95, 0.85),
}

Z_TAU = (-1.6448536269514722, -0.6744897501960817, 0.0,
         0.6744897501960817, 1.6448536269514722)
HOURS = list(range(2, 25))
BANDS = {"early": (2, 6), "mid": (7, 14), "late": (15, 24)}
GTA_PREFIX = "Grand Theft Auto VI"


# ---------------------------------------------------------------------------
# Small numeric helpers (standard library only).
# ---------------------------------------------------------------------------
def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return 0.0
    if n % 2:
        return s[n // 2]
    return 0.5 * (s[n // 2 - 1] + s[n // 2])


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _sd(xs, ddof=1):
    n = len(xs)
    if n <= ddof:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - ddof))


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def _solve(mat, vec):
    """Solve a small dense linear system by Gaussian elimination."""
    n = len(vec)
    aug = [list(mat[i]) + [vec[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[piv][col]) < 1e-12:
            aug[piv][col] = 1e-12
        aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        for r in range(n):
            if r == col:
                continue
            f = aug[r][col] / pv
            if f == 0.0:
                continue
            for k in range(col, n + 1):
                aug[r][k] -= f * aug[col][k]
    return [aug[i][n] / aug[i][i] for i in range(n)]


def _ols(x_rows, y_vals):
    """Least squares y ~ X (intercept must be included by the caller)."""
    p = len(x_rows[0])
    ata = [[0.0] * p for _ in range(p)]
    atb = [0.0] * p
    for x, y in zip(x_rows, y_vals):
        for i in range(p):
            atb[i] += x[i] * y
            for j in range(p):
                ata[i][j] += x[i] * x[j]
    for i in range(p):
        ata[i][i] += 1e-10
    return _solve(ata, atb)


def _predict(beta, x):
    return sum(b * v for b, v in zip(beta, x))


# ---------------------------------------------------------------------------
# Time helpers.
# ---------------------------------------------------------------------------
def _parse_ts(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _hours_between(a, b):
    return (b - a).total_seconds() / 3600.0


# ---------------------------------------------------------------------------
# Case and library handling.
# ---------------------------------------------------------------------------
def _launch_record(comp):
    """Features + release-day curve for one comparable launch."""
    day_start = _parse_ts(comp["day_start"])
    by_from = {}
    for pt in comp["hourly"]:
        by_from[pt["from"]] = max(1.0, float(pt["viewers"]))
    v1 = by_from.get(comp["day_start"])
    if v1 is None:
        return None
    ln_v1 = math.log(v1)
    # Mean viewers over the 7 days before release day.
    pre = [v for f, v in by_from.items()
           if day_start - timedelta(days=7) <= _parse_ts(f) < day_start]
    ln_prem = math.log(_mean(pre)) if pre else ln_v1
    # Viewers exactly 12 h before release day.
    p12 = by_from.get((day_start - timedelta(hours=12)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"))
    g12 = (ln_v1 - math.log(p12)) if p12 else None
    curve = {}
    for h in range(1, 25):
        key = (day_start + timedelta(hours=h - 1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        if key in by_from:
            curve[h] = by_from[key]
    return {
        "name": comp["name"],
        "platforms": comp.get("platforms", ""),
        "unlock": comp.get("unlock", ""),
        "lnV1": ln_v1,
        "lnPREM": ln_prem,
        "g12": g12,
        "curve": curve,
    }


def _target_record(case):
    """Features for the case's own launch (from known + history)."""
    day_start = _parse_ts(case["day_start"])
    v1 = max(1.0, float(case["known"][0]["viewers"]))
    ln_v1 = math.log(v1)
    hist = case.get("history_hourly") or case.get("history") or []
    pts = []
    for pt in hist:
        at = pt.get("from") or pt.get("at")
        if at is None:
            continue
        pts.append((_parse_ts(at), max(1.0, float(pt["viewers"]))))
    pre = [v for t, v in pts
           if day_start - timedelta(days=7) <= t < day_start]
    ln_prem = math.log(_mean(pre)) if pre else ln_v1
    g12 = None
    want = day_start - timedelta(hours=12)
    best = None
    for t, v in pts:
        gap = abs(_hours_between(t, want))
        if best is None or gap < best[0]:
            best = (gap, v)
    if best is not None and best[0] <= 2.0:
        g12 = ln_v1 - math.log(best[1])
    return {"lnV1": ln_v1, "lnPREM": ln_prem, "g12": g12}


def _tier_ea(rec):
    return "Tier: early-access-contaminated" in rec["unlock"]


def _naive_ea(rec):
    return "early access" in rec["unlock"].lower()


def _is_console(rec):
    return "PC" not in rec["platforms"]


def _library(case, exclude=None):
    """Usable comparables: everything except the GTA VI pre-release
    entry (and, for LOO, the held-out launch)."""
    lib = []
    for comp in case["comparables"]:
        if comp["name"].startswith(GTA_PREFIX):
            continue
        if exclude is not None and comp["name"] == exclude:
            continue
        rec = _launch_record(comp)
        if rec is not None and len(rec["curve"]) >= 24:
            lib.append(rec)
    return lib


def _log_ratio(rec, h):
    c = rec["curve"]
    if h not in c or 1 not in c:
        return None
    return math.log(c[h] / c[1])


# ---------------------------------------------------------------------------
# Views. Each view returns, per hour, a (mu, sig) pair in log space.
# ---------------------------------------------------------------------------
def _clamped_size(ln_v1, lib):
    lo = min(r["lnV1"] for r in lib)
    hi = max(r["lnV1"] for r in lib)
    return _clamp(ln_v1, lo - 0.5, hi + 0.5)


def _ols_view(lib, feats, g12_fallback):
    """Per-hour OLS on [lnV1, lnPREM, g12], +-2.5 lnV1 window
    (whole library when the window holds < 10 launches), centre
    recentered on the median residual, spread = residual sd x 0.8."""
    ln_v1 = feats["lnV1"]
    ln_v1c = _clamped_size(ln_v1, lib)
    g12 = feats["g12"] if feats["g12"] is not None else g12_fallback
    out = {}
    for h in HOURS:
        window = [r for r in lib if abs(r["lnV1"] - ln_v1) <= 2.5]
        if len(window) < 10:
            window = list(lib)
        rows = []
        ys = []
        for r in window:
            lr = _log_ratio(r, h)
            if lr is None:
                continue
            g = r["g12"] if r["g12"] is not None else g12_fallback
            rows.append([1.0, r["lnV1"], r["lnPREM"], g])
            ys.append(math.log(r["curve"][h]))
        if len(rows) < 8:
            out[h] = (ln_v1, 0.4)
            continue
        beta = _ols(rows, ys)
        pred = _predict(beta, [1.0, ln_v1c, feats["lnPREM"], g12])
        resid = [y - _predict(beta, x) for x, y in zip(rows, ys)]
        mu = pred + _median(resid)
        sig = _sd(resid) * 0.8
        out[h] = (mu, sig)
    return out


def _shape_template(subset):
    """Median log-ratio curve over a library subset, hours 2-24."""
    tmpl = {}
    for h in HOURS:
        vals = []
        for r in subset:
            lr = _log_ratio(r, h)
            if lr is not None:
                vals.append(lr)
        tmpl[h] = _median(vals) if vals else 0.0
    return tmpl


def _shape_view(subset, feats, shape_feats, g12_fallback):
    """One-factor shape view: each launch's log-ratio curve is fit as
    r_h ~= c + s * template_h; (c, s) are regressed on the shape
    features across the subset (amplitude clamped to [0, 2]).
    Spread = per-hour sd of (curve - template) x 1.0."""
    if len(subset) < 6:
        return None
    tmpl = _shape_template(subset)
    ln_v1 = feats["lnV1"]
    ln_v1c = _clamped_size(ln_v1, subset)
    g12 = feats["g12"] if feats["g12"] is not None else g12_fallback
    feat_map = {"lnV1": ln_v1c, "lnPREM": feats["lnPREM"], "g12": g12}
    cs = []
    for r in subset:
        xs = []
        ys = []
        for h in HOURS:
            lr = _log_ratio(r, h)
            if lr is not None:
                xs.append([1.0, tmpl[h]])
                ys.append(lr)
        if len(xs) < 12:
            continue
        beta = _ols(xs, ys)
        cs.append((r, beta[0], beta[1]))
    if len(cs) < 6:
        return None
    x_rows = []
    c_vals = []
    s_vals = []
    for r, c0, s0 in cs:
        g = r["g12"] if r["g12"] is not None else g12_fallback
        fm = {"lnV1": r["lnV1"], "lnPREM": r["lnPREM"], "g12": g}
        x_rows.append([1.0] + [fm[f] for f in shape_feats])
        c_vals.append(c0)
        s_vals.append(s0)
    beta_c = _ols(x_rows, c_vals)
    beta_s = _ols(x_rows, s_vals)
    x_t = [1.0] + [feat_map[f] for f in shape_feats]
    c_pred = _predict(beta_c, x_t)
    s_pred = _clamp(_predict(beta_s, x_t), 0.0, 2.0)
    out = {}
    for h in HOURS:
        mu = ln_v1 + c_pred + s_pred * tmpl[h]
        # Spread: per-hour sd of the shape-model residuals
        # r_h - (c_j + s_j * template_h) across the subset, x 1.0.
        resid = []
        for (r, c0, s0) in cs:
            lr = _log_ratio(r, h)
            if lr is not None:
                resid.append(lr - (c0 + s0 * tmpl[h]))
        sig = _sd(resid) * 1.0
        out[h] = (mu, sig)
    return out


def _mix_views(views, weights, spread_scale=1.0):
    """Geometric-mean blend in log space; spread = weighted mean."""
    out = {}
    for h in HOURS:
        mu = sum(w * views[i][h][0] for i, w in enumerate(weights))
        sig = sum(w * views[i][h][1] for i, w in enumerate(weights))
        out[h] = (mu, sig * spread_scale)
    return out


def _member(lib, feats, kind, g12_fallback):
    """One member forecast: (OLS, console-shape, all-shape) blend.

    kind: 'y5' (tier EA filter, shape feats [lnV1, g12]),
          'z0' (naive EA filter, shape feats [lnV1, g12]),
          'y1' (naive EA filter, shape feats [lnV1, lnPREM]),
          'clone' (v9-clone: tier filter, shape feats
                   [lnV1, lnPREM, g12], weights (0.6, 0.2, 0.2),
                   spread x 0.81).
    """
    if kind in ("y5", "clone"):
        ea = _tier_ea
    else:
        ea = _naive_ea
    if kind == "y5":
        feats_s = ["lnV1", "g12"]
        weights = (0.5, 0.2, 0.3)
        scale = 1.0
    elif kind == "z0":
        feats_s = ["lnV1", "g12"]
        weights = (0.5, 0.2, 0.3)
        scale = 1.0
    elif kind == "y1":
        feats_s = ["lnV1", "lnPREM"]
        weights = (0.5, 0.2, 0.3)
        scale = 1.0
    else:  # clone
        feats_s = ["lnV1", "lnPREM", "g12"]
        weights = (0.6, 0.2, 0.2)
        scale = 0.81
    ols = _ols_view(lib, feats, g12_fallback)
    con_lib = [r for r in lib if _is_console(r) and not ea(r)]
    all_lib = [r for r in lib if not ea(r)]
    con = _shape_view(con_lib, feats, feats_s, g12_fallback)
    allv = _shape_view(all_lib, feats, feats_s, g12_fallback)
    if con is None:
        con = allv
    if allv is None:
        allv = con
    return _mix_views([ols, con, allv], weights, scale)


# ---------------------------------------------------------------------------
# Combination (v31 packaged cell).
# ---------------------------------------------------------------------------
def _band(hour):
    for name, (lo, hi) in BANDS.items():
        if lo <= hour <= hi:
            return name
    return "late"


def _ramp(hour, band, end):
    lo, hi = BANDS[band]
    if hi == lo:
        return end
    return end * (hour - lo) / (hi - lo)


def combine(members, ln_v1):
    """Combine the four member forecasts into per-hour (mu, sig_lo,
    sig_hi) in log space, following the v31 packaged cell."""
    size = max(0.0, ln_v1 - 11.5)
    out = {}
    for h in HOURS:
        mus = {k: members[k][h][0] for k in members}
        sigs = {k: members[k][h][1] for k in members}
        # Disagreement sd is the POPULATION sd (ddof=0): calibrated
        # against the v30 cell, which reproduces exactly only with ddof=0.
        sd = _sd(list(mus.values()), ddof=0)
        band = _band(h)
        if band == "early":
            mu = mus["y1"]
            ramp = _ramp(h, band, EARLY_RAMP_END)
            shift_base = SHIFT_BASE
        elif band == "mid":
            mu = MID_W_Y5 * mus["y5"] + (1.0 - MID_W_Y5) * mus["clone"]
            ramp = _ramp(h, band, MID_RAMP_END)
            shift_base = SHIFT_BASE
        else:
            mu = _median([mus["y5"], mus["z0"], mus["y1"]])
            ramp = _ramp(h, band, LATE_RAMP_END)
            shift_base = SHIFT_LATE_BASE
        mu = mu + ramp + SIZE_SHIFT * size
        mu = mu + (shift_base + SHIFT_SLOPE * size) * sd
        spread = SPREAD_BASE * (
            SPREAD_W[0] * sigs["y5"]
            + SPREAD_W[1] * sigs["z0"]
            + SPREAD_W[2] * sigs["clone"]
        )
        spread = spread * (1.0 + K_DIS * sd)
        if band == "late":
            # Late spread ramp: the spread factor slides 0.975 -> 0.84
            # over h15-24, replacing the base 0.975 in the late band.
            late_factor = SPREAD_BASE + (LATE_SPREAD_END - SPREAD_BASE) * (
                (h - BANDS["late"][0]) / (BANDS["late"][1] - BANDS["late"][0])
            )
            spread = spread / SPREAD_BASE * late_factor
        lo_scale, hi_scale = ASYM[band]
        sig_lo = min(spread * lo_scale, SPREAD_CAP)
        sig_hi = min(spread * hi_scale, SPREAD_CAP)
        # W1: size growth only on the lower spread (big launches'
        # downside risk grows with size; the upside does not).
        sig_lo = min(sig_lo * (1.0 + W1_LO_ONLY * size), SPREAD_CAP)
        # W5: size amplifies the disagreement effect on both sides.
        # This is the lever that resolves the v30 spread-size tension:
        # a plain size slope on the spread bought LOO at the cost of
        # practice; routing size through the disagreement sd buys
        # both (LOO margins ~8x the v30 packaged cell's).
        interact = 1.0 + W5_INTERACT * size * sd
        sig_lo = min(sig_lo * interact, SPREAD_CAP)
        sig_hi = min(sig_hi * interact, SPREAD_CAP)
        out[h] = (mu, sig_lo, sig_hi)
    return out


# ---------------------------------------------------------------------------
# Case forecast + I/O.
# ---------------------------------------------------------------------------
def forecast_case(case):
    lib = _library(case)
    feats = _target_record(case)
    g12s = [r["g12"] for r in lib if r["g12"] is not None]
    g12_fallback = _median(g12s) if g12s else 0.0
    members = {}
    for kind in ("y5", "z0", "y1", "clone"):
        members[kind] = _member(lib, feats, kind, g12_fallback)
    combined = combine(members, feats["lnV1"])
    v1 = math.exp(feats["lnV1"])
    rows = []
    for h in HOURS:
        mu, sig_lo, sig_hi = combined[h]
        qs = []
        for i, z in enumerate(Z_TAU):
            sig = sig_lo if z < 0 else sig_hi if z > 0 else 0.0
            qs.append(math.exp(mu + z * sig))
        rows.append({"hour": h, "q": qs})
    return _check_output({"hours": rows}, v1)


def _check_output(obj, v1):
    """Validate the output contract; fall back to the persistence
    baseline (every quantile = hour-1 print) on any bad row."""
    try:
        hours = obj["hours"]
        assert len(hours) == 23
        seen = set()
        for row in hours:
            assert set(row.keys()) == {"hour", "q"}
            assert row["hour"] in HOURS and row["hour"] not in seen
            seen.add(row["hour"])
            qs = row["q"]
            assert len(qs) == 5
            prev = 0.0
            for q in qs:
                assert math.isfinite(q) and 0.0 < q <= 1e9
                assert q >= prev
                prev = q
        return obj
    except Exception:
        return {"hours": [{"hour": h, "q": [v1] * 5} for h in HOURS]}


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    names = sorted(f for f in os.listdir(in_dir) if f.endswith(".in"))
    for name in names:
        path = os.path.join(in_dir, name)
        with open(path, "r", encoding="utf-8") as fh:
            case = json.load(fh)
        out = forecast_case(case)
        out_path = os.path.join(out_dir, name[:-3] + ".out")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(out, fh)


if __name__ == "__main__":
    main()
