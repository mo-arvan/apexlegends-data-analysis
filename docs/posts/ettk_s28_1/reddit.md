# ALGS one-clip model: three major balance calls, defended with the data

I scored every firearm in the latest ALGS tournament against seven capability and speed objectives — can it crack? can it down? can it do either fast at realistic vs elite accuracy? — and three balance calls fell out clean. I'll defend each one with the figure that shows it.

## The overview: every weapon × every objective

![scorecard](../../../output/ettk_figs/01_scorecard.png)

- **Green** = margin under target, **red** = shortfall over target, **∞** = impossible at any accuracy.
- 7 objectives + a `total passed` column.
- Only **HAVOC Rifle** passes all 7. Most ARs and R-301 pass 5/7. The bottom rows (R-99, Mozambique, Wingman, P2020) pass 1–2.

One important note before the decisions: an earlier version of this analysis had a data bug using per-engagement observed mag usage as weapon mag size — that flipped Mastiff and several LMGs / snipers from "broken" to "fine" once fixed. The post below uses the corrected numbers.

## Decision 1 — R-99 **−1 damage, +3 mag (13/27 → 12/30)**

Not a straight nerf. A paired change that preserves R-99's unique niche but lowers pro dominance.

![skill metrics — R-99 in the hard-threshold / fast-ceiling corner](../../../output/ettk_figs/03_skill_metrics.png)

The scatter isolates the R-99 argument in one geometric fact: **R-99 and Wingman are the only two points on the right side of the `threshold = q75` vertical with ceiling speeds under 2s**. That corner is the mathematical "hard to unlock, fastest when you do" signature. No other weapon lives there.

The obvious nerf looking at the scorecard ("R-99 is 2/7 and over-picked, cut it") would collapse this corner — push `a_down` further right and R-99 stops being a skill-reward weapon without buffing anyone else. Meta loses diversity, nothing improves.

The paired change keeps the niche:

| version | dmg × mag | total HP/mag | `a_down` | `t_down(q100)` | miss-tolerance |
|---|---|---|---|---|---|
| current | 13 × 27 | 351 | 57% | 0.83s | 10 misses = impossible |
| proposed | 12 × 30 | 360 | 56% | 0.89s | 10 misses = still possible |

Capability holds (total HP/mag barely moves). Per-bullet damage drops, so peak speed at q100 rises ~7%. Larger mag forgives more misses. R-99 stays the precision-reward SMG — just less dominant at the pro ceiling.

## Decision 2 — P2020 needs a real buff: **+6 damage + mag 9 → 12**

P2020 is the only remaining played firearm that truly can't one-clip. Scorecard row: 1/7. `a_down = 93%`. Shortfalls on the core capability columns: **+101% on crack@q50, +110% on down@q75**. 766 shots landed.

Respawn's smallest-single-lever search returned "+1 pellet" but P2020 is a single-projectile pistol — adding a pellet changes its identity. Realistic levers are mag or damage. **+6 damage (24 → 30) combined with mag 9 → 12 takes `a_down` from 93% → 56%** without making it a shotgun. Closest path to target that keeps the weapon's character.

## Decision 3 — HAVOC Rifle and Mastiff: **don't nerf / don't buff; fix pickup friction instead**

![shotgun panel with R-99 anchor](../../../output/ettk_figs/05c_t_down_shotgun.png)

The shotgun panel shows Mastiff's `t_down` curve sits right next to Peacekeeper and safely below the R-99 anchor across the whole accuracy range. **Mastiff is capable at 42%**. Despite that, only 796 shots in the tournament.

HAVOC is the same pattern on the AR panel: **7/8 on the scorecard**, only 457 shots. And the one cell HAVOC fails is now telling the whole story: **`peek_100ms_at_q75`** — can the weapon deliver ≥ 30 HP in a 100 ms peek window? This is the objective that captures "how much damage does one trigger-pull buy you" — the thing shotguns and snipers own and auto-weapons with spin-up time can't.

| weapon | peek 100ms @ q75 | why |
|---|---|---|
| Kraber | 66 HP | one-shot sniper |
| Peacekeeper | 44 HP | 11 pellets × 11 dmg |
| Mastiff | 42 HP | 5 pellets × 19 dmg |
| Sentinel | 31 HP | 70 dmg single-shot |
| HAVOC | 18 HP | 0.42 s spin-up burns the window |
| R-99 | 11 HP | ~2 shots in 100 ms, low per-shot dmg |

So HAVOC's adoption problem is **exactly** what the peek column says: you can't peek-shoot with a weapon that spends 100 ms winding up. Drop spin-up to ~0.2 s and HAVOC's peek damage doubles (17.6 → 35 HP, passes the objective). No other scorecard cell needs to change.

**This is the release valve that justifies Decision 1's paired −damage / +mag instead of a heavy R-99 nerf.** A HAVOC spin-up tune gives pros a faster-ceiling alternative AR that doesn't require q75+ accuracy, shifting pick rate off R-99 without touching its skill-reward archetype.

## Why "one-clip" and not TTK or DPS

Earlier metrics failed: time-to-kill with reload modelling was dominated by reload at pro accuracy, creating step-function noise; sustained eDPS was linear in accuracy, so the multi-accuracy view collapsed. The one-clip model is bounded, non-linear (sharp transition at the threshold), and doesn't require guessing which secondary weapon the player swapped to — if the primary can't one-clip, its contribution to the engagement is measured.

## Caveats

- Latest-tournament sample only (patch-consistent, smaller N than season-wide).
- Expected-damage model. Stochastic fights would need binomial intervals.
- Shot location not modelled.
- Nemesis charge-mode and bolt-action mechanics are approximate.
- Movement, heals, team dynamics ignored. Firing-range math, not a fight model.

**Code + data**: [github.com/mo-arvan/apexlegends-data-analysis](https://github.com/mo-arvan/apexlegends-data-analysis). Full methodology and every CSV in [technical.md](technical.md).
