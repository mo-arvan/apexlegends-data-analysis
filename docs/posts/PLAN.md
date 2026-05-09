# 10 Days of Apex — content calendar

Ten standalone analyses dropped on r/CompetitiveApex around the S29 patch window. Half pre-patch (current meta is fresh), half post-patch (what changed, what didn't, what we predicted right/wrong).

Built on the analysis framework already in `docs/posts/ettk_s28_1/`: per-weapon scorecard with seven objectives, the threshold-gap × peak-speed scatter, and class-grouped t_down curves. Each post is a single argument with one or two charts.

## Anchor dates

`T = S29 patch ship date`. Working assumption: T ≈ 2026-05-13 to 2026-05-20 (2–3 weeks out from 2026-04-26). All other dates expressed as `T ± n`. Update once Respawn confirms.

| key date | what | constraint |
| --- | --- | --- |
| `T - 14d` | Campaign starts | Must have Y5 + Y6 reprocessed by then |
| `T - 1d`  | Last pre-patch post | "Predictions on file" recap |
| `T + 0`   | S29 drops |  |
| `T + 1d`  | Patch reaction post | Compare predicted changes vs actual |
| `T + 7d`  | Last post |  |

## The 10 posts

Each row: (working title, primary chart, status, dependencies).

### Pre-patch — what the current meta says (6 posts)

| # | day | working title | hero chart | status | depends on |
|---|---|---|---|---|---|
| 1 | T−14 | The R-99 change Respawn hasn't tried: −1 dmg + 3 mag | `proposal_r99.png` + SMG t_down curves | ✅ drafted | none |
| 2 | T−12 | P2020 is the only outclassed pistol left worth fixing | `proposal_p2020.png` + pistol t_down curves | 📝 to draft | proposal generator (built) |
| 3 | T−10 | Mozambique is one pellet away from being the best peek shotgun | `proposal_mozambique.png` + shotgun t_down curves | 📝 to draft | same |
| 4 | T−8 | Wingman: two-tap precision now needs 80% accuracy | `proposal_wingman.png` + skill_metrics with Wingman highlighted | 📝 to draft | same |
| 5 | T−6 | HAVOC and Mastiff: capable but invisible — adoption is ergonomic, not numeric | scorecard close-up + peek 100ms strip from target_strips | 📝 to draft | none |
| 6 | T−4 | The full scorecard: how every ALGS firearm scores on 7 objectives | full `01_scorecard.png` + `03_skill_metrics.png` | 📝 to draft | overview-style synthesis |

### Pre-patch — beyond weapons (1 post)

| # | day | working title | hero chart | status | depends on |
|---|---|---|---|---|---|
| 7 | T−2 | MnK vs Controller in ALGS Y6: descriptive, not causal | reused MnK eccdf charts, reframed | 📝 to rewrite | reframe existing post |

### Patch day + reaction (1 post)

| # | day | working title | hero chart | status | depends on |
|---|---|---|---|---|---|
| 8 | T+1 | S29 patch vs the scorecard's predictions: what hit and what missed | side-by-side `proposal_*` (predicted) vs actual S29 stats applied to fig 03 | 📝 build day-of | scorecard generator + S29 patch notes parsed |

### Post-patch — what the new data says (2 posts)

| # | day | working title | hero chart | status | depends on |
|---|---|---|---|---|---|
| 9 | T+4 | Zone prediction: where do ALGS finals end? | new — heatmap of final-zone centroid vs ring sequence | 📝 NEW analysis | Y5+Y6 fights data; centroid pipeline TBD |
| 10 | T+7 | The first ALGS days of S29: who actually got picked? | scorecard rerun on S29 data + delta vs pre-patch | 📝 build week-of | first S29 tournament data scraped |

## What needs to land before T−14 (~2.5 weeks)

This is the prep checklist. Anything that misses this list either gets cut from the calendar or shifts later.

### Required (must-haves)

- [ ] **Y5 scrape complete** — currently ~17h ETA. (no action; just monitor)
- [ ] **Y5+Y6 reprocessing pipeline** verified end-to-end: `preprocess_player_events.py` → fights data → events → weapon stats refreshed. (Phase B in `PROGRESS.md`)
- [ ] **Proposal-chart generator generalized** to take a (weapon, current, proposed, anchors) tuple and emit `proposal_<weapon>.png` consistently. Already built for R-99, just needs P2020 / Mozambique / Wingman / Mastiff calls in `main()`.
- [ ] **Patch-note diff parser working on S29** so post 8 can land within 24 hours of patch. (already have `parse_patch_note_deltas.py`; check it handles S29's format on patch day)
- [ ] **MnK post reframe** — small edit, mostly removing causal language.

### New analyses (build before T−14 if possible)

- [ ] **Zone prediction (post 9)**: pipeline that, given a ring sequence and game state at end-of-ring-2, predicts the final zone centroid. Could be naive (historical centroid heatmap conditioned on ring-2 location) or model-based (gradient boosting on game features). The naive version is enough for one good post.
- [ ] **Pre-flight sanity checks for S29 reactions (post 8)**: pre-build the script that takes a YAML of S29 patch deltas and re-runs the scorecard with the new numbers. Day-of authoring is then *running the script* + writing the narrative, not building infrastructure under deadline pressure.

### Nice-to-have (improves quality, not blocking)

- [ ] **30-30 Repeater `t_down` bug** investigated (max `damage_one_mag` only reaches ~163 HP — likely a damage-formula edge case for high-damage low-RPM weapons).
- [ ] **`player_hash_to_input.py:44` bare-except** fixed + audit unmapped roster hashes after Y5 lands.
- [ ] **P2020 mag verification** against wiki — `magazine_4 = 9` from patches feels low.

## Cadence + length guidance

- **Length**: 600–1000 words per post, two charts max. The R-99 post sets the bar.
- **Cadence**: ~every other day pre-patch (Days T−14, −12, −10, −8, −6, −4, −2). Daily would saturate the subreddit; biweekly looks like a victory lap.
- **Post-patch**: T+1 (reaction), T+4 (zone), T+7 (S29 first-data).
- Always lead with **identity → gap filled → how to improve** (the framework Mo asked for after the R-99 draft). Show the math; embed the chart that makes the point; close with caveats.
- ASCII punctuation throughout (workspace convention). No em dashes, no smart quotes.

## Risks

| risk | likelihood | mitigation |
|---|---|---|
| S29 ships earlier than expected | medium | Have posts 1–6 + 7 ready by T−7; can compress cadence |
| S29 ships later (delayed patch) | medium | Add a T−14 hold-over post about HAVOC ergonomics or a Y5+Y6 retro |
| Zone prediction analysis is fragile | high | Naive heatmap version is the floor; ML version optional |
| Post 8 day-of authoring slips | medium | Pre-build the run-and-narrate script; reduce day-of to text only |
| Y5 reprocessing breaks (schema drift) | medium | Phase B work in `PROGRESS.md` should catch most issues; budget a day |

## Open questions for Mo

1. **Patch date** — confirmed yet, or still estimate?
2. **Cross-post to r/apexlegends** in addition to r/CompetitiveApex? The audience is huge but lower signal — likely worth it for the patch-reaction post (post 8) only.
3. **Branding** — "10 Days of Apex" as a thread tag, or just sequential standalone posts? A pinned/linked index post might help discovery on day 1.
4. **Zone prediction scope** — naive (historical heatmap) or model-based? The naive version is post-shaped; the model would be a multi-week effort.
