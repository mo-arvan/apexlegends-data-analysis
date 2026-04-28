# Apex Legends Data Analysis

Analysis of ALGS tournament damage-event data, centered on **effective TTK (eTTK)** and **effective damage dealt (eDD)**. These are accuracy-adjusted alternatives to theoretical TTK/DPS for evaluating weapons.

## Overview

- Streamlit app is being retired. Posts (rendered HTML, likely Quarto) are the distribution channel.
- Next post: eTTK-per-weapon across ALGS history, not another MnK-vs-controller piece.
- Y6 ALGS data fully scraped; Y5 backfill running in the background (ETA ~35h as of 2026-04-20).
- Weapon-stats pipeline complete: patch notes, wikis, history, four-way reconciliation all emitting.

## Repo layout

- `src/`: analysis and data pipeline.
  - **ALGS event scrape / processing**
    - `scrape_dgs.py`: pulls tournament game lists and events from apexlegendsstatus.com (HTML + DGS API)
    - `scrape_liquipedia.py`: tournament metadata from Liquipedia
    - `process_events.py` / `preprocess_player_events.py`: turn raw event feed into damage events
    - `process_fights_breakdown.py`: groups damage events into fights (see [docs/fights_breakdown.md](docs/fights_breakdown.md))
    - `damage_calculator.py`: eTTK / eDD math
    - `player_hash_to_input.py`: maps player hashes to MnK/controller
    - `playoff_analysis.py`: tournament-specific analyses
  - **Weapon-stats pipeline** (patch notes + wikis + ALGS data → canonical stats)
    - `scrape_patch_notes.py`: downloads EA patch-note posts from ea.com as markdown
    - `scrape_weapons_wiki.py`: scrapes weapon infoboxes from wiki.gg and fandom via MediaWiki API
    - `parse_patch_note_deltas.py`: extracts per-weapon stat deltas from patch-note markdown
    - `apply_patch_deltas.py`: applies deltas chronologically to guns_stats.csv baseline, emits history
    - `reconcile_weapon_stats.py`: four-way comparison of guns_stats / wiki.gg / fandom / patches-derived
- `pages/`: Streamlit pages (being phased out). Numbered: 10/11 damage curves, 13 grid rank, 14 eTTK, 20 shots hit, 21 input parity, 30 ranker.
- `Home.py`: Streamlit landing page (will be removed with the migration).
- `data/`
  - `events/`, `events_processed/`: raw and processed event feeds per game
  - `algs_games/`, `algs_game_list.csv`: tournament game registry
  - `fights_data.parquet`: preprocessed fights
  - `guns_stats.csv`: weapon stats, **S21-era baseline** (schema in [docs/guns_stats_info.md](docs/guns_stats_info.md))
  - `player_to_hash.json`, `esports_name_to_hash.json`: identity maps
  - `patch_notes/`: markdown dumps of every EA Apex news post, 2019-2026 (raw JSON in `patch_notes/raw/`)
  - `patch_note_deltas.csv`: one row per bullet under a recognized weapon across all patches (numeric + qualitative)
  - `weapons_wiki/{wikigg,fandom}/`: per-wiki `wikitext/*.txt` + `infobox/*.json` + `index.json`
  - `weapon_history.csv`: long history table, one row per (weapon, patch-where-changed). Carries forward unchanged stats.
  - `weapon_current_from_patches.csv`: latest snapshot per weapon from `weapon_history.csv`; the "current-per-patch-notes" state
  - `weapon_history_unapplied.csv`: audit trail of bullets the parser couldn't map to a CSV column (qualitative, attachment-specific, unmatched stats)
  - `weapon_stats_reconciliation.{csv,md}`: four-way comparison per (weapon, stat); `.md` flags the wiki.gg ≠ patches-derived cells for review
- `docs/`: published and draft writeups. Posts live under `docs/posts/`.

## Running things

Pipeline commands (scrape, event processing, weapon-stats chain, eTTK chain) live in [`README.md`](README.md) — same docs humans read. Don't duplicate them here.

Agent-only nuances:

- `--debug` on `scrape_dgs.py` writes to `data/debug/` (a separate cache) and limits to 2 tournaments × 5 games. Use this for smoke-testing changes; the real cache stays untouched.
- The scrape script is idempotent on the cache: it skips game JSONs that already exist on disk, so a re-run after a partial crash only fetches the missing items. Don't delete `data/algs_games/getPlayerEvents/` between runs unless you're rebuilding from scratch.
- All four pipelines are idempotent end-to-end. Outputs from chain 4 (eTTK) are gitignored; their source of truth is the script set plus chains 2 and 3.
- **Chain 3 has a manual review step.** After the five scripts run, `output/weapon_stats_reconciliation.md` flags every (weapon, stat) cell where the four sources disagree. Reviewing that diff and deciding which value is authoritative is part of the workflow — see the README's "Manual review step" table for the standard fix-layer mapping (parser tightening, sanity check in `build_ettk_inputs.py`, `HOPUP_OVERRIDES` entry, etc.). Don't trust `weapon_current_from_patches.csv` blindly for downstream eTTK work without skimming the reconciliation report first.

## Weapon stats: source hierarchy

The pipeline treats sources as follows, in order of trust for *current-patch values*:

1. **Patch notes chain** applied to the S21 baseline. Authoritative for anything Respawn explicitly announced. Walks from `guns_stats.csv` (S21-era) forward through every patch in `data/patch_notes/` applying numeric deltas. Output in `weapon_current_from_patches.csv`.
2. **wiki.gg infobox**. More current than fandom but still lags by 1-2 patches for many weapons; has some outright errors. Use as a cross-check and for fields patch notes don't quantify (deploy/holster, head multiplier when not given).
3. **fandom infobox**. Clearly stale in places (Mastiff still shows 11x8 from an ancient season). Low trust.
4. **Event-feed medians** (ALGS damage-per-shot per weapon). Validates `damage` and effective RPM only; blind to mag/reload/multipliers. Planned, not yet built.

Unmappable patch-note bullets (hipfire, recoil, hop-ups, firing modes) are preserved in `weapon_history_unapplied.csv` so nothing is silently dropped.

## Scraper: two CLI flags worth knowing

- `--min-year N`: tournament-year cutoff. Applied before any per-tournament HTTP, so it trims both HTML scraping and API calls. Use for Y6+ only etc.
- `--since YYYY-MM-DD`: game-timestamp cutoff. Applied after init JSONs are downloaded (so init is always pulled for every game in scope), but before the expensive per-player events scrape. Use when you want a full tournament index but only want player events for recent games.

## Gotchas

All catalogued in [docs/limitations.md](docs/limitations.md). Most load-bearing:

- **Ammo data is unreliable** (36% missing, 8.5% have hits > ammo). This is why the project uses *shots hit* as the primary signal and *cannot* compute true accuracy from the event feed. Any analysis framed as "accuracy" is really about shots-hit shape.
- **Devotion excluded** (variable RPM with no published ramp). Skip it or model it explicitly; don't silently include.
- **30-30 and Mastiff** have segmented reloads that the pipeline doesn't handle correctly.
- **Havoc open-bolt delay** not modeled. tTTK for Havoc is optimistic.
- **Revenant overshield** treated as regular health shield.

### Schema quirks introduced by the 2026-04 ALS redesign

The new Overview page no longer exposes per-game ordinals or prettified maps, so two CSV columns behave differently from older data:

- `game_title`: now stores the URL's match slug (e.g. `"Finals"`, `"AvB"`, `"Day1"`). Old data had `"Game #7"` style strings. Any downstream code parsing `game_title` with a `"Game #(\d+)"` regex will silently stop matching.
- `game_map`: now stores the raw init-JSON `mapImg` filename (e.g. `"mp_rr_tropic_island_mu2.png"`). Old data had human names like `"Storm Point"`. A mapping table belongs somewhere downstream (probably `src/chart_config.py`); add it when the processing step is touched.
- `game_num`: empty string. No longer derivable from HTML. If the downstream really needs it, derive post-hoc from within-tournament ordering by `game_timestamp`.

## Writing conventions

- No em dashes. Use periods, commas, or parentheses.
- Plots: follow the `research-plots` skill. Maximalist, one per figure, no seaborn.
- Before publishing a causal claim, check whether the evidence is actually causal or just suggestive. The MnK post ([docs/posts/mnk_vs_controller/post.md](docs/posts/mnk_vs_controller/post.md)) overclaimed and needs reframing.

## Decisions

Dated decision log. Context → options → choice → why. Newest first.

### 2026-04-19 — Retire the Streamlit app; posts become the artifact

**Context.** The Streamlit app at `apexlegends-data-analysis.streamlit.app` hosts interactive versions of every analysis (damage curves, grid rank, eTTK, shots-hit, input parity, ranker). In practice nobody explores it; the posts and video are what actually reach an audience. Maintaining the app costs dependency sprawl (`streamlit`, `streamlit-extras`, `streamlit-dynamic-filters`, `st-btn-group`), hosting, and UI-framework coupling on the analysis code.

**Options considered.**

1. Keep Streamlit as-is.
2. Migrate to Quarto: each post renders to HTML with embedded interactive Altair charts. Static, hostable on GitHub Pages. Loses dropdown filters but keeps tooltips/zoom/pan/selection (those come from Altair, not Streamlit).
3. Jupyter + nbconvert: simpler, uglier, works.
4. Marimo or Observable for only the weapon-adjustment tool; kill the rest.

**Choice.** Quarto for posts. Reconsider Marimo/Observable for the weapon-adjustment tool only if it proves load-bearing for a post; otherwise ship pre-computed scenario grids.

**Why.** The project is a "distill findings into posts" workflow, not a data-exploration app. The app's interactive surface was never used. Quarto matches the actual shape of the work and removes UI-framework coupling from the analysis code in `src/`, which is the part worth keeping. Also need a redirect/landing page at the old Streamlit URL so any Reddit/video outbound links don't 404.

### 2026-04-19 — Next post is eTTK-per-weapon, not an MnK-vs-controller redo

**Context.** The existing MnK post has real problems: causal claims that outrun a two-point before/after design, no uncertainty quantification, weapon/legend confounds, survivorship in the MnK pro pool, and a metric (shots-hit-per-damage-event) that's blind to misses. A full redo could address some but not all of these.

**Choice.** Produce the eTTK-per-weapon post first. Keep the MnK post live but reframe its language from causal to descriptive.

**Why.** eTTK-per-weapon is the project's founding premise and is genuinely novel (no one else publishes it). It also avoids MnK's two unfixable problems (misses invisible in the event feed, survivorship in the pro MnK pool). The weapon-stratification work required for a credible MnK redo falls out naturally once eTTK is done, making the MnK redo cheaper if/when we get to it.

### 2026-04-19 — Switch to uv for package management; retire Docker and pip

**Context.** Project shipped with `requirements.txt` (unpinned), two Dockerfiles (`artifact/Dockerfile`, stray `Dockerfile_2` in root), and a local `venv/`. Unpinned deps + two Docker images + a committed venv is three sources of truth for environment. Coming back after 1-2 years, reproducing the environment is friction that kills momentum.

**Choice.** uv. Single tool for env, deps, and execution. `uv run python ...` replaces Docker for local dev. Lockfile is committed; `.venv/` is gitignored.

**Why.** Fast, deterministic, modern. Docker wasn't buying isolation anyone needed on a single-developer analysis repo. The Dockerfiles can go. uv's execution model (`uv run`) removes the "did I activate the venv?" class of bugs entirely. Trimmed deps at the same time: dropped `streamlit`, `streamlit-extras`, `streamlit-dynamic-filters`, `st-btn-group`, `plotly` — all Streamlit-tier, all going away with the Quarto migration.

Pending cleanup: delete `requirements.txt`, `artifact/Dockerfile`, `Dockerfile_2`, and the old `venv/` once the uv setup is proven against a real scrape run.

### 2026-04-19 — Weapon stats via patch-notes chain, not wiki alone

**Context.** `guns_stats.csv` is a hand-maintained S21-era (mid-2024) snapshot. Any eTTK analysis against current ALGS games needs stats that reflect the current patch (S28.1, 2026-04). Candidate sources: EA patch notes, apexlegends.wiki.gg, apexlegends.fandom.com, bakersbakebread.github.io/ApexWeaponStats, TrueGameData. Event-feed data can validate damage-per-bullet and effective RPM but nothing else.

**Choice.** Multi-source reconciliation. Patch notes applied chronologically to the S21 baseline become the primary "current" signal; wiki.gg is a cross-check; fandom and bakersbakebread are deprioritised (fandom is often >1 year stale; bakersbakebread last updated 2021).

**Why.** Any single source has been demonstrably wrong on at least one weapon (Mastiff shows a different damage value across all three wikis and the CSV). Patch notes are the only source that represents authoritative intent, but they describe deltas, not absolute state, and many changes are qualitative ("increased fire rate") rather than numeric. The reconciler doesn't try to pick a winner; it shows all four values per (weapon, stat) and flags disagreements (particularly wiki.gg ≠ patches-derived) for human judgment. Unmappable bullets (hipfire spreads, hop-up reworks, firing-mode-specific damages) are preserved in a separate audit CSV so nothing is silently dropped.

Downstream implication: `guns_stats.csv` will be rewritten once a human reviews the reconciler output and resolves the ~10 real damage disagreements, ~11 magazine disagreements, and the weapon-variant gaps. Automation gets it 80% of the way; the last 20% is a judgment call per weapon.

### 2026-04-19 — Rewrite scrape_dgs.py for the new ALS site

**Context.** After the 1-2 year hiatus, apexlegendsstatus.com was fully redesigned. The old scraper's selectors (`algsRegionElem`, `algsDaysNav`, `algsGameElem`, `listText`, `gameTitle`, `gameMap`, `settings-label`) all return zero matches. The tournament-name regex (`... - Year N, Split M`) also does not match the new display format. The DGS API (`algs-public-outbound.apexlegendsstatus.com`) still works and returns the same schema (verified against a Y5 Championship game).

**Choice.** Rewrite the HTML scrape against the new, semantically clean markup; keep the DGS API calls intact. Also split the old monolithic `scrape_games_data()` so the expensive players-endpoint scrape can be filtered by `--since` date after init JSONs are downloaded.

**Why.** The new HTML uses stable-looking semantic classes (`tournament-item`, `tournament-name`, `region-card`), and the URL structure (`/algs/Y{year}-Split{split}/{type}/{region}/Overview`) carries all the routing information. This is more robust than a reverse-engineered API we have no contract with. The rewrite also simplifies the scrape: the new Overview page directly lists every game in the tournament, so the old day-by-day walking loop is gone. Side effects: `game_title` now stores the URL match slug, `game_map` stores the raw `mapImg` filename, `game_num` is empty. See "Schema quirks" in Gotchas.

### 2026-04-19 — Reframe the MnK post from causal to descriptive

**Context.** The post's title and conclusion attribute the shrinking MnK-controller gap to the Season 22 aim assist nerf. Evidence is a before/after comparison across two splits with many simultaneous patch changes. Not a causal design.

**Choice.** Update in place: keep the data and charts, rewrite title/intro/conclusion to describe the distributional shift without claiming causation. Flag limitations (shots-hit is not accuracy; survivorship; confounds).

**Why.** The descriptive content holds up. The causal framing doesn't. Rewriting framing preserves the work while removing the overclaim. Full redo deferred until eTTK-per-weapon post is out.
