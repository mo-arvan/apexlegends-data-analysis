# One-clip analysis: ALGS latest tournament (S28.1)

Technical report. Reddit-audience summary in [reddit.md](reddit.md).

## What this measures

For every firearm with ≥100 shots landed in the latest ALGS tournament: **can it remove a target's 200 HP in a single magazine, and if so at what accuracy and how fast?**

Per weapon:

- `a_crack` — minimum accuracy to deal 100 HP in one mag
- `a_down` — minimum accuracy to deal 200 HP in one mag
- `t_crack(a)`, `t_down(a)` — seconds at accuracy `a`; `∞` if unreachable in one mag

Bounded by one magazine. No reload model, no secondary-weapon assumption. Earlier TTK-with-reload and sustained-eDPS models both failed (reload dominated at pro accuracy; eDPS was linear, making multi-accuracy views redundant).

## Data and scope

Damage from Y6 event mode (56k events). Mag / RPM / reload / pellets / burst delay from patch notes and wiki.gg. Accuracy quantiles from per-weapon medians in the latest tournament: **q25 = 19%, q50 = 23%, q75 = 44%**.

**25 weapons in scope** (≥100 shots landed, valid patch stats). Excluded list in [`data/weapon_stats_for_ettk_excluded.csv`](../../../data/weapon_stats_for_ettk_excluded.csv).

**Data caveat**: an earlier pipeline bug was using observed-per-engagement p99 as the weapon's magazine size, which under-counted every shotgun / LMG / sniper (pros swap before emptying mags). Fixed in this build — now trusts patches/wiki for mag. The correction flipped Mastiff from "structurally impossible" to "capable at 42%", and several LMGs / snipers from "outclassed" to "underrated".

**Objective set (8 total)**, grouped by native unit:

- *Accuracy* — `crack_at_q50`, `down_at_50`, `down_at_q75`, `down_feasible_at_100`
- *Time* — `crack_fast_at_q50`, `down_fast_at_q75`, `peak_speed_at_q100` (renamed from `burst_speed_at_q90` — "burst" conflicted with burst-fire weapons, and at 100% accuracy every weapon's cadence is already at the one-shot-weapon ceiling)
- *Damage* — `peek_100ms_at_q75` (HP delivered in a 100 ms peek window at q75 accuracy — captures high-per-trigger-pull weapons the other objectives miss)

## Archetypes and the skill-reward score

A `pick rate median × a_down ≤ 50%` split gives four archetypes:

- `meta_dominant` — picked + capable
- `skill_reward` — picked but hard to one-clip, with a fast ceiling speed
- `underrated` — capable but neglected
- `outclassed` — slow and avoided

`skill_reward_score = z(threshold_gap_vs_q75) − z(ceiling_speed_q100)`. High gap + low ceiling speed → high score. Full table: [`data/ettk_skill_metrics.csv`](../../../data/ettk_skill_metrics.csv).

## Figures

All in `output/ettk_figs/`, ordered: overview → paradox → deep dive → reference → recommendations.

| fig | file | shows |
|---|---|---|
| 01 | `01_scorecard.png` | 7-objective × 25-weapon grid, signed gap per cell |
| 02 | `02_target_strips.png` | Same 7 objectives as scatter strips on native axes |
| 03 | `03_skill_metrics.png` | `threshold_gap_vs_q75` × `ceiling_speed_q100` |
| 04 | `04_quadrants.png` | Adoption (log) × `a_down` with archetype shading |
| 05 | `05[a-h]_t_down_*.png` | `t_down` vs accuracy per class + combined, anchor weapons |
| 06 | `06_capability_heatmap.png` | Weapon × accuracy lookup table of `t_down` |
| 07 | `07_thresholds_bar.png` | `a_crack` → `a_down` bar per weapon |
| 08 | `08_rebalance_dumbbell.png` | Current vs recommended `a_down` |
| 09 | `09_fired_vs_landed.png` | Ammo used vs shots landed (log-log) |

## Three major balancing decisions

Each decision leads with the figure that defends it. The scorecard is the overview; the other figures each isolate one mechanic the decision depends on.

### 1. R-99 (and Wingman): paired **−damage / +mag** nerfs, not straight cuts

![fig 3 — skill metrics](../../../output/ettk_figs/03_skill_metrics.png)

The skill-metrics scatter is the only place in the analysis where the R-99 paradox is visible as a single geometric fact. **R-99 and Wingman are the two points on the right side of the `threshold = q75` line with ceiling speeds under 2 seconds.** That corner is the mathematical signature of "hard to one-clip but fastest when you do". No other weapon is close.

That changes the balance calculus. R-99 leads the tournament in pick rate (48,185 shots, ~3× any other SMG) but scores only 2/7 on capability objectives — the scorecard's obvious read is "nerf it". **The obvious move is wrong.** A straight mag cut or damage cut pushes `a_down` further right, which collapses the archetype entirely; the skill-reward corner of the scatter would empty. Meta diversity loses, nothing else gains.

A **paired** change preserves the archetype while lowering pro dominance:

| version | damage × mag | total HP/mag | `a_down` | `t_down(q100)` | miss-tolerance |
|---|---|---|---|---|---|
| current | 13 × 27 | 351 | 57% | 0.83s | 10 misses = impossible |
| proposed | 12 × 30 | 360 | 56% | 0.89s | 10 misses = still possible |

Capability is preserved (per-mag HP holds). Per-bullet damage drops, so peak speed at q100 rises 0.83s → 0.89s (≈7% slower). Larger mag forgives more misses. Net: R-99 stays the precision-reward weapon, but less of a pro-only one.

**Wingman** sits at `a_down = 80%`, `ceiling_speed = 1.54s`, `skill_reward_score = 2.51` — technically the highest score in the roster. But Wingman's precision reward is already aligned with its weapon class (one-shot pistol) and 1,931 shots is low enough that no change is warranted. Flag it as a secondary skill-reward case; don't tune.

### 2. P2020: the only remaining outclassed weapon with real adoption

![fig 1 — scorecard](../../../output/ettk_figs/01_scorecard.png)

The scorecard's bottom row tells the whole story: **P2020 is 1/7, with a_down = 93% and +101% / +110% shortfalls on the central capability columns**. After the Mastiff data correction, P2020 is the only played firearm that genuinely can't one-clip at realistic accuracy. 766 shots landed — not popular, but picked often enough that the weapon matters.

Respawn's search for the smallest single-lever buff returned `+1 pellet` (takes `a_down` to 46%), but P2020 is a single-projectile pistol — adding a pellet would change its identity. The realistic levers are **+mag** (9 → 15 takes `a_down` to ≈56%, +mag 9 → 18 to 47%) or **+damage** (24 → 32 takes `a_down` to 69%, 24 → 48 to 46%). A **+6 damage + mag 9 → 12** combo takes `a_down` to 56% — closest to target without changing the weapon's character.

This is a buff that stays off Respawn's usual lever-set (straight RPM or damage) precisely because RPM doesn't change capability and big damage bumps are dramatic. Mag is the cleanest path.

### 3. Mastiff and HAVOC: two "underrated, capable" cases — but different reasons

![fig 5c — shotgun panel with R-99 anchor](../../../output/ettk_figs/05c_t_down_shotgun.png)

The shotgun panel makes the Mastiff correction visible: Mastiff's curve sits right next to Peacekeeper and comfortably below the R-99 anchor across the whole accuracy range. **Mastiff is capable at 42% — it just has 796 shots of adoption.** Not a numeric balance problem.

HAVOC Rifle on the scorecard: **7/8**. Passes every capability and speed objective with margin. The one cell it fails — **`peek_100ms_at_q75` at +41% shortfall** — is the data confirmation of the ergonomic story. HAVOC's spin-up (0.42 s) means in a 100 ms peek window the weapon fires **zero usable shots**; 100 ms is spent winding up. Mastiff and Peacekeeper in the same window deliver 42 and 44 HP respectively — the damage advantage of one-trigger-pull weapons that Mastiff / Peacekeeper / Kraber cleanly own.

| weapon | peek 100ms @ q75 | spin-up / fire delay |
|---|---|---|
| Kraber | 66 HP | 0 |
| Peacekeeper | 43.6 HP | 0 |
| Mastiff | 41.8 HP | 0 |
| Sentinel | 30.8 HP | 0 |
| HAVOC | 17.6 HP | 0.42 s spin-up |
| R-99 | 11.4 HP | 0 |

**The lever for both is not numeric `a_down` or damage**. For Mastiff: pick-up friction — Dual Shell hop-up is unlock-gated this split, lowering effective DPS until late-game. For HAVOC: the spin-up. Reducing HAVOC's spin-up to ~0.2 s takes its peek damage from 17.6 → 35.2 HP (passes the peek objective), without changing `a_down` or any other row on the scorecard.

**This is the release valve that justifies Decision 1's paired −damage / +mag instead of a heavy R-99 nerf.** A HAVOC spin-up tune gives pros a faster-ceiling AR that doesn't require accuracy above q75, shifting pick rate off R-99 without touching its skill-reward archetype.

## Limitations

- Latest-tournament sample only (smaller N than season-wide, but patch-consistent).
- Expected-damage model: at exactly `a_threshold`, one-clip succeeds *on average*. Stochastic weapons need binomial intervals (v2).
- Shot location not modelled (no head/leg multipliers).
- Nemesis charge-mode power not captured.
- Gold-tier mag / reload only.
- Steady-state, single-target. No movement, heals, peeking, team dynamics.
- Patches CSV may lag the most recent in-game values for some weapons (verified Mastiff post-fix; P2020's mag_4 = 9 is worth a manual re-check against wiki).

## Reproducibility

Rerun `src/build_ettk_inputs.py && src/analyze_ettk.py && src/plot_ettk.py`. Every derived value lands in a `data/ettk_*` CSV.
