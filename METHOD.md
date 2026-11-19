# Method — how this forecast is built

## What is being forecast

For every PlayStation 5 trophy of Grand Theft Auto VI, the percent of the
players Exophase tracks for the game who will have earned it at the case's
target (for the final case, 2026-11-26T00:00:00Z, one week after launch).
The program writes, per trophy, five quantiles (0.05, 0.25, 0.5, 0.75,
0.95) of that earn rate. Scoring is mean pinball loss on the logit scale,
so the quantiles below are the model's honest beliefs, not a point guess
with decoration.

## Sources

- The case files themselves: the house's recording of Exophase's trophy
  page for the game, https://www.exophase.com/game/grand-theft-auto-vi-psn/trophies/
  (described in the kit's input/NOTICE.txt). Everything the program knows
  at run time is in its case file; it runs with no network.
- The competition's RULES.txt, for the scoring rule, the case format, and
  the house's account of launch night: the page sat unchanged at 638
  tracked players from 2026-11-18T23:48Z to its 04:00Z read, then refreshed
  by 04:30Z to 3,868 tracked players with nearly every rate lower.
- The kit's practice cases p00 and p01, used to test the program's output
  shape and determinism. Their histories hold a single distinct snapshot,
  so on them the model is persistence with a wide band — which is the
  honest forecast for a page that has not moved yet in the data given.

No play data of my own is claimed anywhere: the numbers the model emits
are forecasts computed from the case's recorded history, nothing else.

## The model

An earn rate is a ratio, earners / players_tracked, and the two sides move
at different speeds. Three views of each trophy are blended in logit
space, with fixed weights chosen before the final (trend 0.45, ratio
0.35, persistence 0.20):

1. **Trend.** Weighted least squares of logit(rate) against
   ln(1 + hours since the first snapshot) — a saturating clock, because
   early story trophies are earned quickly and then progress slows.
2. **Ratio.** The same log-growth fit applied separately to the earner
   count (rate × players_tracked) and to players_tracked; the forecast
   divides them again. This is the part that can call a rate *down* while
   earners rise, as happened at the first refresh.
3. **Persistence.** The last recorded rate, which anchors trophies whose
   series is too short or too still to fit.

Details that keep the fits honest:

- Reads are compressed to snapshots — the moments the page actually
  changed — and each snapshot is weighted by how long it stayed current,
  so a frozen page repeated for hours does not outvote real movement.
- The median's logit move away from the last rate is kept inside a wide
  fixed corridor (−2.5 to +3.0), so a wild early fit cannot promise a
  rate the week cannot deliver.
- The spread is calibrated per trophy from its own snapshot-to-snapshot
  logit moves (median absolute move, scaled to a daily sigma, floored at
  0.45 and capped at 1.40), widened by the square root of the horizon in
  days and by the size of the median's own move. A still page therefore
  gets the default sigma of 0.80, and a jumping page a wider band.

## Verification done while building

- Ran on the kit's practice cases p00 and p01: output shape checked row
  by row (55 trophies, ids 1–55 once each, five non-decreasing quantiles
  in [0, 100], only the `trophies` key, well under the 65,536-byte cap),
  and two runs byte-identical.
- Ran on a synthetic moving-history case shaped like the final (about
  2.5 days of changing snapshots, 6,510-minute horizon) to exercise the
  trend and ratio fits: valid output, medians close to the last rates
  with the trend's pull, runtime far under the 8-second cap.
