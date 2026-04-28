"""One-clip analysis per weapon: time-to-crack and time-to-down, bounded by one mag.

No secondary-weapon assumption. The metric stops at the end of the primary's
magazine — if the weapon can't deal the target milestone (crack=100, down=200)
in one mag at the given accuracy, it's reported as impossible.

Core signals per weapon:
  a_crack: minimum accuracy to deal 100 HP in one mag
  a_down : minimum accuracy to deal 200 HP in one mag
  t_crack(a): time to deal 100 HP at accuracy a (bounded by one mag, else inf)
  t_down(a) : time to deal 200 HP at accuracy a (bounded by one mag, else inf)

Why this model:
- eDPS is linear in accuracy; rankings don't change across accuracies.
- eTTK with reload is dominated by reload time at pro-realistic accuracies.
- Pros swap rather than reload mid-fight; secondary is unknown and weapon-pair-
  dependent. So we model only the primary's one-mag contribution.
- This reintroduces genuine non-linearity (the one-clip threshold) and surfaces
  weapons whose problem isn't DPS but "can't down in one mag, ever" (Mastiff).

Reload is not used in this model at all. RPM and burst timing determine t_*,
mag × damage × pellets determines the one-clip thresholds.
"""

import logging
import math
import os
from dataclasses import dataclass

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

INPUT_CSV = "data/weapon_stats_for_ettk.csv"
OUT_CURVES = "data/ettk_curves.csv"
OUT_RESULTS = "data/ettk_results.csv"
OUT_FIXES = "data/ettk_fixes.csv"
OUT_SUMMARY_MD = "output/ettk_summary.md"
OUT_OBJECTIVES = "data/ettk_objectives.csv"
OUT_OBJECTIVES_WIDE = "data/ettk_objectives_wide.csv"
OUT_REBALANCE_BY_OBJ = "data/ettk_rebalance_by_objective.csv"
OUT_SKILL_METRICS = "data/ettk_skill_metrics.csv"

SHIELD_HP = 100  # purple shield (also = CRACK_HP — the milestone for "crack")
HEALTH_HP = 100  # base body HP after shield is gone
CRACK_HP = SHIELD_HP
DOWN_HP = SHIELD_HP + HEALTH_HP   # = 200, kept for backwards compat
ACC_GRID = [a / 100 for a in range(5, 96)]

# Weapons with a_down at or below this threshold are considered "one-clip
# capable" for quadrant assignment and the rebalance recommender's projected
# target. 0.50 = 50% accuracy, generously inclusive of pro-realistic accuracy.
A_DOWN_BAND = 0.50

# Multi-objective balance specification. Each entry: (name, kind, target, accuracy).
# kind = "a_crack_le" / "a_down_le" / "t_crack_le" / "t_down_le".
# For time-based objectives, `accuracy` is the accuracy at which the time must hold.
# For accuracy-threshold objectives, `accuracy` is None (the target IS an accuracy).
OBJECTIVES = [
    # name                   kind            target  accuracy     lens
    ("crack_at_q50", "a_crack_le", 0.23, None),  # pressure weapon viability
    ("crack_fast_at_q50", "t_crack_le", 2.0, 0.23),  # quick armor-break pressure
    ("down_at_q75", "a_down_le", 0.44, None),  # realistic pro one-clip
    ("down_at_50", "a_down_le", 0.50, None),  # generous pro one-clip
    ("down_feasible_at_100", "a_down_le", 1.00, None),  # physical capability
    ("down_fast_at_q75", "t_down_le", 2.0, 0.44),  # speed among capable weapons
    (
        "peak_speed_at_q100",
        "t_down_le",
        1.2,
        1.00,
    ),  # renamed from burst_speed_at_q100 (conflicted with burst-fire weapons).
        # At 100% accuracy every weapon's cadence bottleneck is pure fire rate / pellet
        # count — already the natural case for one-shot weapons, now uniform across all.
    (
        "peek_100ms_at_q75",
        "peek_100ms_ge",
        30.0,
        0.44,
    ),  # damage in a 100ms peek at q75 — rewards high-damage per-shot weapons
]


@dataclass
class Weapon:
    name: str
    damage: int
    pellets_per_shot: int
    magazine_4: int
    rpm_4: float
    reload_time_4: float  # unused in this metric; kept for provenance
    bullets_per_burst: int
    burst_fire_delay: float
    y6_shots_hit: int
    y6_accuracy_median: float
    evo_damage_multiplier: float = 1.0       # vs evo (purple) shield phase
    non_evo_damage_multiplier: float = 1.0   # vs base health phase


def _safe_float(v, default=1.0):
    try:
        if v == "" or v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _opt(x):
    """Return None for infinite values, rounded float otherwise. For CSV cells."""
    return None if x == float("inf") else round(x, 3)


def load_weapons():
    df = pd.read_csv(INPUT_CSV, na_filter=False)
    rows = []
    for _, r in df.iterrows():
        pellets = int(r["pellets_per_shot"]) if r["pellets_per_shot"] != "" else 1
        bpb = int(r["bullets_per_burst"]) if r["bullets_per_burst"] != "" else 0
        bfd = float(r["burst_fire_delay"]) if r["burst_fire_delay"] != "" else 0.0
        acc_raw = r["y6_accuracy_median"]
        try:
            acc_med = float(acc_raw) if acc_raw != "" else float("nan")
        except ValueError:
            acc_med = float("nan")
        rows.append(
            Weapon(
                name=r["weapon"],
                damage=int(r["damage"]),
                pellets_per_shot=pellets,
                magazine_4=int(r["magazine_4"]),
                rpm_4=float(r["rpm_4"]),
                reload_time_4=float(r["reload_time_4"]),
                bullets_per_burst=bpb,
                burst_fire_delay=bfd,
                y6_shots_hit=int(r["y6_shots_hit"]),
                y6_accuracy_median=acc_med,
                evo_damage_multiplier=_safe_float(r.get("evo_damage_multiplier", 1.0), 1.0),
                non_evo_damage_multiplier=_safe_float(r.get("non_evo_damage_multiplier", 1.0), 1.0),
            )
        )
    return rows


# ----- Core metric functions -----


def time_to_fire(weapon: Weapon, n_bullets: int) -> float:
    """Time (seconds) from first bullet to n-th bullet, within one mag.

    Returns inf if n_bullets > mag. Handles burst weapons explicitly:
    within-burst transitions use shot_interval, between-burst transitions
    use burst_fire_delay.
    """
    if n_bullets <= 1:
        return 0.0
    if n_bullets > weapon.magazine_4:
        return float("inf")
    shot_interval = 60.0 / weapon.rpm_4
    is_burst = weapon.bullets_per_burst > 0 and weapon.burst_fire_delay > 0
    if not is_burst:
        return (n_bullets - 1) * shot_interval
    bursts = math.ceil(n_bullets / weapon.bullets_per_burst)
    within_shots = n_bullets - bursts
    between_gaps = bursts - 1
    return within_shots * shot_interval + between_gaps * weapon.burst_fire_delay


def hits_to_milestone(weapon: "Weapon", milestone: float) -> int:
    """Hits needed at full per-bullet damage to deal `milestone` HP, with
    in-game overspill on the shield-breaking bullet.

    Wingman headshot example (d=50, head_mult=1.92, per-hit=96): bullet 1
    leaves 4 shield, bullet 2 breaks shield with 92 raw left over which lands
    on health, bullet 3 finishes. 3 hits — matches the game.

    Strict per-phase ceiling would give 4 (ceil(100/96)+ceil(100/96)) and
    waste the 92-HP overspill, which is wrong for high-damage weapons.
    """
    per_raw = weapon.damage * weapon.pellets_per_shot
    e = weapon.evo_damage_multiplier
    h = weapon.non_evo_damage_multiplier
    if per_raw <= 0 or e <= 0 or h <= 0:
        return 10**9
    if milestone <= SHIELD_HP:
        return math.ceil(milestone / (per_raw * e))
    shield = SHIELD_HP
    health = milestone - SHIELD_HP
    n_s_full = math.floor(shield / (per_raw * e))
    shield_left = shield - n_s_full * per_raw * e
    # The (n_s_full+1)-th bullet breaks the shield. Raw damage used on shield
    # is shield_left/e; remaining raw lands on health at rate h.
    raw_used = shield_left / e
    raw_left = per_raw - raw_used
    overspill_health = raw_left * h
    n_s = n_s_full + 1
    health_remaining = max(0.0, health - overspill_health)
    n_h = math.ceil(health_remaining / (per_raw * h))
    return n_s + n_h


def bullets_for_milestone(weapon: Weapon, milestone: float, accuracy: float) -> int:
    """Bullets to fire at accuracy `a` to land enough hits to deal `milestone`
    HP. Hits-to-kill computed with overspill (game-accurate); bullets fired
    are ceiling of hits-needed / accuracy.

    Wingman head at a=0.75: 3 hits / 0.75 = 4 bullets fired.
    """
    if accuracy <= 0:
        return 10**9
    hits_needed = hits_to_milestone(weapon, milestone)
    return math.ceil(hits_needed / accuracy)


def shots_in_window(weapon: Weapon, window_seconds: float) -> int:
    """Number of shots the weapon can fire in an open window starting at t=0.

    Includes the shot at t=0 plus each additional shot whose firing time
    (from t=0) is ≤ window_seconds. Caps at magazine size. Burst weapons are
    modelled with within-burst interval = 60/rpm and between-burst = burst_fire_delay.
    """
    if window_seconds < 0:
        return 0
    shot_interval = 60.0 / weapon.rpm_4
    is_burst = weapon.bullets_per_burst > 0 and weapon.burst_fire_delay > 0
    n = 1  # shot at t=0
    t = 0.0
    while n < weapon.magazine_4:
        if is_burst and (n % weapon.bullets_per_burst) == 0:
            t += weapon.burst_fire_delay
        else:
            t += shot_interval
        if t > window_seconds + 1e-9:
            break
        n += 1
    return n


def peek_damage(weapon: Weapon, window_seconds: float, accuracy: float) -> float:
    """Expected damage dealt in `window_seconds` at `accuracy`. Captures the
    'quick peek' value of a weapon — high-damage single-shot weapons (shotguns,
    snipers, Wingman) dominate short windows where fire rate can't add shots."""
    n = shots_in_window(weapon, window_seconds)
    return n * weapon.damage * weapon.pellets_per_shot * accuracy


def t_to_milestone(weapon: Weapon, accuracy: float, milestone: float) -> float:
    """Time to deal `milestone` HP. inf if not possible in one mag."""
    n = bullets_for_milestone(weapon, milestone, accuracy)
    return time_to_fire(weapon, n)


def one_clip_threshold(weapon: Weapon, milestone: float) -> float:
    """Minimum accuracy required to deal `milestone` HP in one mag.
    `a >= hits_to_kill / magazine`, with hits computed using game-accurate
    overspill on the shield-breaking bullet.
    """
    hits_needed = hits_to_milestone(weapon, milestone)
    if hits_needed >= 10**9 or hits_needed > weapon.magazine_4:
        return float("inf")
    return min(hits_needed / weapon.magazine_4, 1.0)


def damage_in_one_mag(weapon: Weapon, accuracy: float, cap: float = DOWN_HP) -> float:
    """Expected damage delivered in one mag dump, capped at `cap` (target HP).

    With phase multipliers: shield bullets at evo rate, health bullets at non_evo
    rate, summed up to mag and target HP."""
    base = weapon.damage * weapon.pellets_per_shot * accuracy
    if base <= 0:
        return 0.0
    # First spend bullets on shield up to SHIELD_HP, rest on health.
    per_evo = base * weapon.evo_damage_multiplier
    per_non_evo = base * weapon.non_evo_damage_multiplier
    if per_evo <= 0:
        return 0.0
    shield_bullets_needed = math.ceil(min(SHIELD_HP, cap) / per_evo)
    shield_bullets_used = min(shield_bullets_needed, weapon.magazine_4)
    shield_dealt = min(shield_bullets_used * per_evo, SHIELD_HP)
    if cap <= SHIELD_HP or weapon.magazine_4 <= shield_bullets_used:
        return min(shield_dealt, cap)
    remaining_bullets = weapon.magazine_4 - shield_bullets_used
    target_remaining = cap - shield_dealt
    health_dealt = min(remaining_bullets * per_non_evo, target_remaining)
    return shield_dealt + health_dealt


# ----- Accuracy quantiles -----


def compute_accuracy_quantiles(weapons):
    medians = [
        w.y6_accuracy_median for w in weapons if not math.isnan(w.y6_accuracy_median)
    ]
    s = pd.Series(medians)
    return {
        "q25": round(float(s.quantile(0.25)), 2),
        "q50": round(float(s.quantile(0.50)), 2),
        "q75": round(float(s.quantile(0.75)), 2),
        "n_weapons": len(medians),
    }


# ----- Quadrant logic based on a_down -----


def quadrant_assignment(results_list, pick_median):
    for r in results_list:
        pick_hi = r["y6_shots_hit"] >= pick_median
        a = r["a_down"] if r["a_down"] is not None else 9.99
        one_clip = a <= A_DOWN_BAND
        if pick_hi and one_clip:
            r["quadrant"] = "meta_dominant"
        elif pick_hi and not one_clip:
            r["quadrant"] = "skill_reward"
        elif not pick_hi and one_clip:
            r["quadrant"] = "underrated"
        else:
            r["quadrant"] = "outclassed"


# ----- Rebalance simulation -----


def _metric_value(weapon: Weapon, kind: str, accuracy):
    """Compute the metric value for a single objective kind."""
    if kind == "a_crack_le":
        return one_clip_threshold(weapon, CRACK_HP)
    if kind == "a_down_le":
        return one_clip_threshold(weapon, DOWN_HP)
    if kind == "t_crack_le":
        return t_to_milestone(weapon, accuracy, CRACK_HP)
    if kind == "t_down_le":
        return t_to_milestone(weapon, accuracy, DOWN_HP)
    if kind == "peek_100ms_ge":
        return peek_damage(weapon, 0.1, accuracy)
    raise ValueError(f"unknown kind {kind!r}")


def _zscore_map(values_by_weapon, higher_is_better=False):
    series = pd.Series(values_by_weapon, dtype="float64")
    mean = float(series.mean())
    std = float(series.std(ddof=0))
    if std == 0 or math.isnan(std):
        out = {weapon: 0.0 for weapon in values_by_weapon}
    else:
        out = {
            weapon: (value - mean) / std for weapon, value in values_by_weapon.items()
        }
    if higher_is_better:
        return out
    return {weapon: -score for weapon, score in out.items()}


def score_objective(weapon: Weapon, name: str, kind: str, target: float, accuracy):
    """Score a weapon against one objective. Returns a dict with value, passes, gap_pct.

    Most objectives are 'le' (lower is better) — accuracy thresholds and times.
    'ge' objectives (peek damage, currently) invert: higher is better. In both
    cases gap_pct is signed and keyed the same way: negative = pass margin,
    positive = shortfall. Scorecard colour ramp works unchanged.
    """
    val = _metric_value(weapon, kind, accuracy)
    if val == float("inf"):
        return {
            "objective": name,
            "kind": kind,
            "target": target,
            "value": None,
            "passes": False,
            "gap_pct": None,
            "impossible": True,
        }
    is_ge = kind.endswith("_ge")
    if is_ge:
        passes = val >= target - 1e-9
        # Positive gap = below target (fail). Negative = above target (margin).
        gap_pct = (target - val) / target if target > 0 else 0.0
    else:
        passes = val <= target + 1e-9
        gap_pct = (val - target) / target if target > 0 else 0.0
    return {
        "objective": name,
        "kind": kind,
        "target": target,
        "value": round(val, 4),
        "passes": bool(passes),
        "gap_pct": round(gap_pct, 4),
        "impossible": False,
    }


def find_smallest_buff_for_objective(
    weapon: Weapon, kind: str, target: float, accuracy
):
    """Search small single-lever buffs for the smallest one that passes the objective.

    Returns (lever_label, new_value, new_weapon_params) or None if no buff in the search
    space passes. Tries levers in order of intuition: mag, pellets (shotguns), damage, RPM.
    RPM only helps time-based objectives.
    """
    # If already passing, no change needed.
    base_val = _metric_value(weapon, kind, accuracy)
    if base_val != float("inf") and base_val <= target + 1e-9:
        return None

    candidates = []
    # Mag bumps
    for bump in range(1, 16):
        mod = _mod_weapon(weapon, mag=weapon.magazine_4 + bump)
        v = _metric_value(mod, kind, accuracy)
        if v != float("inf") and v <= target + 1e-9:
            candidates.append(
                (bump, f"+{bump} mag", {"mag": weapon.magazine_4 + bump}, v)
            )
            break
    # Pellet bumps (only shotguns)
    if weapon.pellets_per_shot > 1:
        for bump in range(1, 4):
            mod = _mod_weapon(weapon, pellets=weapon.pellets_per_shot + bump)
            v = _metric_value(mod, kind, accuracy)
            if v != float("inf") and v <= target + 1e-9:
                candidates.append(
                    (
                        bump + 2,
                        f"+{bump} pellet",
                        {"pellets": weapon.pellets_per_shot + bump},
                        v,
                    )
                )
                break
    # Damage bumps
    for bump in range(1, 8):
        mod = _mod_weapon(weapon, damage=weapon.damage + bump)
        v = _metric_value(mod, kind, accuracy)
        if v != float("inf") and v <= target + 1e-9:
            candidates.append(
                (bump * 2 + 5, f"+{bump} damage", {"damage": weapon.damage + bump}, v)
            )
            break
    # RPM bumps (only useful for time-based objectives)
    if kind in ("t_crack_le", "t_down_le"):
        for pct in range(5, 51, 5):
            mod = _mod_weapon(weapon, rpm=weapon.rpm_4 * (1 + pct / 100))
            v = _metric_value(mod, kind, accuracy)
            if v != float("inf") and v <= target + 1e-9:
                candidates.append(
                    (
                        pct + 15,
                        f"+{pct}% RPM",
                        {"rpm": weapon.rpm_4 * (1 + pct / 100)},
                        v,
                    )
                )
                break

    if not candidates:
        return None
    candidates.sort(key=lambda r: r[0])  # smallest-score first
    _, label, params, new_val = candidates[0]
    return {"lever": label, "new_value": round(new_val, 4), "params": params}


def _mod_weapon(w, damage=None, rpm=None, mag=None, pellets=None):
    return Weapon(
        name=w.name,
        damage=w.damage if damage is None else max(damage, 1),
        pellets_per_shot=w.pellets_per_shot if pellets is None else max(pellets, 1),
        magazine_4=w.magazine_4 if mag is None else max(mag, 1),
        rpm_4=w.rpm_4 if rpm is None else max(rpm, 1),
        reload_time_4=w.reload_time_4,
        bullets_per_burst=w.bullets_per_burst,
        burst_fire_delay=w.burst_fire_delay,
        y6_shots_hit=w.y6_shots_hit,
        y6_accuracy_median=w.y6_accuracy_median,
    )


def simulate_variants(weapon: Weapon, acc_for_time: float, directions=("buff", "nerf")):
    """Enumerate buff and/or nerf variants. Each row carries a_down and t_down(acc).

    For 'a_down' metric, only mag / damage / pellets matter (RPM doesn't shift it).
    RPM variants are included for their t_down effect.
    """
    rows = []
    base_a_down = one_clip_threshold(weapon, DOWN_HP)
    base_t_down = t_to_milestone(weapon, acc_for_time, DOWN_HP)
    rows.append(
        {
            "weapon": weapon.name,
            "variant": "baseline",
            "direction": "none",
            "a_down": round(base_a_down, 4) if base_a_down != float("inf") else None,
            "t_down_at_q50": round(base_t_down, 3)
            if base_t_down != float("inf")
            else None,
        }
    )

    buffs = [
        ("+1 damage", {"damage": weapon.damage + 1}),
        ("+2 damage", {"damage": weapon.damage + 2}),
        ("+1 mag", {"mag": weapon.magazine_4 + 1}),
        ("+3 mag", {"mag": weapon.magazine_4 + 3}),
        ("+5 mag", {"mag": weapon.magazine_4 + 5}),
        ("+1 pellet", {"pellets": weapon.pellets_per_shot + 1}),
        ("+10% RPM", {"rpm": weapon.rpm_4 * 1.10}),
        ("+20% RPM", {"rpm": weapon.rpm_4 * 1.20}),
    ]
    nerfs = [
        ("-1 damage", {"damage": weapon.damage - 1}),
        ("-2 damage", {"damage": weapon.damage - 2}),
        ("-1 mag", {"mag": weapon.magazine_4 - 1}),
        ("-3 mag", {"mag": weapon.magazine_4 - 3}),
        ("-10% RPM", {"rpm": weapon.rpm_4 * 0.90}),
        ("-20% RPM", {"rpm": weapon.rpm_4 * 0.80}),
    ]

    to_run = []
    if "buff" in directions:
        to_run.extend(("buff", *b) for b in buffs)
    if "nerf" in directions:
        to_run.extend(("nerf", *n) for n in nerfs)

    for direction, label, kwargs in to_run:
        mod = _mod_weapon(weapon, **kwargs)
        a = one_clip_threshold(mod, DOWN_HP)
        t = t_to_milestone(mod, acc_for_time, DOWN_HP)
        rows.append(
            {
                "weapon": weapon.name,
                "variant": label,
                "direction": direction,
                "a_down": round(a, 4) if a != float("inf") else None,
                "t_down_at_q50": round(t, 3) if t != float("inf") else None,
            }
        )
    return rows


def recommend_change(
    weapon: Weapon,
    baseline_a_down: float,
    variant_rows,
    quadrant: str,
    target_a_down: float = 0.50,
):
    """Pick a single recommendation per weapon.

    Outclassed / meta-dominant weapons act on a_down. Underrated and skill-reward
    picks get no numeric change — the problem lives outside the metric.
    """
    buffs = [
        r for r in variant_rows if r["direction"] == "buff" and r["a_down"] is not None
    ]
    nerfs = [
        r for r in variant_rows if r["direction"] == "nerf" and r["a_down"] is not None
    ]

    def _fmt_a(a):
        return "cannot one-clip" if a is None else f"{a * 100:.0f}%"

    if quadrant == "outclassed":
        # Find the smallest buff that brings a_down ≤ target. Prefer mag/pellet/damage
        # over RPM, since RPM doesn't affect a_down at all (it affects t_down).
        # Skip RPM buffs from the candidate set; they won't help.
        non_rpm = [b for b in buffs if "RPM" not in b["variant"]]
        good = [b for b in non_rpm if b["a_down"] <= target_a_down]
        if good:
            # Smallest buff = the one with the HIGHEST remaining a_down still ≤ target
            # (barely crosses the threshold)
            best = max(good, key=lambda r: r["a_down"])
        elif non_rpm:
            # No buff reaches target; pick the one with the lowest a_down
            best = min(non_rpm, key=lambda r: r["a_down"])
        else:
            best = None

        if best is None:
            action = "BUFF: no mag/dmg/pellet lever available"
            rationale = (
                "No mag/damage/pellet buff tested; RPM alone does not affect a_down. "
                "Combined buff likely needed."
            )
            new_a_down = baseline_a_down
        elif best["a_down"] <= target_a_down:
            action = f"BUFF: {best['variant']}"
            rationale = (
                f"a_down {_fmt_a(baseline_a_down)} → {_fmt_a(best['a_down'])}. "
                f"Smallest single-lever buff that enables one-clip at {int(target_a_down * 100)}% accuracy."
            )
            new_a_down = best["a_down"]
        else:
            action = f"BUFF: {best['variant']} (insufficient alone)"
            rationale = (
                f"a_down {_fmt_a(baseline_a_down)} → {_fmt_a(best['a_down'])}. "
                f"No single-lever preset reaches target {int(target_a_down * 100)}%; combined buff needed."
            )
            new_a_down = best["a_down"]

    elif quadrant == "meta_dominant":
        # Nerf to raise a_down toward target (makes one-clip harder), but not past 60%
        # which would make weapon noncompetitive
        upper_ok = 0.60
        raising = [n for n in nerfs if n["a_down"] > baseline_a_down]
        reachable = [n for n in raising if n["a_down"] <= upper_ok]
        if reachable:
            best = min(reachable, key=lambda r: abs(r["a_down"] - target_a_down))
            action = f"NERF (optional): {best['variant']}"
            rationale = (
                f"a_down {_fmt_a(baseline_a_down)} → {_fmt_a(best['a_down'])}. "
                f"Small nerf makes one-clip slightly harder; weapon is already heavily picked."
            )
            new_a_down = best["a_down"]
        else:
            action = "HOLD: no nerf lever moves it meaningfully"
            rationale = (
                f"baseline a_down {_fmt_a(baseline_a_down)} already near target."
            )
            new_a_down = baseline_a_down

    elif quadrant == "underrated":
        action = "HOLD numeric; address ergonomics"
        rationale = (
            f"a_down {_fmt_a(baseline_a_down)} is already one-clip-capable. "
            f"Low pick rate suggests non-numeric friction (attachments, "
            f"recoil feel, loot-pool priority)."
        )
        new_a_down = baseline_a_down

    else:  # skill_reward
        action = "HOLD; selected for non-one-clip reasons"
        rationale = (
            f"Hard to one-clip ({_fmt_a(baseline_a_down)}) but played for "
            f"range / charge mode / one-shot potential / beam consistency. "
            f"Raising one-clip capability isn't the right balance lever."
        )
        new_a_down = baseline_a_down

    return {
        "weapon": weapon.name,
        "quadrant": quadrant,
        "current_a_down": baseline_a_down if baseline_a_down != float("inf") else None,
        "recommendation": action,
        "rationale": rationale,
        "projected_a_down": new_a_down if new_a_down != float("inf") else None,
    }


# ----- Main -----


def main():
    os.makedirs("output", exist_ok=True)
    weapons = load_weapons()
    logger.info(f"Loaded {len(weapons)} weapons")
    q = compute_accuracy_quantiles(weapons)
    q25, q50, q75 = q["q25"], q["q50"], q["q75"]
    logger.info(f"Y6 accuracy quantiles: q25={q25} q50={q50} q75={q75}")

    # Curves: t_crack(a) and t_down(a) across the accuracy grid; damage_in_one_mag(a)
    curves = []
    for w in weapons:
        for a in ACC_GRID:
            t_c = t_to_milestone(w, a, CRACK_HP)
            t_d = t_to_milestone(w, a, DOWN_HP)
            dmg = damage_in_one_mag(w, a)
            curves.append(
                {
                    "weapon": w.name,
                    "accuracy": round(a, 2),
                    "t_crack": round(t_c, 4) if t_c != float("inf") else None,
                    "t_down": round(t_d, 4) if t_d != float("inf") else None,
                    "damage_one_mag": round(dmg, 2),
                }
            )
    pd.DataFrame(curves).to_csv(OUT_CURVES, index=False)
    logger.info(f"Wrote {OUT_CURVES}")

    # Per-weapon summary
    results = []
    for w in weapons:
        a_crack = one_clip_threshold(w, CRACK_HP)
        a_down = one_clip_threshold(w, DOWN_HP)
        results.append(
            {
                "weapon": w.name,
                "damage": w.damage,
                "pellets": w.pellets_per_shot,
                "mag_4": w.magazine_4,
                "rpm_4": int(w.rpm_4),
                "max_mag_damage": w.magazine_4 * w.damage * w.pellets_per_shot,
                "a_crack": round(a_crack, 4) if a_crack != float("inf") else None,
                "a_down": round(a_down, 4) if a_down != float("inf") else None,
                "t_crack_q25": _opt(t_to_milestone(w, q25, CRACK_HP)),
                "t_crack_q50": _opt(t_to_milestone(w, q50, CRACK_HP)),
                "t_crack_q75": _opt(t_to_milestone(w, q75, CRACK_HP)),
                "t_down_q25": _opt(t_to_milestone(w, q25, DOWN_HP)),
                "t_down_q50": _opt(t_to_milestone(w, q50, DOWN_HP)),
                "t_down_q75": _opt(t_to_milestone(w, q75, DOWN_HP)),
                "y6_shots_hit": w.y6_shots_hit,
                "y6_accuracy_median": None
                if math.isnan(w.y6_accuracy_median)
                else round(w.y6_accuracy_median, 3),
            }
        )

    pick_median = pd.Series([r["y6_shots_hit"] for r in results]).median()
    quadrant_assignment(results, pick_median)

    pd.DataFrame(results).sort_values(
        by=["a_down"], ascending=True, na_position="last"
    ).to_csv(OUT_RESULTS, index=False)
    logger.info(f"Wrote {OUT_RESULTS}")

    # Rebalance simulation
    fix_rows = []
    rec_rows = []
    for w, r in zip(weapons, results):
        directions = ("buff", "nerf") if r["quadrant"] == "meta_dominant" else ("buff",)
        variants = simulate_variants(w, q50, directions=directions)
        fix_rows.extend(variants)
        baseline_a = one_clip_threshold(w, DOWN_HP)
        rec = recommend_change(
            w, baseline_a, variants, r["quadrant"], target_a_down=A_DOWN_BAND
        )
        rec_rows.append(rec)
    pd.DataFrame(fix_rows).to_csv(OUT_FIXES, index=False)
    logger.info(f"Wrote {OUT_FIXES}")

    rec_path = OUT_FIXES.replace(".csv", "_recommendations.csv")
    pd.DataFrame(rec_rows).to_csv(rec_path, index=False)
    logger.info(f"Wrote {rec_path}")

    # --- Derived skill / paradox metrics ---
    threshold_gap = {}
    threshold_gap_rel = {}
    ceiling_speed = {}
    for w in weapons:
        a_down = one_clip_threshold(w, DOWN_HP)
        t_q100 = t_to_milestone(w, 1.00, DOWN_HP)
        threshold_gap[w.name] = None if a_down == float("inf") else a_down - q75
        threshold_gap_rel[w.name] = (
            None if a_down == float("inf") else (a_down - q75) / q75
        )
        ceiling_speed[w.name] = None if t_q100 == float("inf") else t_q100

    finite_threshold_gap = {k: v for k, v in threshold_gap.items() if v is not None}
    finite_ceiling_speed = {k: v for k, v in ceiling_speed.items() if v is not None}
    threshold_gap_z = _zscore_map(finite_threshold_gap, higher_is_better=True)
    ceiling_speed_z = _zscore_map(finite_ceiling_speed, higher_is_better=False)

    skill_rows = []
    for r in results:
        weapon = r["weapon"]
        a_down = r["a_down"]
        t_q100 = _metric_value(
            next(w for w in weapons if w.name == weapon), "t_down_le", 1.00
        )
        gap_abs = threshold_gap[weapon]
        gap_rel = threshold_gap_rel[weapon]
        gap_z = threshold_gap_z.get(weapon)
        speed_z = ceiling_speed_z.get(weapon)
        score = None if gap_z is None or speed_z is None else round(gap_z + speed_z, 4)
        skill_rows.append(
            {
                "weapon": weapon,
                "quadrant": r["quadrant"],
                "a_down": a_down,
                "threshold_gap_vs_q75": None if gap_abs is None else round(gap_abs, 4),
                "threshold_gap_vs_q75_pct": None
                if gap_rel is None
                else round(gap_rel, 4),
                "ceiling_speed_q100": None if t_q100 == float("inf") else round(t_q100, 4),
                "threshold_gap_z": None if gap_z is None else round(gap_z, 4),
                "ceiling_speed_z": None if speed_z is None else round(speed_z, 4),
                "skill_reward_score": score,
                "shots_landed": r["y6_shots_hit"],
            }
        )
    pd.DataFrame(skill_rows).sort_values(
        "skill_reward_score", ascending=False, na_position="last"
    ).to_csv(OUT_SKILL_METRICS, index=False)
    logger.info(f"Wrote {OUT_SKILL_METRICS}")

    # --- Multi-objective scoring ---
    obj_long_rows = []
    rebalance_obj_rows = []
    for w in weapons:
        for name, kind, target, accuracy in OBJECTIVES:
            score = score_objective(w, name, kind, target, accuracy)
            score["weapon"] = w.name
            score["accuracy_context"] = "" if accuracy is None else round(accuracy, 2)
            obj_long_rows.append(score)

            # Per-objective rebalance recommendation (only if not passing)
            if not score["passes"]:
                fix = find_smallest_buff_for_objective(w, kind, target, accuracy)
                if fix:
                    rebalance_obj_rows.append(
                        {
                            "weapon": w.name,
                            "objective": name,
                            "kind": kind,
                            "target": target,
                            "current_value": score["value"],
                            "current_impossible": score["impossible"],
                            "suggested_buff": fix["lever"],
                            "projected_value": fix["new_value"],
                        }
                    )
                else:
                    rebalance_obj_rows.append(
                        {
                            "weapon": w.name,
                            "objective": name,
                            "kind": kind,
                            "target": target,
                            "current_value": score["value"],
                            "current_impossible": score["impossible"],
                            "suggested_buff": "no single-lever buff in search range",
                            "projected_value": None,
                        }
                    )

    obj_df = pd.DataFrame(obj_long_rows)
    obj_df.to_csv(OUT_OBJECTIVES, index=False)
    logger.info(f"Wrote {OUT_OBJECTIVES}")

    # Wide format for the scorecard heatmap: one row per weapon, one column per objective.
    # Cell value = gap_pct (0 = passes, positive = gap), with "impossible" flagged separately.
    wide_passes = obj_df.pivot(index="weapon", columns="objective", values="passes")
    wide_gap = obj_df.pivot(index="weapon", columns="objective", values="gap_pct")
    wide_impossible = obj_df.pivot(
        index="weapon", columns="objective", values="impossible"
    )
    # Merge into a long-format CSV with one row per (weapon, objective, status)
    wide_gap.to_csv(OUT_OBJECTIVES_WIDE)
    logger.info(f"Wrote {OUT_OBJECTIVES_WIDE}")

    pd.DataFrame(rebalance_obj_rows).to_csv(OUT_REBALANCE_BY_OBJ, index=False)
    logger.info(f"Wrote {OUT_REBALANCE_BY_OBJ}")

    # Summary
    def _fmt_a(a):
        if a is None:
            return "∞"
        return f"{a * 100:.0f}%"

    def _fmt_t(t):
        return "—" if t is None else f"{t:.2f}s"

    lines = [
        "# One-clip analysis summary (S28.1, Y6 Pro League)",
        "",
        "Metric: **time to crack (100 HP) or down (200 HP) in one magazine**.",
        "No secondary-weapon assumption. If a weapon cannot reach the milestone in",
        "one mag at the given accuracy, time = impossible (`∞`). `a_crack` / `a_down`",
        "are the minimum accuracies required to reach each milestone in one mag.",
        "",
        f"- Y6 pro accuracy quantiles: q25={q25}  q50={q50}  q75={q75}",
        f"- Pack has {len(weapons)} weapons in scope",
        f"- One-clip-down threshold for 'capable': a_down ≤ {int(A_DOWN_BAND * 100)}%",
        "",
        "## Per weapon: one-clip thresholds and times",
        "",
        "| weapon | a_crack | a_down | t_down q25 | t_down q50 | t_down q75 | quadrant |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(
        results, key=lambda r: r["a_down"] if r["a_down"] is not None else 9.99
    ):
        lines.append(
            f"| {r['weapon']} | {_fmt_a(r['a_crack'])} | {_fmt_a(r['a_down'])} "
            f"| {_fmt_t(r['t_down_q25'])} | {_fmt_t(r['t_down_q50'])} | {_fmt_t(r['t_down_q75'])} "
            f"| {r['quadrant']} |"
        )

    lines += [
        "",
        "## Rebalance recommendations",
        "",
        f"Target: a_down ≤ {int(A_DOWN_BAND * 100)}% (weapon can one-clip down at 50% accuracy).",
        "",
        "| weapon | quadrant | current a_down | recommendation | projected a_down | rationale |",
        "|---|---|---|---|---|---|",
    ]
    rec_order = {
        "meta_dominant": 0,
        "skill_reward": 1,
        "underrated": 2,
        "outclassed": 3,
    }
    for rec in sorted(
        rec_rows,
        key=lambda r: (
            rec_order.get(r["quadrant"], 9),
            r["current_a_down"] if r["current_a_down"] is not None else 9.99,
        ),
    ):
        lines.append(
            f"| {rec['weapon']} | {rec['quadrant']} | {_fmt_a(rec['current_a_down'])} "
            f"| {rec['recommendation']} | {_fmt_a(rec['projected_a_down'])} | {rec['rationale']} |"
        )

    with open(OUT_SUMMARY_MD, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info(f"Wrote {OUT_SUMMARY_MD}")


if __name__ == "__main__":
    main()
