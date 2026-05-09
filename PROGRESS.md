# Progress

<!-- Reverse-chronological. Newest entry on top. Stable context lives in AGENTS.md. -->

## 2026-05-04

Status: Built end-to-end WPA model for ALGS Y4 (test R² 0.62 kills, 0.71 placement, stratified per-tournament split). Pipeline lives in `src/build_match_state.py`, `src/train_wpa.py`, `src/compute_team_elo*.py`, `src/add_player_features.py`, `src/ablation_wpa.py`, `src/validate_wpa.py`, `src/analyze_top_wpa.py`, `src/analyze_impactful_plays.py`, `src/analyze_positional.py`. Honest summary at `output/wpa/STATUS.md`.

The "top impactful plays" framing didn't pay off as a deliverable: raw leverage = pivotal SITUATIONS not skillful PLAYS, and Y6 broadcast is observer-only (no team POVs released) so spot-checking events against footage isn't practical. Decision: park the highlight-plays angle, keep the pipeline and feature streams, redirect into existing weapon-balance work.

Next:

1. **Methodology writeup** ("WPA for ALGS: what the model learns and what it doesn't"). Documentation post for the analytics-curious audience. Frames the approach without overclaiming. Pulls from `output/wpa/STATUS.md` plus the ablation tables in `output/wpa/all_features_final.md` and `output/wpa/stratified_split_overview.md`. Not r/CompetitiveApex bait; long-form arxiv-style or blog post.

2. **Cannibalize the WPA pipeline into the weapon-balance work.** Five concrete opportunities (numbered for backlog):
   1. **Augment `kill_records.parquet`** with `team_HP_sum_at_engagement_start`, `team_kills_last_60s_at_start`, `team_centroid_x/y_at_start`, `dist_to_nearest_alive_team_at_start`. One merge of match_state into kill_records. Foundational; unlocks 2-5 below. Currently match_state exists for Y4 only - extend to Y5+Y6 first.
   2. **Re-cluster engagements** with HP / momentum / positional features added to `cluster_engagements.py`. Should split current 6 clusters into more meaningful archetypes (ambush vs trade, isolated vs contested, etc).
   3. **Per-cluster weapon scorecard.** Cross-tab `analyze_underrated_weapons.py` by engagement cluster. Headline framing: "weapon X is meta for situation Y but bad for situation Z" - a different and harder-to-argue-with weapon-balance angle than current usage-vs-conversion.
   4. **Player-skill-controlled weapon stats.** Use per-player KPG/DPG aggregates (already produced by `add_player_features.py`) to ask "which weapons forgive low skill" and "which weapons amplify high skill." Settles the "weapon vs player" argument that comes up in every balance discussion.
   5. **Engagement-position heatmaps per map.** Extend `analyze_positional.py` with healed-vs-down heatmaps, clutch heatmaps, density-vs-placement plots. Visual posts on their own.

Blockers: (1) needs match_state extended to Y5+Y6 before downstream work has a clean foundation. (2-5) wait on (1).

## 2026-04-22

Status: Migrated from `CLAUDE.md` + `DECISIONS.md` to `AGENTS.md` + `PROGRESS.md`. No content changes to project state.
Next: See the roadmap below for the active plan toward the first shipped eTTK-per-weapon post.

## 2026-04-20

Status: Weapon-stats pipeline complete (patch notes + wikis + history + four-way reconciliation all emitting). Y6 ALGS data fully on disk. Y5 backfill scrape running in background (~24% through, ~35h remaining).
Next: Phase A parallel work while scrape runs (reconciliation review, silent-drop fix, MnK reframe, event-data validator, Quarto migration plan).

---

## Roadmap

Ordered plan from the current state to the first shipped post.

### North-star deliverable

eTTK-per-weapon post, Quarto-rendered, published to the project's post site. Headline table + accuracy-curve chart comparing ~15 close-range weapons at three data-informed accuracy points. Honest about measurement limits. Everything below serves this.

### Phase A: Parallel work while Y5 scrape runs (no blockers)

- **A1. Weapon-stat reconciliation review.** Open [output/weapon_stats_reconciliation.md](output/weapon_stats_reconciliation.md), walk the "wiki.gg ≠ patches-derived" table (~10 damage cells + ~11 magazine cells), decide the canonical value per weapon (usually patches-derived wins when notes are explicit; wiki.gg wins when notes only had qualitative hints), add `[S28.1]`-tagged rows to `data/guns_stats.csv`, keep S21 rows as historical variants. ~30-60 min.
- **A2. Fix `player_hash_to_input.py:44` silent-drop.** Replace bare `except: continue` with explicit handling plus `logger.warning`. Audit roster coverage against current Y6 init JSONs; report unmapped nucleusHashes. ~20 min.
- **A3. Reframe MnK post** from causal to descriptive. Edit [docs/posts/mnk_vs_controller/post.md](docs/posts/mnk_vs_controller/post.md): drop the "Effect" framing, acknowledge the data can't establish causation, add a limitations paragraph. Keep charts and data. ~30 min, ships independently.
- **A4. Event-data validation layer.** New `src/validate_weapon_stats_from_events.py`. Per close-range weapon: compute per-event `damage / shots_hit` (single-bullet weapons), output mode + median + sample size. Compare against `data/weapon_current_from_patches.csv`. Smoke-test on Y6 data now; rerun after Y5. Adds a fifth column to the reconciliation report.
- **A5. Quarto migration planning.** Scan [pages/*.py](pages/), tag each as `extract business logic to src/` or `delete`. Output: a short note per page. Unblocks the Phase C migration.

### Phase B: Once Y5 scrape finishes (est. 2026-04-22)

- **B1. Run the ALGS processing pipeline** on the combined Y5+Y6 dataset: `preprocess_player_events.py` → `process_fights_breakdown.py` → `process_events.py`. Expect fixups from the HTML-redesign schema quirks. Deliverable: refreshed `data/fights_data.parquet` + per-game event tables spanning Y5 + Y6.
- **B2. Compute accuracy quantiles for eTTK reference points.** On clean events (ammo_used present, hits ≤ ammo, single-bullet weapons only): per-weapon median accuracy, pool medians, take q25 / q50 / q75. Round to nice numbers for the published table (e.g. 35% / 50% / 65%). Rerun A4's validator on the full dataset.
- **B3. Verify `damage_calculator.py`** against reconciled stats. Add `tests/` with unit tests for the pure-function parts. Pandas 3.0 / numpy 2.4 may have shifted groupby or dtype defaults; tests catch drift.

### Phase C: Write the post

- **C1. Draft eTTK-per-weapon post** as `.qmd`:
  - Headline table: eTTK at q25/q50/q75 accuracy for ~15 close-range weapons vs 200 HP target
  - Curve chart: eTTK vs accuracy, highlight 3-4 crossover pairs
  - Methodology section: explicit about what accuracy means here, what we can and can't measure
  - Limitations section: misses not observed, weapon-player selection confound, per-weapon sample sizes
- **C2. Quarto migration.** Set up `quarto` project, port the reframed MnK post and the new eTTK post as `.qmd`, build, deploy (GitHub Pages likely).

### Phase D: Cleanup

- Delete `pages/`, `Home.py`, `data_helper.py`, `dynamic_filters.py`, `streamtlit_helper.py`.
- Add the redirect page on the old Streamlit URL so outbound links from Reddit / video descriptions don't 404.
- Decide what analyses come after the first eTTK post.

### Parking lot (known, not blocking the post)

- **ALGS Open tournaments return 0 games** from the current scraper. URL structure or ordering may differ. Investigate before relying on Open-tier data.
- **`game_title` / `game_map` schema quirks** from the ALS redesign. Downstream code that greps on old formats will need patching during B1.
- **Fandom wiki is significantly stale**; treat as tertiary, not as a cross-check for recent patches.
- **Patch-note parser has ~315 unapplied bullets** (mostly correctly unmapped: qualitative, attachment-specific, hipfire). A one-hour review pass to confirm no numeric-but-unrecognized bullets are being missed would be worth it eventually.
- **Devotion excluded from analysis** (variable RPM). Either model the ramp-up or keep calling it out in posts.
- **Event feed doesn't validate** mag size, reload time, deploy / holster, or headshot / leg multipliers. For those, the reconciler has no ground truth from games; human review of wiki vs patches stands.

### Success criteria

- eTTK post publishes on the project site
- MnK post updated with honest framing
- Y5 + Y6 data processed end to end through the existing pipeline
- Streamlit app retired and replaced by Quarto
- `guns_stats.csv` reflects S28.1 balance with S21 rows preserved as history
