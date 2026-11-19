# gta6-trophy-rarity-forecast-01

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/ibell230814/gta6-trophy-rarity-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/ibell230814/gta6-trophy-rarity-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

A forecast, for every Grand Theft Auto VI trophy on PlayStation 5, of the percent of Exophase-tracked players who will have earned it one week after launch (2026-11-26T00:00:00Z). The program (`main.py`, Python 3.13, standard library only, no network) reads one case file — the recorded history of the game's Exophase trophy page up to a checkpoint — and writes five quantiles of each trophy's earn rate at the target. Its model blends a logit trend on a saturating clock, a separate earners-vs-players-tracked ratio forecast (rates can fall while earners rise, when the tracked pool grows faster), and persistence, with a spread calibrated from each trophy's own snapshot-to-snapshot moves. See METHOD.md for the full method and sources.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=2zq0ch20&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
