"""Altair port of the eTTK chart suite.

Mirrors the matplotlib version in `plot_ettk.py` chart-for-chart so the two
outputs can be compared side-by-side and an informed library choice made.

Output goes to `output/ettk_altair/` with the same base filenames as the
matplotlib version's `output/ettk_figs/`. Each chart produces:
  <name>.html   interactive
  <name>.svg    static vector
  <name>.png    static raster (via vl-convert-python)

Run: uv run python src/plot_ettk_altair.py

This is a parallel implementation. It does not modify any matplotlib code.
"""

import json
import logging
import os
from argparse import ArgumentParser

import altair as alt
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OUT_DIR = "output/ettk_altair"
DATA_DIR = "data"

# --- Palette + class config (mirrors plot_ettk.py) ---

# Paul Tol Vibrant — colorblind-safe.
PALETTE = ["#0077BB", "#33BBEE", "#009988", "#EE7733", "#CC3311", "#EE3377", "#BBBBBB"]

QUADRANT_COLORS = {
    "meta_dominant": "#0077BB",
    "skill_reward": "#EE7733",
    "underrated": "#009988",
    "outclassed": "#CC3311",
}
QUADRANT_BG = {
    "meta_dominant": "#a4cee5",
    "skill_reward": "#f9d6a8",
    "underrated": "#a4d8c4",
    "outclassed": "#f5b1a5",
}

CLASS_COLOR = {
    "AR": "#0077BB",
    "Assault Rifle": "#0077BB",
    "LMG": "#EE7733",
    "Marksman": "#009988",
    "Pistol": "#EE3377",
    "SMG": "#CC3311",
    "Submachine Gun": "#CC3311",
    "Shotgun": "#33BBEE",
    "Sniper": "#666666",
}
CLASS_SHAPE = {
    "AR": "circle",
    "Assault Rifle": "circle",
    "LMG": "triangle-down",
    "Marksman": "triangle-up",
    "Pistol": "cross",
    "SMG": "square",
    "Submachine Gun": "square",
    "Shotgun": "diamond",
    "Sniper": "stroke",
}

WEAPON_ABBREV = {
    "R-99 SMG": "R99", "Hemlok Breach AR": "HB", "VK-47 Flatline": "FL",
    "Alternator SMG": "AL", "Prowler Burst PDW": "PW",
    "Nemesis Burst AR": "NE", "Wingman": "WM", "Peacekeeper": "PK",
    "R-301 Carbine": "R3", "C.A.R. SMG": "CA", "Volt SMG": "VO",
    "Mozambique Shotgun": "MZ", "Mastiff Shotgun": "MS", "P2020": "P2",
    "HAVOC Rifle": "HV", "L-STAR EMG": "LS", "M600 Spitfire": "SP",
    "Rampage LMG": "RM", "EVA-8 Auto": "EV", "RE-45 Auto": "RE",
    "G7 Scout": "G7", "30-30 Repeater": "33", "Triple Take": "TT",
    "Longbow DMR": "LB", "Bocek Compound Bow": "BC",
    "Kraber .50-Cal Sniper": "KR", "Sentinel": "SN",
}

A_DOWN_TARGET = 0.50
A_CRACK_TARGET = 0.62

# --- Save helper ---

def _save(chart, name):
    """Save a chart to HTML + SVG + PNG. PNG via vl-convert-python."""
    os.makedirs(OUT_DIR, exist_ok=True)
    chart.save(os.path.join(OUT_DIR, f"{name}.html"))
    try:
        chart.save(os.path.join(OUT_DIR, f"{name}.svg"))
        chart.save(os.path.join(OUT_DIR, f"{name}.png"), ppi=150)
    except Exception as exc:
        logger.warning(f"static export failed for {name}: {exc}")
    logger.info(f"wrote {name}")


def _config(chart, title=None):
    """Apply the standard no-spines, gray-label aesthetic to a chart.

    Mirrors the matplotlib `research_vibrant.mplstyle` baseline: no view
    border, gray axis labels/titles, no axis domain lines or ticks.
    """
    base = chart.configure_view(stroke=None).configure_axis(
        labelFontSize=11,
        titleFontSize=11,
        titleColor="#666",
        labelColor="#666",
        domain=False,
        ticks=False,
    ).configure_legend(
        labelFontSize=10,
        titleFontSize=10,
        labelColor="#333",
        titleColor="#333",
    ).configure_title(
        fontSize=14,
        fontWeight="bold",
        anchor="start",
        color="#000",
    )
    return base


# --- Data loaders (read once, used across charts) ---

_data_cache = {}

def _load(name):
    if name not in _data_cache:
        _data_cache[name] = pd.read_csv(os.path.join(DATA_DIR, f"{name}.csv"))
    return _data_cache[name]


# ============================================================================
# Group A — direct ports
# ============================================================================

def chart_story(spec):
    """Port of fig_story: line + marker chart with anchor/highlight/default
    styling, optional reference lines and readout boxes.

    spec: same shape as matplotlib version's spec, with keys:
      title, outname, weapons (list of dicts), ref_lines, h_ref_lines,
      readouts, scatter_bullets.
    """
    curves = _load("ettk_curves")
    rows = []
    for entry in spec["weapons"]:
        weapon = entry["name"]
        label = entry.get("label", weapon)
        style = entry.get("style", "default")
        color_override = entry.get("color")
        overrides = entry.get("overrides", {})

        if overrides:
            # Recompute the curve from per-weapon stats with the override applied.
            sub = _curve_with_overrides(weapon, overrides, entry.get("head_mode", False))
        elif entry.get("head_mode"):
            sub = _curve_with_overrides(weapon, {}, head_mode=True)
        else:
            sub = curves[curves["weapon"] == weapon].copy()

        sub = sub[sub["t_down"].notna()].copy()
        sub["accuracy_pct"] = sub["accuracy"] * 100
        sub["label"] = label
        sub["style"] = style
        if color_override:
            sub["color"] = color_override
        rows.append(sub)

    if not rows:
        logger.warning(f"No data for {spec['outname']}")
        return
    df = pd.concat(rows, ignore_index=True)

    # Three-tier styling. Anchors are muted grey + dashed, highlights are bold.
    anchor_df = df[df["style"] == "anchor"]
    highlight_df = df[df["style"] == "highlight"]
    default_df = df[df["style"] == "default"]

    color_scale = alt.Scale(
        domain=list(df["label"].unique()),
        range=[entry.get("color", PALETTE[i % len(PALETTE)])
               for i, entry in enumerate(spec["weapons"])],
    )

    layers = []

    # Anchors (greyed background)
    if not anchor_df.empty:
        anchor_line = (
            alt.Chart(anchor_df)
            .mark_line(interpolate="step-after", strokeDash=[5, 2],
                       strokeWidth=1.5, color="#999", opacity=0.85)
            .encode(
                x=alt.X("accuracy_pct:Q"),
                y=alt.Y("t_down:Q"),
                detail="label:N",
            )
        )
        layers.append(anchor_line)

    # Defaults (palette colour)
    if not default_df.empty:
        default_line = (
            alt.Chart(default_df)
            .mark_line(interpolate="step-after", strokeWidth=2.0,
                       point=alt.OverlayMarkDef(size=40))
            .encode(
                x=alt.X("accuracy_pct:Q"),
                y=alt.Y("t_down:Q"),
                color=alt.Color("label:N", scale=color_scale,
                                legend=alt.Legend(
                                    orient="top", title=None,
                                    direction="horizontal", columns=4,
                                )),
            )
        )
        layers.append(default_line)

    # Highlights (bolder line, larger markers)
    if not highlight_df.empty:
        highlight_line = (
            alt.Chart(highlight_df)
            .mark_line(interpolate="step-after", strokeWidth=3.0,
                       point=alt.OverlayMarkDef(size=80, filled=True))
            .encode(
                x=alt.X("accuracy_pct:Q"),
                y=alt.Y("t_down:Q"),
                color=alt.Color("label:N", scale=color_scale),
            )
        )
        layers.append(highlight_line)

    # Reference lines (vertical and horizontal)
    for ref in spec.get("ref_lines", []):
        rule = alt.Chart(pd.DataFrame({"x": [ref["x"]]})).mark_rule(
            color=ref.get("color", "#888"), strokeDash=[3, 3], strokeWidth=1.0,
        ).encode(x="x:Q")
        layers.append(rule)
    for ref in spec.get("h_ref_lines", []):
        rule = alt.Chart(pd.DataFrame({"y": [ref["y"]]})).mark_rule(
            color=ref.get("color", "#888"), strokeDash=[3, 3], strokeWidth=1.0,
        ).encode(y="y:Q")
        layers.append(rule)

    chart = alt.layer(*layers).properties(
        width=720,
        height=380,
        title=spec["title"],
    ).encode(
        x=alt.X("accuracy_pct:Q",
                title="accuracy (%)",
                scale=alt.Scale(domain=[
                    spec.get("x_min", df["accuracy_pct"].min() - 2),
                    spec.get("x_max", 100),
                ]),
                axis=alt.Axis(grid=False)),
        y=alt.Y("t_down:Q",
                title="time to down (s)",
                scale=alt.Scale(domain=[
                    spec.get("y_min", max(0.5, df["t_down"].min() - 0.1)),
                    spec.get("y_max", min(5.5, df["t_down"].max() + 0.1)),
                ]),
                axis=alt.Axis(grid=True, gridOpacity=0.22)),
    )
    chart = _config(chart)
    _save(chart, spec["outname"])


def _curve_with_overrides(weapon, overrides, head_mode=False):
    """Recompute the eTTK curve for a weapon with stat overrides applied.

    Replicates analyze_ettk's logic (overspill model, integer hits) using
    the per-weapon row from weapon_stats_for_ettk.csv.
    """
    stats_df = _load("weapon_stats_for_ettk")
    row = stats_df[stats_df["weapon"] == weapon]
    if row.empty:
        return pd.DataFrame(columns=["weapon", "accuracy", "t_down"])
    row = row.iloc[0].to_dict()
    damage = overrides.get("damage", row["damage"])
    mag = overrides.get("magazine_4", row["magazine_4"])
    rpm = overrides.get("rpm_4", row["rpm_4"])
    head_mult = row.get("head_multiplier", 1.0) if head_mode else 1.0
    pellets = row.get("pellets_per_shot") or 1
    if pd.isna(pellets):
        pellets = 1
    per_hit = damage * pellets * head_mult
    if not per_hit or per_hit <= 0:
        return pd.DataFrame(columns=["weapon", "accuracy", "t_down"])

    out = []
    for acc_int in range(5, 101):
        a = acc_int / 100.0
        # Shield phase
        k_s = -(-100 // per_hit)
        shield_remaining = 100 - (k_s - 1) * per_hit
        spill = per_hit - shield_remaining
        # Health phase
        health_left = 100 - spill
        if health_left <= 0:
            k_h = 0
        else:
            k_h = -(-int(health_left) // per_hit) if per_hit > 0 else 0
        k = k_s + k_h
        n = -(-k // a) if a > 0 else float("inf")
        if n > mag:
            t = None
        else:
            t = (n - 1) * 60.0 / rpm
        out.append({"weapon": weapon, "accuracy": a, "t_down": t})
    return pd.DataFrame(out)


def chart_quadrants():
    """04_quadrants: scatter with quadrant rect backgrounds + reference lines."""
    df = _load("ettk_results").copy()
    df = df[df["a_down"].notna()]
    df["a_down_pct"] = df["a_down"] * 100
    df["shots"] = df["y6_shots_hit"].fillna(1).clip(lower=1)

    pick_median = df["shots"].median()

    # Quadrant background rectangles. The chart is split at a_down=50% (the
    # threshold target) and shots = pick-rate median.
    bg = pd.DataFrame([
        {"q": "underrated", "x1": 0, "x2": A_DOWN_TARGET * 100,
         "y1": pick_median, "y2": df["shots"].max() * 1.5},
        {"q": "meta_dominant", "x1": A_DOWN_TARGET * 100, "x2": 100,
         "y1": pick_median, "y2": df["shots"].max() * 1.5},
        {"q": "outclassed", "x1": 0, "x2": A_DOWN_TARGET * 100,
         "y1": 1, "y2": pick_median},
        {"q": "skill_reward", "x1": A_DOWN_TARGET * 100, "x2": 100,
         "y1": 1, "y2": pick_median},
    ])

    bg_layer = alt.Chart(bg).mark_rect(opacity=0.25).encode(
        x=alt.X("x1:Q"), x2="x2:Q",
        y=alt.Y("y1:Q"), y2="y2:Q",
        color=alt.Color("q:N",
                        scale=alt.Scale(domain=list(QUADRANT_BG),
                                        range=list(QUADRANT_BG.values())),
                        legend=alt.Legend(
                            orient="top", title=None, direction="horizontal",
                        )),
    )

    points = alt.Chart(df).mark_circle(size=80, opacity=0.9).encode(
        x=alt.X("a_down_pct:Q",
                title="accuracy required to one-clip down",
                scale=alt.Scale(domain=[0, 105])),
        y=alt.Y("shots:Q",
                title="shots landed in Y6 (log)",
                scale=alt.Scale(type="log")),
        color=alt.Color("quadrant:N",
                        scale=alt.Scale(domain=list(QUADRANT_COLORS),
                                        range=list(QUADRANT_COLORS.values())),
                        legend=None),
        tooltip=["weapon", "a_down_pct", "shots", "quadrant"],
    )

    labels = alt.Chart(df).mark_text(align="left", baseline="middle",
                                     dx=8, fontSize=9, color="#333").encode(
        x=alt.X("a_down_pct:Q"), y=alt.Y("shots:Q"), text="weapon:N",
    )

    target = alt.Chart(pd.DataFrame({"x": [A_DOWN_TARGET * 100]})).mark_rule(
        color="#CC3311", strokeDash=[3, 3], strokeWidth=1.2,
    ).encode(x="x:Q")
    median = alt.Chart(pd.DataFrame({"y": [pick_median]})).mark_rule(
        color="#888", strokeDash=[1, 3], strokeWidth=1.0,
    ).encode(y="y:Q")

    chart = alt.layer(bg_layer, target, median, points, labels).properties(
        width=700, height=480, title="Weapon meta map",
    )
    chart = _config(chart)
    _save(chart, "04_quadrants")


def chart_fired_vs_landed():
    """09_fired_vs_landed: log-log scatter of ammo used vs shots landed."""
    results = _load("ettk_results")
    stats = _load("weapon_stats_for_ettk")
    merged = results.merge(
        stats[["weapon", "y6_ammo_used_sum"]],
        on="weapon", how="left",
    )
    df = merged[merged["y6_shots_hit"].notna() & merged["y6_ammo_used_sum"].notna()].copy()
    df = df[(df["y6_shots_hit"] > 0) & (df["y6_ammo_used_sum"] > 0)]
    df["accuracy_pct"] = (df["y6_shots_hit"] / df["y6_ammo_used_sum"] * 100).round(0)
    df["weapon_label"] = df["weapon"] + " (" + df["accuracy_pct"].astype(int).astype(str) + "%)"

    points = alt.Chart(df).mark_circle(size=120, opacity=0.9).encode(
        x=alt.X("y6_ammo_used_sum:Q",
                title="ammo used in latest tournament",
                scale=alt.Scale(type="log")),
        y=alt.Y("y6_shots_hit:Q",
                title="shots landed in latest tournament",
                scale=alt.Scale(type="log")),
        color=alt.Color("quadrant:N",
                        scale=alt.Scale(domain=list(QUADRANT_COLORS),
                                        range=list(QUADRANT_COLORS.values())),
                        legend=alt.Legend(
                            orient="top", title=None, direction="horizontal",
                        )),
        tooltip=["weapon", "y6_ammo_used_sum", "y6_shots_hit", "accuracy_pct"],
    )
    labels = alt.Chart(df).mark_text(align="left", baseline="middle",
                                     dx=8, fontSize=9, color="#333").encode(
        x="y6_ammo_used_sum:Q", y="y6_shots_hit:Q", text="weapon_label:N",
    )

    # 1:1 line. Compute over the data range.
    diag_min = max(1.0, min(df["y6_ammo_used_sum"].min(), df["y6_shots_hit"].min()))
    diag_max = max(df["y6_ammo_used_sum"].max(), df["y6_shots_hit"].max())
    diag = alt.Chart(pd.DataFrame({
        "x": [diag_min, diag_max], "y": [diag_min, diag_max],
    })).mark_line(strokeDash=[5, 3], color="#888", strokeWidth=1.0).encode(
        x="x:Q", y="y:Q",
    )

    chart = alt.layer(diag, points, labels).properties(
        width=700, height=460, title="Fired vs landed volume",
    )
    chart = _config(chart)
    _save(chart, "09_fired_vs_landed")


def chart_proposal_r99():
    """proposal_r99: scatter of skill metrics, R-99 current + proposed.

    A simplified port that captures the essence (current vs proposed marker
    overlay against background skill-metric scatter).
    """
    sm = _load("ettk_skill_metrics").copy()
    sm = sm[sm["threshold_gap_vs_q75"].notna() & sm["ceiling_speed_q100"].notna()]
    sm["threshold_gap_vs_q75"] = sm["threshold_gap_vs_q75"] * 100

    bg = alt.Chart(sm).mark_circle(size=40, opacity=0.45, color="#bbb").encode(
        x=alt.X("threshold_gap_vs_q75:Q",
                title="accuracy gap above q75 (points)"),
        y=alt.Y("ceiling_speed_q100:Q",
                title="time to down at 100% accuracy (s)"),
    )

    # R-99 current
    current_row = sm[sm["weapon"] == "R-99 SMG"]
    if current_row.empty:
        chart = bg.properties(width=720, height=400, title="R-99 SMG: proposed change")
        _save(_config(chart), "proposal_r99")
        return

    current_pt = alt.Chart(current_row).mark_point(
        shape="square", filled=True, size=240, color="#EE7733",
    ).encode(x="threshold_gap_vs_q75:Q", y="ceiling_speed_q100:Q")

    # Proposed: damage 12, mag 30. Recompute t_down at 100% acc.
    proposed_curve = _curve_with_overrides("R-99 SMG", {"damage": 12, "magazine_4": 30})
    proposed_t100 = proposed_curve[proposed_curve["accuracy"] == 1.0]["t_down"]
    if not proposed_t100.empty:
        # threshold_gap shifts because a_down changes from 59% → 57%
        proposed_row = pd.DataFrame([{
            "weapon": "R-99 SMG (proposed)",
            "threshold_gap_vs_q75": current_row.iloc[0]["threshold_gap_vs_q75"] - 2,
            "ceiling_speed_q100": float(proposed_t100.iloc[0]),
        }])
        proposed_pt = alt.Chart(proposed_row).mark_point(
            shape="square", filled=False, size=240, color="#EE7733",
            strokeWidth=2.5,
        ).encode(x="threshold_gap_vs_q75:Q", y="ceiling_speed_q100:Q")
    else:
        proposed_pt = alt.Chart(pd.DataFrame()).mark_point()

    legend_data = pd.DataFrame([
        {"label": "current", "x": 0, "y": 0},
        {"label": "proposed", "x": 0, "y": 0},
    ])

    chart = alt.layer(bg, current_pt, proposed_pt).properties(
        width=720, height=400, title="R-99 SMG: proposed change",
    )
    chart = _config(chart)
    _save(chart, "proposal_r99")


# ============================================================================
# Group B — medium ports
# ============================================================================

def chart_t_down_class(class_key, class_display, anchor_weapon, outname):
    """05a-g: per-class t_down curves + shots-landed bar composite."""
    curves = _load("ettk_curves")
    stats = _load("weapon_stats_for_ettk")

    class_weapons = stats[stats["class"].isin([class_key, class_key.replace("_", " ")])]["weapon"].tolist()
    if not class_weapons:
        # Try fuzzy match for class names like "Submachine Gun" / "SMG"
        class_aliases = {
            "AR": ["Assault Rifle", "AR"],
            "SMG": ["Submachine Gun", "SMG"],
            "LMG": ["LMG"],
            "Pistol": ["Pistol"],
            "Marksman": ["Marksman"],
            "Sniper": ["Sniper"],
            "Shotgun": ["Shotgun"],
        }
        names = class_aliases.get(class_key, [class_key])
        class_weapons = stats[stats["class"].isin(names)]["weapon"].tolist()

    panel_weapons = class_weapons + [anchor_weapon] if anchor_weapon and anchor_weapon not in class_weapons else class_weapons
    sub = curves[curves["weapon"].isin(panel_weapons) & curves["t_down"].notna()].copy()
    if sub.empty:
        logger.warning(f"No curve data for {outname}")
        return
    sub["accuracy_pct"] = sub["accuracy"] * 100
    sub["is_anchor"] = sub["weapon"] == anchor_weapon

    # Distinguish anchor weapon visually.
    sub["weapon_display"] = sub.apply(
        lambda r: f"{r['weapon']} (anchor)" if r["is_anchor"] else r["weapon"],
        axis=1,
    )

    color_domain = sub["weapon_display"].unique().tolist()
    color_range = []
    for w in color_domain:
        if "(anchor)" in w:
            color_range.append("#999999")
        else:
            color_range.append(PALETTE[len(color_range) % len(PALETTE)])

    line = alt.Chart(sub).mark_line(interpolate="step-after",
                                    point=alt.OverlayMarkDef(size=40)).encode(
        x=alt.X("accuracy_pct:Q",
                title="accuracy (%)",
                axis=alt.Axis(grid=False)),
        y=alt.Y("t_down:Q",
                title="time to down (seconds)",
                scale=alt.Scale(domain=[0.7, 5.5]),
                axis=alt.Axis(grid=True, gridOpacity=0.22)),
        color=alt.Color("weapon_display:N",
                        scale=alt.Scale(domain=color_domain, range=color_range),
                        legend=alt.Legend(
                            orient="top", title=None, direction="horizontal",
                            columns=4,
                        )),
        strokeDash=alt.condition(
            alt.datum.is_anchor,
            alt.value([5, 2]), alt.value([1, 0]),
        ),
        size=alt.condition(
            alt.datum.is_anchor,
            alt.value(1.4), alt.value(2.5),
        ),
    ).properties(
        width=720, height=320,
        title=f"Down time vs accuracy — {class_display}",
    )

    # Bar chart of shots landed
    shots_df = stats[stats["weapon"].isin(panel_weapons)].copy()
    shots_df = shots_df[shots_df["y6_shots_hit"].fillna(0) > 0]
    shots_df["weapon_display"] = shots_df.apply(
        lambda r: f"{r['weapon']} (anchor)" if r["weapon"] == anchor_weapon else r["weapon"],
        axis=1,
    )
    shots_df = shots_df.sort_values("y6_shots_hit", ascending=False)

    bars = alt.Chart(shots_df).mark_bar().encode(
        x=alt.X("y6_shots_hit:Q",
                title="shots landed in latest tournament (log scale)",
                scale=alt.Scale(type="log")),
        y=alt.Y("weapon_display:N", sort="-x", title=None),
        color=alt.Color("weapon_display:N",
                        scale=alt.Scale(domain=color_domain, range=color_range),
                        legend=None),
    ).properties(
        width=720, height=max(60, 32 * len(shots_df)),
        title="Shots landed",
    )
    bar_labels = alt.Chart(shots_df).mark_text(
        align="left", baseline="middle", dx=4, fontSize=9, color="#333",
    ).encode(
        x="y6_shots_hit:Q", y=alt.Y("weapon_display:N", sort="-x"),
        text=alt.Text("y6_shots_hit:Q", format=",.0f"),
    )

    composite = alt.vconcat(line, alt.layer(bars, bar_labels)).resolve_scale(
        color="shared",
    )
    composite = _config(composite)
    _save(composite, outname)


def chart_thresholds_bar():
    """07_thresholds_bar: lollipop chart of a_crack and a_down per weapon."""
    df = _load("ettk_results").copy()
    df = df[df["a_down"].notna() | df["a_crack"].notna()]
    df["a_crack_pct"] = (df["a_crack"] * 100).fillna(0)
    df["a_down_pct"] = (df["a_down"] * 100).fillna(100)
    df = df.sort_values("a_down_pct")

    # Stems
    stems = alt.Chart(df).mark_rule(strokeWidth=2.5).encode(
        x=alt.X("a_crack_pct:Q",
                title="accuracy required to one-clip",
                scale=alt.Scale(domain=[0, 105])),
        x2="a_down_pct:Q",
        y=alt.Y("weapon:N", sort=df["weapon"].tolist(), title=None),
        color=alt.Color("quadrant:N",
                        scale=alt.Scale(domain=list(QUADRANT_COLORS),
                                        range=list(QUADRANT_COLORS.values())),
                        legend=alt.Legend(orient="top", title=None,
                                          direction="horizontal")),
    )
    crack_dots = alt.Chart(df).mark_point(filled=False, size=120,
                                          strokeWidth=2.0).encode(
        x="a_crack_pct:Q", y=alt.Y("weapon:N", sort=df["weapon"].tolist()),
        color=alt.Color("quadrant:N",
                        scale=alt.Scale(domain=list(QUADRANT_COLORS),
                                        range=list(QUADRANT_COLORS.values())),
                        legend=None),
    )
    down_dots = alt.Chart(df).mark_point(filled=True, size=140).encode(
        x="a_down_pct:Q", y=alt.Y("weapon:N", sort=df["weapon"].tolist()),
        color=alt.Color("quadrant:N",
                        scale=alt.Scale(domain=list(QUADRANT_COLORS),
                                        range=list(QUADRANT_COLORS.values())),
                        legend=None),
    )
    end_labels = alt.Chart(df).mark_text(align="left", baseline="middle",
                                         dx=8, fontSize=9, color="#333").encode(
        x="a_down_pct:Q", y=alt.Y("weapon:N", sort=df["weapon"].tolist()),
        text=alt.Text("a_down_pct:Q", format=".0f"),
    )

    target = alt.Chart(pd.DataFrame({"x": [A_DOWN_TARGET * 100]})).mark_rule(
        color="#CC3311", strokeDash=[3, 3], strokeWidth=1.0,
    ).encode(x="x:Q")

    chart = alt.layer(target, stems, crack_dots, down_dots, end_labels).properties(
        width=620, height=max(400, 22 * len(df)),
        title="One-clip thresholds per weapon",
    )
    chart = _config(chart)
    _save(chart, "07_thresholds_bar")


def chart_rebalance_dumbbell():
    """08_rebalance_dumbbell: dumbbell chart with directional Unicode arrows."""
    df = _load("ettk_results").copy()
    fixes = _load("ettk_fixes_recommendations")
    df = df.merge(fixes[["weapon", "projected_a_down", "recommendation"]],
                  on="weapon", how="left")
    df = df[df["a_down"].notna()]
    df["current_pct"] = df["a_down"] * 100
    df["proj_pct"] = df["projected_a_down"].fillna(df["a_down"]) * 100
    df["delta"] = df["proj_pct"] - df["current_pct"]
    df["dir_label"] = df["recommendation"].fillna("hold")
    df["delta_color"] = df["delta"].apply(
        lambda d: "#CC3311" if d > 0 else ("#009988" if d < 0 else "#999999")
    )
    df = df.sort_values("current_pct")

    stems = alt.Chart(df).mark_rule(strokeWidth=2.0).encode(
        x=alt.X("current_pct:Q", title="accuracy required to one-clip down",
                scale=alt.Scale(domain=[0, 105])),
        x2="proj_pct:Q",
        y=alt.Y("weapon:N", sort=df["weapon"].tolist(), title=None),
        color=alt.Color("delta_color:N", scale=None, legend=None),
    )
    start_dots = alt.Chart(df).mark_point(filled=True, size=110).encode(
        x="current_pct:Q", y=alt.Y("weapon:N", sort=df["weapon"].tolist()),
        color=alt.Color("quadrant:N",
                        scale=alt.Scale(domain=list(QUADRANT_COLORS),
                                        range=list(QUADRANT_COLORS.values())),
                        legend=alt.Legend(orient="top", title=None,
                                          direction="horizontal")),
    )
    proj_df = df[df["delta"].abs() > 0.01]
    proj_dots = alt.Chart(proj_df).mark_point(
        filled=True, size=110,
    ).encode(
        x="proj_pct:Q", y=alt.Y("weapon:N", sort=df["weapon"].tolist()),
        color=alt.Color("delta_color:N", scale=None, legend=None),
    )
    rec_labels = alt.Chart(df).mark_text(align="left", baseline="middle",
                                         dx=8, fontSize=8, color="#333",
                                         fontStyle="italic").encode(
        x="proj_pct:Q", y=alt.Y("weapon:N", sort=df["weapon"].tolist()),
        text="dir_label:N",
    )
    target = alt.Chart(pd.DataFrame({"x": [A_DOWN_TARGET * 100]})).mark_rule(
        color="#CC3311", strokeDash=[3, 3], strokeWidth=1.0,
    ).encode(x="x:Q")

    chart = alt.layer(target, stems, start_dots, proj_dots, rec_labels).properties(
        width=620, height=max(400, 22 * len(df)),
        title="Rebalance suggestions",
    )
    chart = _config(chart)
    _save(chart, "08_rebalance_dumbbell")


# ============================================================================
# Group C — hard ports
# ============================================================================

def chart_capability_heatmap():
    """06_capability_heatmap: per-weapon t_down at fixed accuracy points."""
    curves = _load("ettk_curves").copy()
    accs = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80]
    df = curves[curves["accuracy"].isin(accs)].copy()
    df["accuracy_pct"] = (df["accuracy"] * 100).astype(int).astype(str) + "%"
    df["t_down_clipped"] = df["t_down"].fillna(99)  # ∞ marker placeholder
    df["display"] = df["t_down"].apply(
        lambda v: "∞" if pd.isna(v) else f"{v:.1f}"
    )

    # Order weapons by total damage at q100 (proxy for ranking).
    weapon_order = (
        df[df["accuracy"] == 0.80].sort_values("t_down").dropna(subset=["t_down"])["weapon"].tolist()
    )
    other = [w for w in df["weapon"].unique() if w not in weapon_order]
    weapon_order = weapon_order + other

    cells = alt.Chart(df).mark_rect().encode(
        x=alt.X("accuracy_pct:O", title="accuracy",
                axis=alt.Axis(orient="bottom")),
        y=alt.Y("weapon:N", sort=weapon_order, title=None),
        color=alt.condition(
            alt.datum.t_down_clipped == 99,
            alt.value("#cccccc"),
            alt.Color("t_down_clipped:Q",
                      scale=alt.Scale(scheme="redyellowgreen", reverse=True,
                                      domain=[1.0, 4.5]),
                      legend=alt.Legend(title="seconds")),
        ),
    )
    text = alt.Chart(df).mark_text(fontSize=10, color="#000").encode(
        x=alt.X("accuracy_pct:O"),
        y=alt.Y("weapon:N", sort=weapon_order),
        text="display:N",
    )

    chart = alt.layer(cells, text).properties(
        width=400, height=max(400, 22 * len(weapon_order)),
        title="One-clip down time (seconds)",
    )
    chart = _config(chart)
    _save(chart, "06_capability_heatmap")


def chart_scorecard():
    """01_scorecard: multi-objective balance scorecard heatmap.

    Note: this is a complex port. Diverging color scale + ∞ cells + summary
    column. Altair doesn't have a direct equivalent of matplotlib's TwoSlopeNorm
    so the color domain is symmetric around 0.
    """
    obj = _load("ettk_objectives").copy()
    if obj.empty:
        logger.warning("ettk_objectives empty; skipping 01_scorecard")
        return
    # Each (weapon, objective) cell. signed_gap is positive when worse than target.
    obj["display"] = obj.apply(lambda r: (
        "∞" if r["impossible"] else f"{r['gap_pct']:+.0f}%"
    ), axis=1)
    obj["gap_pct_clip"] = obj["gap_pct"].clip(-150, 150).fillna(0)

    objective_order = obj["objective"].drop_duplicates().tolist()
    weapon_order = (
        obj.groupby("weapon")["passes"].sum()
        .sort_values(ascending=False).index.tolist()
    )

    cell_w = 70
    cell_h = 22
    n_obj = len(objective_order)
    n_wep = len(weapon_order)
    cells = alt.Chart(obj).mark_rect().encode(
        x=alt.X("objective:O", sort=objective_order, title=None,
                axis=alt.Axis(orient="bottom", labelAngle=-30)),
        y=alt.Y("weapon:N", sort=weapon_order, title=None),
        color=alt.condition(
            alt.datum.impossible,
            alt.value("#cccccc"),
            alt.Color("gap_pct_clip:Q",
                      scale=alt.Scale(scheme="redyellowgreen",
                                      reverse=True, domain=[-150, 150]),
                      legend=alt.Legend(title="gap from target (%)",
                                        orient="bottom")),
        ),
    )
    text = alt.Chart(obj).mark_text(fontSize=8, color="#000").encode(
        x=alt.X("objective:O", sort=objective_order),
        y=alt.Y("weapon:N", sort=weapon_order),
        text="display:N",
    )

    # Summary column: passed/total
    summary = obj.groupby("weapon").agg(
        passed=("passes", "sum"),
        total=("passes", "count"),
    ).reset_index()
    summary["display"] = summary["passed"].astype(str) + "/" + summary["total"].astype(str)
    summary["objective"] = "total\npassed"
    summary["pass_pct"] = summary["passed"] / summary["total"]

    summary_cells = alt.Chart(summary).mark_rect().encode(
        x=alt.X("objective:O"),
        y=alt.Y("weapon:N", sort=weapon_order),
        color=alt.Color("pass_pct:Q",
                        scale=alt.Scale(scheme="greens", domain=[0, 1]),
                        legend=None),
    )
    summary_text = alt.Chart(summary).mark_text(fontSize=8, color="#000").encode(
        x=alt.X("objective:O"),
        y=alt.Y("weapon:N", sort=weapon_order),
        text="display:N",
    )

    main = alt.layer(cells, text).properties(
        width=cell_w * n_obj, height=cell_h * n_wep,
    )
    summary_view = alt.layer(summary_cells, summary_text).properties(
        width=cell_w, height=cell_h * n_wep,
    )

    chart = alt.hconcat(main, summary_view).properties(
        title="Multi-objective balance scorecard - signed gap from target per cell",
    )
    chart = _config(chart)
    _save(chart, "01_scorecard")


def chart_target_strips():
    """02_target_strips: 8 stacked scatter strips, one per objective."""
    obj = _load("ettk_objectives").copy()
    stats = _load("weapon_stats_for_ettk")

    obj = obj.merge(stats[["weapon", "class", "y6_shots_hit"]],
                    on="weapon", how="left")
    obj["y6_shots_hit"] = obj["y6_shots_hit"].fillna(1).clip(lower=1)
    obj["abbr"] = obj["weapon"].map(WEAPON_ABBREV).fillna(obj["weapon"].str[:3])

    panels = []
    for objective in obj["objective"].drop_duplicates():
        sub = obj[obj["objective"] == objective].copy()
        target = sub["target"].iloc[0] if not sub.empty else None
        kind = sub["kind"].iloc[0] if not sub.empty else "value"
        sub["passing"] = sub["passes"].astype(bool)

        scatter = alt.Chart(sub).mark_point(size=80, filled=True).encode(
            x=alt.X("value:Q", title=f"{objective} ({kind})"),
            y=alt.Y("y6_shots_hit:Q",
                    title="shots landed (log)",
                    scale=alt.Scale(type="log")),
            color=alt.Color("class:N",
                            scale=alt.Scale(domain=list(CLASS_COLOR.keys()),
                                            range=list(CLASS_COLOR.values())),
                            legend=alt.Legend(orient="bottom",
                                              title=None,
                                              direction="horizontal")),
            shape=alt.Shape("class:N",
                            scale=alt.Scale(domain=list(CLASS_SHAPE.keys()),
                                            range=list(CLASS_SHAPE.values())),
                            legend=None),
            opacity=alt.condition(alt.datum.passing,
                                  alt.value(1.0), alt.value(0.5)),
        )

        labels = alt.Chart(sub).mark_text(
            align="left", baseline="middle", dx=6, fontSize=8, color="#333",
        ).encode(
            x="value:Q", y="y6_shots_hit:Q", text="abbr:N",
        )

        if target is not None:
            target_line = alt.Chart(pd.DataFrame({"x": [target]})).mark_rule(
                color="#CC3311", strokeDash=[3, 3], strokeWidth=1.2,
            ).encode(x="x:Q")
            panel = alt.layer(target_line, scatter, labels)
        else:
            panel = alt.layer(scatter, labels)

        panel = panel.properties(width=720, height=80, title=objective)
        panels.append(panel)

    chart = alt.vconcat(*panels).resolve_scale(color="shared", shape="shared")
    chart = _config(chart).properties(
        title="Target strips — every objective x adoption per weapon (x = score, y = shots landed log, colour/shape = class)",
    )
    _save(chart, "02_target_strips")


def chart_skill_metrics():
    """03_skill_metrics: scatter of threshold gap vs ceiling speed.

    Note: matplotlib uses adjustText for label repulsion. Altair has no
    equivalent — labels overlap. This is the "Altair does less" data point.
    """
    df = _load("ettk_skill_metrics").copy()
    df = df[df["threshold_gap_vs_q75"].notna() & df["ceiling_speed_q100"].notna()]
    df["threshold_gap_vs_q75"] = df["threshold_gap_vs_q75"] * 100
    df["abbr"] = df["weapon"].map(WEAPON_ABBREV).fillna(df["weapon"].str[:3])
    df["q_label"] = df["quadrant"].map({
        "meta_dominant": "meta dominant",
        "skill_reward": "skill reward",
        "underrated": "underrated",
        "outclassed": "outclassed",
    })

    points = alt.Chart(df).mark_point(filled=True, size=140).encode(
        x=alt.X("threshold_gap_vs_q75:Q",
                title="threshold gap vs q75 (accuracy points)",
                scale=alt.Scale(domain=[-50, 50])),
        y=alt.Y("ceiling_speed_q100:Q",
                title="peak speed at q100 (seconds)",
                scale=alt.Scale(domain=[0.5, 5.0])),
        color=alt.Color("q_label:N",
                        scale=alt.Scale(
                            domain=["meta dominant", "skill reward",
                                    "underrated", "outclassed"],
                            range=[QUADRANT_COLORS["meta_dominant"],
                                   QUADRANT_COLORS["skill_reward"],
                                   QUADRANT_COLORS["underrated"],
                                   QUADRANT_COLORS["outclassed"]],
                        ),
                        legend=alt.Legend(
                            orient="top", title=None, direction="horizontal",
                        )),
        tooltip=["weapon", "threshold_gap_vs_q75", "ceiling_speed_q100"],
    )
    labels = alt.Chart(df).mark_text(
        align="center", baseline="bottom", dy=-8, fontSize=8, color="#333",
    ).encode(
        x="threshold_gap_vs_q75:Q", y="ceiling_speed_q100:Q", text="abbr:N",
    )

    target = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(
        color="#888", strokeDash=[3, 3], strokeWidth=1.0,
    ).encode(x="x:Q")
    speed_target = alt.Chart(pd.DataFrame({"y": [1.2]})).mark_rule(
        color="#CC3311", strokeDash=[1, 3], strokeWidth=1.0,
    ).encode(y="y:Q")

    chart = alt.layer(target, speed_target, points, labels).properties(
        width=720, height=480, title="Skill reward: hard threshold, fast peak",
    )
    chart = _config(chart)
    _save(chart, "03_skill_metrics")


def chart_t_down_all():
    """05h_t_down_all: 4-panel composite (curves, rank, volume, legend)."""
    curves = _load("ettk_curves")
    stats = _load("weapon_stats_for_ettk")
    df = curves[curves["t_down"].notna()].copy()
    df["accuracy_pct"] = df["accuracy"] * 100

    weapon_order = (
        stats.dropna(subset=["y6_shots_hit"])
        .sort_values("y6_shots_hit", ascending=False)["weapon"].tolist()
    )
    weapon_order = [w for w in weapon_order if w in df["weapon"].unique()]

    color_scale = alt.Scale(
        domain=weapon_order,
        range=[PALETTE[i % len(PALETTE)] for i in range(len(weapon_order))],
    )

    line = alt.Chart(df).mark_line(interpolate="step-after",
                                   point=alt.OverlayMarkDef(size=20)).encode(
        x=alt.X("accuracy_pct:Q",
                title="accuracy (%)", axis=alt.Axis(grid=False)),
        y=alt.Y("t_down:Q",
                title="time to down (s)",
                scale=alt.Scale(domain=[0.7, 5.5])),
        color=alt.Color("weapon:N", scale=color_scale,
                        legend=alt.Legend(orient="bottom", title=None,
                                          direction="horizontal", columns=4)),
        size=alt.value(1.5),
    ).properties(width=900, height=400, title="Down time vs accuracy — all weapons")

    # Rank panel: each weapon's rank at each accuracy
    rank_rows = []
    for acc in df["accuracy"].unique():
        row = df[df["accuracy"] == acc].sort_values("t_down")
        for i, (_, r) in enumerate(row.iterrows(), start=1):
            rank_rows.append({"weapon": r["weapon"], "accuracy_pct": acc * 100,
                              "rank": i})
    rank_df = pd.DataFrame(rank_rows)
    rank = alt.Chart(rank_df).mark_line(interpolate="step-after",
                                        point=alt.OverlayMarkDef(size=20)).encode(
        x=alt.X("accuracy_pct:Q", axis=alt.Axis(grid=False), title=None),
        y=alt.Y("rank:Q", title="rank (lower = faster)",
                scale=alt.Scale(reverse=True)),
        color=alt.Color("weapon:N", scale=color_scale, legend=None),
        size=alt.value(1.5),
    ).properties(width=900, height=300, title="Rank vs accuracy — all weapons")

    # Volume panel
    vol_df = stats[stats["weapon"].isin(weapon_order)].copy()
    vol_df = vol_df[vol_df["y6_shots_hit"].fillna(0) > 0]
    vol_df = vol_df.sort_values("y6_shots_hit", ascending=False)
    volume = alt.Chart(vol_df).mark_bar().encode(
        x=alt.X("y6_shots_hit:Q",
                title="shots landed (log scale)",
                scale=alt.Scale(type="log")),
        y=alt.Y("weapon:N", sort=weapon_order, title=None),
        color=alt.Color("weapon:N", scale=color_scale, legend=None),
    ).properties(width=900, height=max(200, 18 * len(vol_df)),
                 title="Shots landed")

    chart = alt.vconcat(line, rank, volume).resolve_scale(color="shared")
    chart = _config(chart)
    _save(chart, "05h_t_down_all")


def chart_design_space():
    """10_design_space: bubble scatter with iso-DPS diagonals."""
    stats = _load("weapon_stats_for_ettk").copy()
    df = stats.dropna(subset=["damage", "rpm_4", "magazine_4", "class"]).copy()
    df["pellets"] = df["pellets_per_shot"].fillna(1)
    df["per_trigger_dmg"] = df["damage"] * df["pellets"]
    df["abbr"] = df["weapon"].map(WEAPON_ABBREV).fillna(df["weapon"].str[:3])

    # Iso-DPS diagonals at 100/200/400 DPS, in log-log space
    dps_lines = []
    for dps in [100, 200, 400]:
        rpms = [60, 1500]
        damages = [dps / (r / 60.0) for r in rpms]
        for r, d in zip(rpms, damages):
            dps_lines.append({"dps": dps, "rpm": r, "dmg": d})
    dps_df = pd.DataFrame(dps_lines)

    bubbles = alt.Chart(df).mark_point(filled=True, opacity=0.85).encode(
        x=alt.X("rpm_4:Q",
                title="RPM (log)",
                scale=alt.Scale(type="log", domain=[20, 1500])),
        y=alt.Y("per_trigger_dmg:Q",
                title="damage per trigger pull (damage x pellets, log)",
                scale=alt.Scale(type="log", domain=[8, 200])),
        size=alt.Size("magazine_4:Q",
                      scale=alt.Scale(range=[40, 600]),
                      legend=alt.Legend(title="magazine")),
        color=alt.Color("class:N",
                        scale=alt.Scale(domain=list(CLASS_COLOR.keys()),
                                        range=list(CLASS_COLOR.values())),
                        legend=alt.Legend(orient="top", title=None,
                                          direction="horizontal")),
        shape=alt.Shape("class:N",
                        scale=alt.Scale(domain=list(CLASS_SHAPE.keys()),
                                        range=list(CLASS_SHAPE.values())),
                        legend=None),
        tooltip=["weapon", "damage", "rpm_4", "magazine_4"],
    )

    labels = alt.Chart(df).mark_text(
        align="center", baseline="bottom", dy=-10, fontSize=8, color="#333",
    ).encode(
        x="rpm_4:Q", y="per_trigger_dmg:Q", text="abbr:N",
    )

    diagonals = alt.Chart(dps_df).mark_line(
        strokeDash=[2, 2], color="#bbb", strokeWidth=1.0, opacity=0.6,
    ).encode(
        x="rpm:Q", y="dmg:Q", detail="dps:N",
    )
    diag_labels = alt.Chart(dps_df.groupby("dps").last().reset_index()).mark_text(
        fontSize=9, color="#888", angle=335,
    ).encode(
        x="rpm:Q", y="dmg:Q", text=alt.Text("dps:Q", format=".0f"),
    )

    chart = alt.layer(diagonals, diag_labels, bubbles, labels).properties(
        width=820, height=520,
        title="Weapon design space: RPM x per-trigger damage  -  bubble area = mag size",
    )
    chart = _config(chart)
    _save(chart, "10_design_space")


# ============================================================================
# Main: render all 30 charts
# ============================================================================

def main():
    parser = ArgumentParser()
    parser.add_argument("--only", help="Render only charts matching this prefix")
    args = parser.parse_args()

    def should_run(name):
        return not args.only or name.startswith(args.only)

    # Group A — direct ports
    if should_run("04"):
        chart_quadrants()
    if should_run("09"):
        chart_fired_vs_landed()
    if should_run("proposal"):
        chart_proposal_r99()

    # Story-driven (R-99 post + lra)
    smg_weapons = ["Alternator SMG", "Volt SMG", "C.A.R. SMG", "R-99 SMG"]
    if should_run("story_r99"):
        chart_story({
            "title": "How to read an eTTK chart",
            "outname": "story_r99_beat0_explainer",
            "weapons": [{"name": w} for w in smg_weapons],
            "ref_lines": [{"x": 60, "color": "#888"}],
            "h_ref_lines": [{"y": 1.5, "color": "#888"}],
        })
        chart_story({
            "title": "SMG: time to down",
            "outname": "story_r99_beat1_smg",
            "weapons": [{"name": w} for w in smg_weapons],
        })
        chart_story({
            "title": "R-99 proposed vs Volt",
            "outname": "story_r99_beat2_volt_context",
            "weapons": [
                {"name": "C.A.R. SMG", "label": "CAR", "style": "anchor",
                 "color": "#0077BB"},
                {"name": "R-99 SMG", "label": "R-99 current", "style": "anchor"},
                {"name": "R-99 SMG", "label": "Option A: 12/30 (CAR-anchored)",
                 "overrides": {"damage": 12, "magazine_4": 30},
                 "style": "highlight", "color": "#CC3311"},
                {"name": "R-99 SMG", "label": "Option B: 11/38 (Volt-anchored)",
                 "overrides": {"damage": 11, "magazine_4": 38},
                 "style": "highlight", "color": "#EE7733"},
                {"name": "Volt SMG", "label": "Volt", "style": "anchor",
                 "color": "#009988"},
            ],
        })
        chart_story({
            "title": "R-99 proposed vs cross-class anchors",
            "outname": "story_r99_beat3_review",
            "weapons": [
                {"name": "R-99 SMG", "label": "R-99 current", "style": "anchor"},
                {"name": "R-99 SMG", "label": "R-99 proposed",
                 "overrides": {"damage": 11, "magazine_4": 32},
                 "style": "highlight"},
                {"name": "Volt SMG", "label": "Volt", "style": "anchor"},
                {"name": "Hemlok Breach AR", "label": "Hemlok Breach AR",
                 "style": "anchor"},
                {"name": "Wingman", "label": "Wingman, all headshots",
                 "head_mode": True},
            ],
        })

    # LRA per-weapon stories
    lra_anchors = [
        {"name": "Hemlok Breach AR", "label": "Hemlok auto (AR baseline)",
         "style": "anchor"},
        {"name": "Volt SMG", "label": "Volt (SMG anchor)", "style": "anchor"},
    ]
    lra_specs = [
        ("flatline", "VK-47 Flatline", "Flatline", {"damage": 18, "magazine_4": 32},
         "(-2 dmg, +3 mag)"),
        ("r301", "R-301 Carbine", "R-301", {"damage": 11, "magazine_4": 40},
         "(-2 dmg, +9 mag)"),
        ("havoc", "HAVOC Rifle", "HAVOC", {"damage": 14, "magazine_4": 32},
         "(-4 dmg, +4 mag)"),
        ("spitfire", "M600 Spitfire", "Spitfire", {"damage": 15, "magazine_4": 55},
         "(-2 dmg, mag unchanged)"),
        ("lstar", "L-STAR EMG", "L-STAR", {"damage": 16, "magazine_4": 30},
         "(-2 dmg, mag unchanged)"),
        ("rampage", "Rampage LMG", "Rampage (revved)",
         {"damage": 25, "magazine_4": 40, "rpm_4": 120}, "(-3 dmg, mag unchanged)"),
    ]
    if should_run("story_lra"):
        for slug, weapon, display, overrides, delta in lra_specs:
            chart_story({
                "title": f"{display}: current vs proposed",
                "outname": f"story_lra_{slug}",
                "weapons": lra_anchors + [
                    {"name": weapon, "label": f"{display} current", "style": "anchor"},
                    {"name": weapon, "label": f"{display} proposed {delta}",
                     "overrides": overrides, "style": "highlight",
                     "color": "#CC3311"},
                ],
            })
        # Class overviews
        chart_story({
            "title": "Proposed ARs vs class anchors",
            "outname": "story_lra_overview_ar",
            "weapons": lra_anchors + [
                {"name": "VK-47 Flatline", "label": "Flatline proposed",
                 "overrides": {"damage": 18, "magazine_4": 32}, "color": "#0077BB"},
                {"name": "R-301 Carbine", "label": "R-301 proposed",
                 "overrides": {"damage": 11, "magazine_4": 40}, "color": "#EE7733"},
                {"name": "HAVOC Rifle", "label": "HAVOC proposed",
                 "overrides": {"damage": 14, "magazine_4": 32}, "color": "#009988"},
            ],
        })
        chart_story({
            "title": "Proposed LMGs vs class anchors",
            "outname": "story_lra_overview_lmg",
            "weapons": lra_anchors + [
                {"name": "M600 Spitfire", "label": "Spitfire proposed",
                 "overrides": {"damage": 15, "magazine_4": 55}, "color": "#0077BB"},
                {"name": "L-STAR EMG", "label": "L-STAR proposed",
                 "overrides": {"damage": 16, "magazine_4": 30}, "color": "#EE7733"},
                {"name": "Rampage LMG", "label": "Rampage proposed (revved)",
                 "overrides": {"damage": 25, "magazine_4": 40, "rpm_4": 120},
                 "color": "#009988"},
            ],
        })

    # Group B — t_down per-class composites
    class_panels = [
        ("AR", "Assault Rifle", "R-99 SMG", "05a_t_down_ar"),
        ("SMG", "Submachine Gun", "Hemlok Breach AR", "05b_t_down_smg"),
        ("Shotgun", "Shotgun", "R-99 SMG", "05c_t_down_shotgun"),
        ("Pistol", "Pistol", "R-99 SMG", "05d_t_down_pistol"),
        ("Marksman", "Marksman Rifle", "Hemlok Breach AR", "05e_t_down_marksman"),
        ("LMG", "LMG", "Hemlok Breach AR", "05f_t_down_lmg"),
        ("Sniper", "Sniper", "Hemlok Breach AR", "05g_t_down_sniper"),
    ]
    for class_key, display, anchor, outname in class_panels:
        if should_run(outname):
            chart_t_down_class(class_key, display, anchor, outname)

    if should_run("07"):
        chart_thresholds_bar()
    if should_run("08"):
        chart_rebalance_dumbbell()

    # Group C — hard ports
    if should_run("06"):
        chart_capability_heatmap()
    if should_run("01"):
        chart_scorecard()
    if should_run("02"):
        chart_target_strips()
    if should_run("03"):
        chart_skill_metrics()
    if should_run("05h"):
        chart_t_down_all()
    if should_run("10"):
        chart_design_space()


if __name__ == "__main__":
    main()
