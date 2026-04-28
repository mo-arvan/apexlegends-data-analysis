# Apex Legends Data Analysis

[GitHub](https://github.com/mo-arvan/apexlegends-data-analysis)

Analysis of ALGS tournament damage-event data, centered on **effective TTK (eTTK)** and **effective damage dealt (eDD)** — accuracy-adjusted alternatives to theoretical TTK / DPS for evaluating weapon balance. Outputs are per-weapon balance posts under [`docs/posts/`](docs/posts/).

## Repo layout

Two top-level data directories:

- `data/` — inputs (tracked, hand-curated), external API caches (tracked, slow to re-fetch), and machine-readable pipeline intermediates that other scripts consume. CSV / parquet / JSON.
- `output/` — gitignored. Plots, human-readable Markdown reports, and any artifact a post would link to. Regeneratable from `data/` plus the script set.

If you find yourself reaching for a `.md` summary or a chart file, it's in `output/`. If a script reads it as input, it's in `data/`.

## Setup

Environment is managed by [uv](https://github.com/astral-sh/uv). Python 3.11.

```bash
uv sync   # installs deps into .venv from pyproject.toml + uv.lock
```

## Pipelines

Four chains, each idempotent. Rerun the chain to incorporate new data; intermediate scripts skip work that's already cached on disk.

### 1. ALGS scrape — pulls tournament data from apexlegendsstatus.com

```bash
uv run python src/scrape_dgs.py --debug             # smoke test: 2 tournaments, 5 games, verbose, writes to data/debug/
uv run python src/scrape_dgs.py --min-year 6        # coarse filter: only scrape Y6+ tournaments
uv run python src/scrape_dgs.py --since 2026-01-01  # fine filter: only pull player events for games on/after this date
uv run python src/scrape_dgs.py                     # full scrape (hours; ~60 HTTP calls/game at 2s sleep)
```

Outputs:

- `data/algs_game_list.csv` — tournament + game registry
- `data/algs_games/init/*.json` — per-game init metadata (timestamp, players, map)
- `data/algs_games/getPlayerEvents/*.json` — per-player damage / movement event feed

### 2. ALGS event processing — turns the raw scrape into the analysis-ready damage table

Run in order; each step consumes what the previous wrote.

```bash
uv run python src/preprocess_player_events.py    # data/events_processed/*.parquet (per-game)
uv run python src/process_fights_breakdown.py    # data/fights_data.parquet
uv run python src/process_events.py              # data/tournament_damage_events/*.parquet (the flat damage-event table)
```

### 3. Weapon-stats chain — independent of the ALGS scrape; rerun when new patches drop

This chain is **not fully automated** — its final step produces a structured diff that a human (or agent) reviews before downstream consumers like the eTTK chain are trusted. Run the scripts, then read the reconciliation report, then encode any fixes you decide on. Rerun until the diff is clean enough.

```bash
uv run python src/scrape_patch_notes.py --max-pages 20   # data/patch_notes/ (markdown dumps of EA news posts)
uv run python src/scrape_weapons_wiki.py                 # data/weapons_wiki/{wikigg,fandom}/ (wikitext + infoboxes)
uv run python src/parse_patch_note_deltas.py             # data/patch_note_deltas.csv (per-bullet stat deltas)
uv run python src/apply_patch_deltas.py                  # data/weapon_history.csv + data/weapon_current_from_patches.csv
uv run python src/reconcile_weapon_stats.py              # data/weapon_stats_reconciliation.{csv,md} (four-way diff)
```

Rebuilds from the markdown / infobox cache and the S21-era `data/guns_stats.csv` baseline.

**Manual review step.** Open `output/weapon_stats_reconciliation.md`. The two sections to read:

- _wiki.gg ≠ patch-notes-derived_ — the cells where the two "current" estimates disagree. Each row is one (weapon, stat) cell that needs adjudication.
- _Per-weapon detail_ — the full four-way table per weapon, useful when a weapon has multiple disagreements.

For each disagreement, decide which source is correct and where the fix belongs:

| disagreement type | example | fix layer |
|---|---|---|
| Patch-note parser misread a delta | Wingman Feb 2025 "Base reduced to 5" landed in `magazine_4` instead of `magazine_0` | tighten `parse_patch_note_deltas.py` regex, or add a sanity check in `build_ettk_inputs.py` (the canonical example: the inverted-mag fallback) |
| Patch-note bullet was qualitative ("improved recoil") | recoil tuning, hipfire spread, hop-up state | nothing to do; lives in `weapon_history_unapplied.csv` for reference |
| New weapon variant has no baseline row | Hemlok Breach AR added in S28.1, no S21 row | add a fallback path in `build_ettk_inputs.py` (e.g. backfill `head_multiplier` from wiki's `damageHead/damageBody`) |
| Default-equipped hop-up changed | CAR ships with Disruptor Rounds since 2025-11-03 | add an entry to `HOPUP_OVERRIDES` in `build_ettk_inputs.py` |
| Wiki page is stale | Mastiff still showing 11×8 from an old season | nothing actionable on our side; trust patches-derived |
| Patch-note text uses non-standard units | "Fire rate increased to 3" (rounds/sec, not RPM) | guard in the consumer (the `_wiki_to_rpm` helper, the `<10` rpm coercion in `build_ettk_inputs.py`) |

The chain is idempotent, so after each fix re-run the affected scripts. The reconciliation report shrinks as bugs get encoded.

### 4. eTTK chain — drives the per-weapon balance posts

Reads the event-derived stats from chain 2 and the patches-derived stats from chain 3, joins them, computes per-weapon time-to-down / one-clip thresholds, and renders every chart used in the posts.

```bash
uv run python src/extract_weapon_stats_from_events.py --latest-tournament-only    # data/weapon_stats_latest_tournament.{csv,md}  (per-weapon damage / accuracy / mag from the most recent tournament)
uv run python src/build_ettk_inputs.py                                            # data/weapon_stats_for_ettk.csv  (joined inputs, one row per weapon, with `_source` provenance per stat)
uv run python src/analyze_ettk.py                                                 # data/ettk_*.csv + output/ettk_summary.md  (per-weapon a_down, t_down, quadrant, multi-objective scorecard, rebalance recommendations)
uv run python src/plot_ettk.py                                                    # output/ettk_figs/*.{png,pdf}  (every figure used in the posts)
```

The `--latest-tournament-only` flag scopes step 1 to the most recent tournament in `data/algs_game_list.csv`; without it, step 1 writes `data/weapon_stats_from_events.{csv,md}` for the full event corpus and step 2 needs `--event-stats-csv data/weapon_stats_from_events.csv` to pick that up.

The eTTK intermediate CSVs (`data/ettk_*.csv`) live alongside other pipeline data; the human-facing artifacts (`output/ettk_summary.md`, `output/ettk_figs/`) are gitignored under `output/`.

## More

- [Why](docs/why.md)
- [Fights Breakdown](docs/fights_breakdown.md)
- [Gun Stats Info](docs/gun_stats_info.md)
- [Limitations](docs/limitations.md)
- [Related Work](docs/related_work.md)
- [Credits](docs/credits.md)
