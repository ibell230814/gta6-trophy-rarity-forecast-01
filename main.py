"""gta6-trophy-rarity-forecast-01 entry (Python 3.13, standard library only).

Forecast, for every PlayStation 5 trophy of Grand Theft Auto VI, the percent
of Exophase-tracked players who will have earned it at the case's target.

How the grader runs it: `python3 /bot/main.py`, one case file in the input
directory (MAKEFUN_INPUT_DIR, else /input), one forecast file per case in
the output directory (MAKEFUN_OUTPUT_DIR, else /output). No network.

The model, in one paragraph per idea (see METHOD.md for the long version):

1. An earn rate is a ratio, earners / players_tracked, and both sides move.
   Early on the tracked pool grows faster than anyone can earn trophies, so
   rates fall even while earners rise (launch night: the pool went from 638
   to 3,868 players at the first refresh and nearly every rate dropped).
   So the model forecasts earners and players separately, each with a
   log-growth trend, and divides them again at the target.
2. It also fits the rate directly: logit(rate) against ln(1 + hours since
   the first snapshot), the same saturating clock the rates themselves
   follow, because story progress slows as the easy trophies run out.
3. The median is a fixed blend of that trend forecast, the ratio forecast
   and persistence (the last rate), and the spread is calibrated from the
   case's own snapshot-to-snapshot logit moves, so a case whose page has
   been jumping gets a wider band than one that has been still.

Snapshots, not reads: Exophase refreshes its counts on its own schedule, so
long runs of reads are the same page repeated. The history is compressed
to the reads where the page actually changed, and each kept snapshot is
weighted by how long it stayed current, which keeps launch night's single
frozen page from outvoting a day of movement.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# The grader's -P leaves this file's directory off sys.path; nothing else is
# imported from it today, but keep the entry self-locating like the kit's.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# Blend weights for the median, in logit space: trend, earners/players
# ratio, persistence. Fixed in advance of the final; they sum to 1.
W_TREND = 0.45
W_RATIO = 0.35
W_STAY = 0.20

# The house baseline's daily logit volatility; this entry's floor is a
# little under it and its ceiling well above it, set from the case itself.
SIGMA_FLOOR = 0.45
SIGMA_CEIL = 1.40
SIGMA_DEFAULT = 0.80


def clamp_rate(pct: float) -> float:
    return min(99.99, max(0.01, pct))


def logit(pct: float) -> float:
    p = clamp_rate(pct)
    return math.log(p / (100.0 - p))


def inv_logit(x: float) -> float:
    if x >= 0:
        return 100.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return 100.0 * e / (1.0 + e)


def round4(x: float) -> float:
    return math.floor(x * 10000.0 + 0.5) / 10000.0


def parse_time(text: str) -> float:
    """ISO 8601 UTC text to epoch seconds."""
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def wls(xs, ys, ws):
    """Weighted least squares y ~ a + b*x; returns (a, b) or None."""
    sw = sum(ws)
    if sw <= 0:
        return None
    mx = sum(w * x for x, w in zip(xs, ws)) / sw
    my = sum(w * y for y, w in zip(ys, ws)) / sw
    sxx = sum(w * (x - mx) ** 2 for x, w in zip(xs, ws))
    if sxx <= 1e-12:
        return (my, 0.0)
    sxy = sum(w * (x - mx) * (y - my) for x, y, w in zip(xs, ys, ws))
    b = sxy / sxx
    return (my - b * mx, b)


def snapshots(case):
    """Compress the read history to the moments the page actually changed.

    Returns a list of (epoch_seconds, players_tracked, rates) with strictly
    increasing times, oldest first. A read joins the previous snapshot when
    neither the tracked-player count nor any rate moved.
    """
    out = []
    for read in case["history"]:
        key = (read.get("players_tracked"), tuple(read["rates"]))
        if out and out[-1][0] == key:
            continue
        out.append((key, parse_time(read["at"]), read.get("players_tracked"), read["rates"]))
    return [(at, players, rates) for _, at, players, rates in out]


def duration_weights(times, end_time):
    """Each snapshot's weight: how long it stayed the current page, in
    hours, with a one-hour floor so a fast-moving stretch still counts."""
    ws = []
    for i, t in enumerate(times):
        nxt = times[i + 1] if i + 1 < len(times) else end_time
        ws.append(max(1.0, (nxt - t) / 3600.0))
    return ws


def forecast_trophy(snaps, idx, t0, t_target, horizon_days):
    """Five quantiles for one trophy, as percents."""
    pts = []  # (hours since t0, rate, players)
    for at, players, rates in snaps:
        r = rates[idx] if idx < len(rates) else None
        if r is not None:
            pts.append(((at - t0) / 3600.0, float(r), players))
    if not pts:
        return [0.01] * 5
    last_rate = pts[-1][1]
    last_logit = logit(last_rate)
    hours_target = (t_target - t0) / 3600.0
    x_target = math.log1p(hours_target)

    median_logit = last_logit
    if len(pts) >= 3:
        xs = [math.log1p(h) for h, _, _ in pts]
        ws = duration_weights([h for h, _, _ in pts], hours_target)
        # Direct trend of the rate on the logit scale.
        fit = wls(xs, [logit(r) for _, r, _ in pts], ws)
        trend_logit = fit[0] + fit[1] * x_target if fit else last_logit
        # Earners and players separately, in log space, then divide.
        ratio_logit = None
        ex, ey, px, py, ew = [], [], [], [], []
        for (h, r, players), w in zip(pts, ws):
            if players and players > 0 and r > 0:
                earners = r / 100.0 * players
                if earners > 0:
                    ex.append(math.log1p(h))
                    ey.append(math.log(earners))
                    px.append(math.log1p(h))
                    py.append(math.log(float(players)))
                    ew.append(w)
        if len(ex) >= 3:
            fe = wls(ex, ey, ew)
            fp = wls(px, py, ew)
            if fe and fp:
                e_hat = math.exp(fe[0] + fe[1] * x_target)
                p_hat = math.exp(fp[0] + fp[1] * x_target)
                if p_hat > 0:
                    ratio_logit = logit(100.0 * e_hat / p_hat)
        if ratio_logit is None:
            # No usable earners/players series (a rate or a player count was
            # missing or zero throughout): give the ratio's share to the
            # trend, keeping the trend:persistence ratio the blend intends.
            trend_share = W_TREND / (W_TREND + W_STAY)
            median_logit = trend_share * trend_logit + (1.0 - trend_share) * last_logit
        else:
            median_logit = W_TREND * trend_logit + W_RATIO * ratio_logit + W_STAY * last_logit
        # No trophy's week-one move is unbounded: keep the median's logit
        # move from its last rate inside a wide, fixed corridor.
        delta = median_logit - last_logit
        median_logit = last_logit + max(-2.5, min(3.0, delta))

    sigma = calibrated_sigma(pts, horizon_days)
    spread = sigma * math.sqrt(max(horizon_days, 0.01))
    spread += 0.12 * abs(median_logit - last_logit)
    spread = min(spread, 2.2)
    qs = [round4(inv_logit(median_logit + z * spread)) for z in Z]
    # Quantiles must never decrease; rounding can only flatten them.
    for i in range(1, len(qs)):
        if qs[i] < qs[i - 1]:
            qs[i] = qs[i - 1]
    return qs


def calibrated_sigma(pts, horizon_days):
    """Daily logit volatility from the trophy's own snapshot moves."""
    moves = []
    for (h0, r0, _), (h1, r1, _) in zip(pts, pts[1:]):
        gap_days = (h1 - h0) / 24.0
        if gap_days > 0:
            moves.append(abs(logit(r1) - logit(r0)) / math.sqrt(gap_days))
    if not moves:
        return SIGMA_DEFAULT
    moves.sort()
    mid = moves[len(moves) // 2]
    # The median absolute move of a normal step is about 0.674 sigma.
    sigma = mid / 0.674 if mid > 0 else SIGMA_FLOOR
    return max(SIGMA_FLOOR, min(SIGMA_CEIL, 0.6 * sigma + 0.4 * 0.5))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = sorted(p for p in INPUT_DIR.iterdir() if p.name.endswith(".in"))
    for path in inputs:
        case = json.loads(path.read_text(encoding="utf-8"))
        if list(case["levels"]) != LEVELS:
            raise ValueError(f"{path.name} asks for levels {case['levels']}, not {LEVELS}")
        snaps = snapshots(case)
        if not snaps:
            raise ValueError(f"{path.name} has no history")
        t0 = snaps[0][0]
        t_target = parse_time(case["target"])
        horizon_days = case["horizon_minutes"] / 1440.0
        rows = []
        for idx, trophy in enumerate(case["trophies"]):
            q = forecast_trophy(snaps, idx, t0, t_target, horizon_days)
            rows.append({"id": trophy["id"], "q": q})
        out_name = path.name[: -len(".in")] + ".out"
        (OUTPUT_DIR / out_name).write_text(
            json.dumps({"trophies": rows}) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
