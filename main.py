"""Forecast the Twitch viewers of GTA VI's launch day, hour by hour.

The idea: big console launches that unlock at midnight local time all trace
a similar daily shape once you divide by the first hour's print. Hour 1 of
the UTC day only has New Zealand and Australia awake, so it is small; the
curve dips in the dead of night, climbs as Europe wakes and the US coasts
unlock, and peaks in the late UTC evening. The shape is a ratio curve:
for each past launch, viewers(hour) / viewers(hour 1).

Two things make the ratio curve usable. First, only console-only launches
with a rolling midnight unlock share GTA VI's shape; PC-simultaneous and
early-access launches have a different hour-1 anchor and are left out.
Second, the curve flattens as the launch gets bigger: the bigger the
first-hour print, the smaller the peak ratio (log peak ratio falls about
0.32 per unit of log first-hour print across the console group). So the
median ratio curve is damped by a factor fitted from that size relation.

Quantiles come from the spread of log ratios across the console group at
each hour, in log space, using the normal quantiles at the five levels.
Everything is deterministic: no randomness, no network, standard library
only. It reads every *.in file in the input directory (name order) and
writes one *.out per case.
"""

import json
import math
import os
import statistics
from datetime import datetime
from pathlib import Path

TAU_LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
NORMAL_Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]
MIN_SPREAD = 0.05
DAMP_LO = 0.15
DAMP_HI = 1.6


def _parse_time(text):
    """ISO 8601 UTC instant, tolerating the trailing Z."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _day_curve(comp):
    """A comparable's release-day hourly viewers: {hour 1..24: viewers}.

    Hours are counted from the comparable's day_start. Points outside the
    24-hour release day are ignored. A comparable with no hour-1 print
    (for instance the GTA VI category's own pre-release history) yields an
    empty hour 1 and is skipped by the caller.
    """
    start = _parse_time(comp["day_start"])
    curve = {}
    for point in comp.get("hourly", []):
        try:
            when = _parse_time(point["from"])
        except (KeyError, ValueError):
            continue
        delta = (when - start).total_seconds() / 3600.0
        if 0.0 <= delta < 24.0:
            hour = int(delta) + 1
            viewers = point.get("viewers")
            if isinstance(viewers, (int, float)) and viewers >= 0:
                curve[hour] = viewers
    return curve


def _rolling_console(comp):
    """True when a comparable is a console-only launch with a rolling
    midnight-local unlock and no early access, the group whose shape
    matches a console-only GTA VI launch."""
    platforms = (comp.get("platforms") or "").lower()
    unlock = (comp.get("unlock") or "").lower()
    if "pc" in platforms:
        return False
    if "early access" in unlock or "early-access" in unlock:
        return False
    return True


def _log_ratios(comps, hours):
    """Per-hour lists of log(viewers_h / viewers_1) for comparables that
    have a usable hour-1 print."""
    per_hour = {h: [] for h in hours}
    for comp in comps:
        curve = _day_curve(comp)
        p1 = curve.get(1)
        if not p1 or p1 < 1:
            continue
        for h in hours:
            v = curve.get(h)
            if v and v >= 1:
                per_hour[h].append(math.log(v / p1))
    return per_hour


def _peak_size_fit(comps, hours):
    """Fit log(peak ratio) = a + b * log(first-hour print) across the
    shape group. Returns (a, b, median_peak_log) or None when the group
    is too small to fit."""
    xs = []
    ys = []
    for comp in comps:
        curve = _day_curve(comp)
        p1 = curve.get(1)
        if not p1 or p1 < 1:
            continue
        ratios = [
            math.log(curve[h] / p1)
            for h in hours
            if h in curve and curve[h] >= 1
        ]
        if ratios:
            xs.append(math.log(p1))
            ys.append(max(ratios))
    if len(xs) < 4:
        return None
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    return (intercept, slope, statistics.median(ys))


def _build_shape(comps, p1, hours):
    """Mean log-ratio per hour and its spread, with the size damping.

    Returns (adjusted_log_ratio, spread) dicts keyed by hour. The damping
    shrinks the whole ratio curve toward flat for a big first-hour print,
    using the fitted peak-size relation; it is clamped so an extreme
    first-hour print can flatten the curve but never invert it.
    """
    per_hour = _log_ratios(comps, hours)
    mean_log = {}
    spread = {}
    for h in hours:
        vals = per_hour[h]
        if not vals:
            mean_log[h] = 0.0
            spread[h] = 0.30
            continue
        m = statistics.mean(vals)
        mean_log[h] = m
        spread[h] = max(
            math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals)),
            MIN_SPREAD,
        )
    damp = 1.0
    fit = _peak_size_fit(comps, hours)
    if fit is not None:
        intercept, slope, median_peak = fit
        if median_peak > 0.05:
            predicted_peak = intercept + slope * math.log(max(1.0, p1))
            damp = predicted_peak / median_peak
            damp = max(DAMP_LO, min(DAMP_HI, damp))
    adjusted = {h: mean_log[h] * damp for h in hours}
    return adjusted, spread


def _quantile_row(p1, centre_log, spread_log):
    """Five quantiles around the centre, non-decreasing, clamped to the
    allowed range, rounded to two decimals."""
    out = []
    for z in NORMAL_Z:
        value = p1 * math.exp(centre_log + z * spread_log)
        value = round(value, 2)
        value = max(0.01, min(1_000_000_000.0, value))
        out.append(value)
    for i in range(1, len(out)):
        if out[i] < out[i - 1]:
            out[i] = out[i - 1]
    return out


def _forecast_case(case):
    """Forecast one case: {"hours": [{"hour": h, "q": [...]}, ...]}."""
    if list(case.get("levels", [])) != TAU_LEVELS:
        raise ValueError("case asks for different levels")
    first = None
    for row in case.get("known", []):
        if row.get("hour") == 1:
            first = row
            break
    if first is None:
        raise ValueError("case has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))
    hours = [row["hour"] for row in case.get("forecast", [])]
    if not hours:
        hours = list(range(2, 25))
    comps = case.get("comparables", [])
    shape_group = [c for c in comps if _rolling_console(c)]
    usable = [
        c for c in shape_group if _day_curve(c).get(1)
    ]
    if len(usable) < 3:
        usable = [c for c in comps if _day_curve(c).get(1)]
    centre, spread = _build_shape(usable, p1, hours)
    rows = []
    for h in hours:
        rows.append(
            {"hour": h, "q": _quantile_row(p1, centre[h], spread[h])}
        )
    return {"hours": rows}


def run():
    in_dir = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(in_dir.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = _forecast_case(case)
        text = json.dumps(result, separators=(",", ":")) + "\n"
        (out_dir / (path.stem + ".out")).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    run()
