"""Figures for the one-clip analysis.

Outputs (PNG + PDF + preview at 72 DPI) to output/ettk_figs/, ordered so the
reader gets an overview first and drills down:

  01_scorecard              multi-objective pass/fail overview per weapon
  02_target_strips          scatter companion to scorecard, one strip per objective
  03_skill_metrics          threshold gap vs ceiling speed (the R-99 paradox)
  04_quadrants              adoption vs capability space
  05[a-h]_t_down_curves     per-class t_down deep dive, with anchor weapons
  06_capability_heatmap     weapon × accuracy lookup table
  07_thresholds_bar         a_crack / a_down per weapon reference
  08_rebalance_dumbbell     recommended single-lever fixes
  09_fired_vs_landed        exposure / accuracy context
"""

import logging
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
plt.style.use(str(_HERE / "research_vibrant.mplstyle"))

RESULTS_CSV = "data/ettk_results.csv"
CURVES_CSV = "data/ettk_curves.csv"
RECS_CSV = "data/ettk_fixes_recommendations.csv"
OBJECTIVES_CSV = "data/ettk_objectives.csv"
SKILL_METRICS_CSV = "data/ettk_skill_metrics.csv"
OUT_DIR = "output/ettk_figs"

# A_DOWN_TARGET parallels analyze_ettk.A_DOWN_BAND. Kept duplicated because the
# two scripts communicate via CSV, not Python imports — if you change one,
# change the other. 50% accuracy is the "generously inclusive of pro-realistic"
# one-clip target the recommender uses.
A_DOWN_TARGET = 0.50

QUADRANT_COLORS = {
    "meta_dominant": "#0077BB",  # blue
    "skill_reward": "#EE7733",  # orange
    "underrated": "#009988",  # teal
    "outclassed": "#CC3311",  # red
}


def _save(fig, name):
    fig.savefig(os.path.join(OUT_DIR, f"{name}_preview.png"), dpi=72)
    fig.savefig(os.path.join(OUT_DIR, f"{name}.png"))
    fig.savefig(os.path.join(OUT_DIR, f"{name}.pdf"))
    _check_overlaps(fig, name)


def _style_legend(ax, handles, labels=None, ncol=4, **kwargs):
    """Place legend between title and chart area (never above the title).

    Follows the research_vibrant convention: legend sits just above the axes
    (y=1.01 in axes coords), and the title is pushed up via pad=30 so it still
    appears at the top of the figure.
    """
    kwargs.setdefault("frameon", False)
    kwargs.setdefault("fontsize", 8)
    if labels is None:
        ax.legend(
            handles=handles,
            loc="lower left",
            bbox_to_anchor=(0, 1.01),
            ncol=ncol,
            **kwargs,
        )
    else:
        ax.legend(
            handles=handles,
            labels=labels,
            loc="lower left",
            bbox_to_anchor=(0, 1.01),
            ncol=ncol,
            **kwargs,
        )
    # Push the title up above the legend row
    for loc in ("left", "center", "right"):
        t = ax.get_title(loc=loc)
        if t:
            ax.set_title(t, loc=loc, pad=30)
            break


def _check_overlaps(fig, name, min_chars=2):
    """After layout, report any text artist whose bounding box overlaps another.

    We collect all visible ax.texts and ax.title bboxes in display pixel space,
    then check every pair. Useful to catch label collisions that the eye would
    spot in a preview, but automatically.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    items = []
    for ax in fig.axes:
        for t in ax.texts:
            s = t.get_text().strip()
            if len(s) < min_chars:
                continue
            try:
                bbox = t.get_window_extent(renderer=renderer)
            except RuntimeError:
                continue
            if bbox.width <= 0 or bbox.height <= 0:
                continue
            items.append((s, bbox))
        for loc in ("left", "center", "right"):
            title_txt = ax.get_title(loc=loc)
            if title_txt:
                try:
                    bbox = ax.title.get_window_extent(renderer=renderer)
                except (RuntimeError, AttributeError):
                    continue
                items.append((f"<title>{title_txt}", bbox))
        if ax.get_legend() is not None:
            try:
                lbbox = ax.get_legend().get_window_extent(renderer=renderer)
                items.append(("<legend>", lbbox))
            except RuntimeError:
                pass
        if ax.xaxis.label.get_text():
            try:
                items.append(
                    (
                        f"<xlabel>{ax.xaxis.label.get_text()}",
                        ax.xaxis.label.get_window_extent(renderer=renderer),
                    )
                )
            except RuntimeError:
                pass

    overlaps = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            s1, b1 = items[i]
            s2, b2 = items[j]
            if b1.overlaps(b2):
                # Small fudge: require >1 pixel of overlap to ignore hairline kisses
                w = min(b1.x1, b2.x1) - max(b1.x0, b2.x0)
                h = min(b1.y1, b2.y1) - max(b1.y0, b2.y0)
                if w > 1 and h > 1:
                    overlaps.append((s1, s2, int(w * h)))
    if overlaps:
        logger.warning(f"[{name}] {len(overlaps)} text overlap(s):")
        for s1, s2, area in sorted(overlaps, key=lambda r: -r[2])[:6]:
            logger.warning(f"  {area:5d}px² :  {s1!r}  <->  {s2!r}")
    return overlaps


def _pct_label(a):
    if pd.isna(a):
        return "cannot"
    return f"{a * 100:.0f}%"


def fig1_thresholds(results):
    """Horizontal chart: a_crack (empty) to a_down (filled) per weapon.

    Only shows the accuracy thresholds. Time data belongs in fig2 (heatmap).
    Reference labels live in the footer below the x-axis label, safely away
    from the title and the data rows.
    """
    df = results.copy()
    df["a_down_plot"] = df["a_down"].fillna(1.07)
    df["a_crack_plot"] = df["a_crack"].fillna(1.07)
    df = df.sort_values("a_down_plot", ascending=True).reset_index(drop=True)

    colors = [QUADRANT_COLORS.get(q, "#888") for q in df["quadrant"]]

    fig, ax = plt.subplots(figsize=(9.5, 0.42 * len(df) + 2.0))
    y = np.arange(len(df))

    for i, row in df.iterrows():
        quad_col = colors[i]
        a_crack = row["a_crack_plot"]
        a_down = row["a_down_plot"]
        ax.plot(
            [a_crack, a_down],
            [i, i],
            color=quad_col,
            linewidth=5,
            solid_capstyle="butt",
            alpha=0.85,
            zorder=2,
        )
        ax.plot(
            a_crack,
            i,
            "o",
            color=quad_col,
            markersize=8,
            markerfacecolor="white",
            markeredgewidth=1.8,
            zorder=3,
        )
        ax.plot(a_down, i, "o", color=quad_col, markersize=10, zorder=3)

        if pd.isna(row["a_down"]):
            ax.text(
                1.09,
                i,
                "impossible",
                va="center",
                fontsize=8.5,
                color="#CC3311",
                fontstyle="italic",
            )
        else:
            ax.text(
                a_down + 0.012,
                i,
                _pct_label(row["a_down"]),
                va="center",
                fontsize=8.5,
                color="#333",
            )

    ax.set_yticks(y)
    ax.set_yticklabels(df["weapon"])
    ax.invert_yaxis()

    # Reference lines: pro q75 accuracy from the input data (computed live so
    # it's never stale relative to the eTTK inputs CSV) and the recommender's
    # one-clip target. Their style is shown as Line2D handles in the legend,
    # so no floating text needed to explain them.
    q75 = float(results["y6_accuracy_median"].dropna().quantile(0.75))
    ax.axvline(q75, color="#888", linestyle="--", linewidth=0.9, alpha=0.6)
    ax.axvline(A_DOWN_TARGET, color="#CC3311", linestyle=":", linewidth=1.2, alpha=0.65)

    ax.set_xlim(0, 1.22)
    ax.set_xticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xticklabels(["20%", "40%", "60%", "80%", "100%"])
    ax.set_xlabel("accuracy required to one-clip")
    ax.set_title("One-clip thresholds per weapon")

    # Single legend: marker meaning (crack/down circles) + quadrant patches +
    # reference lines (with real dash styles). Two columns to keep it compact.
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles = [
        # Column 1: what the circles mean
        Line2D(
            [0],
            [0],
            marker="o",
            color="#555",
            markerfacecolor="white",
            markeredgewidth=1.8,
            markersize=8,
            linestyle="",
            label="crack (100 HP)",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="#555",
            markerfacecolor="#555",
            markersize=10,
            linestyle="",
            label="down (200 HP)",
        ),
        Line2D(
            [0], [0], color="#888", linestyle="--", linewidth=1.2,
            label=f"q75 ({int(round(q75 * 100))}%)"
        ),
        Line2D(
            [0],
            [0],
            color="#CC3311",
            linestyle=":",
            linewidth=1.5,
            label="target (50%)",
        ),
        # Column 2: quadrant colouring
        Patch(facecolor=QUADRANT_COLORS["meta_dominant"], label="meta dominant"),
        Patch(facecolor=QUADRANT_COLORS["skill_reward"], label="skill reward"),
        Patch(facecolor=QUADRANT_COLORS["underrated"], label="underrated"),
        Patch(facecolor=QUADRANT_COLORS["outclassed"], label="outclassed"),
    ]
    ax.legend(
        handles=handles,
        loc="upper right",
        fontsize=8,
        frameon=True,
        facecolor="white",
        edgecolor="#ccc",
        ncol=2,
        borderpad=0.6,
        labelspacing=0.5,
        columnspacing=1.2,
    )

    _save(fig, "07_thresholds_bar")
    plt.close(fig)
    logger.info("wrote 07_thresholds_bar")


def fig2_capability_heatmap(results, curves):
    """Heatmap: rows = weapons, columns = accuracy levels, cells = t_down.

    Three-axis view of the capability space: weapon × accuracy × time-to-down.
    'Impossible' cells (can't one-clip at that accuracy) shown in a neutral
    grey with "∞" annotation. Annotated with time values for legible cells.
    """
    # Columns: six accuracy levels across the meaningful range.
    acc_cols = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80]
    # Sort weapons by a_down (best one-clippers on top)
    df = results.copy()
    df["a_down_plot"] = df["a_down"].fillna(1.07)
    df = df.sort_values("a_down_plot", ascending=True).reset_index(drop=True)
    weapons = df["weapon"].tolist()

    # Build the matrix: t_down per (weapon, accuracy). NaN = impossible.
    matrix = np.full((len(weapons), len(acc_cols)), np.nan)
    for i, w in enumerate(weapons):
        for j, a in enumerate(acc_cols):
            sub = curves[(curves["weapon"] == w) & (np.isclose(curves["accuracy"], a))]
            if not sub.empty:
                v = sub.iloc[0]["t_down"]
                matrix[i, j] = v  # NaN stays NaN when t_down was null in CSV

    # Colormap: intuitive green=fast / red=slow. RdYlGn reversed so low=green.
    vmin, vmax = 1.0, 4.5
    cmap = plt.cm.RdYlGn_r
    masked = np.ma.masked_invalid(matrix)

    fig, ax = plt.subplots(figsize=(8.5, 0.45 * len(weapons) + 1.6))
    im = ax.imshow(masked, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
    # Impossible cells: grey with "∞"
    for i in range(len(weapons)):
        for j in range(len(acc_cols)):
            if np.isnan(matrix[i, j]):
                ax.add_patch(
                    plt.Rectangle(
                        (j - 0.5, i - 0.5),
                        1,
                        1,
                        facecolor="#DDDDDD",
                        edgecolor="white",
                        zorder=2,
                    )
                )
                ax.text(
                    j,
                    i,
                    "∞",
                    ha="center",
                    va="center",
                    fontsize=10,
                    color="#888",
                    zorder=3,
                )
            else:
                v = matrix[i, j]
                # Dark text on light (fast) cells, white on deep-red (slow) cells.
                col = "white" if v >= 3.5 else "#222"
                ax.text(
                    j,
                    i,
                    f"{v:.1f}",
                    ha="center",
                    va="center",
                    fontsize=9,
                    color=col,
                    fontweight="bold",
                    zorder=3,
                )

    ax.set_yticks(np.arange(len(weapons)))
    ax.set_yticklabels(weapons)
    ax.set_xticks(np.arange(len(acc_cols)))
    ax.set_xticklabels([f"{int(a * 100)}%" for a in acc_cols])
    ax.set_xlabel("accuracy")
    ax.set_title("One-clip down time (seconds)")

    cbar = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label("seconds", fontsize=9)

    # Don't use x-axis gridlines inside the heatmap
    ax.set_xticks(np.arange(-0.5, len(acc_cols)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(weapons)), minor=True)
    ax.grid(which="minor", color="white", linewidth=1)
    ax.tick_params(which="minor", length=0)

    _save(fig, "06_capability_heatmap")
    plt.close(fig)
    logger.info("wrote 06_capability_heatmap")


def fig2_tdown_curves(results, curves):
    """t_down vs accuracy. Emits one figure per class + one combined:

      05a_t_down_ar          Assault Rifle              + R-99 anchor
      05b_t_down_smg         Submachine Gun             + Hemlok anchor
      05c_t_down_shotgun     Shotgun                    + R-99 anchor
      05d_t_down_pistol      Pistol                     + R-99 anchor
      05e_t_down_marksman    Marksman                   + Hemlok anchor
      05f_t_down_lmg         LMG                        + Hemlok anchor
      05g_t_down_sniper      Sniper                     + Hemlok anchor
      05h_t_down_all         every weapon combined

    Each per-class panel renders class members with strong color + solid line +
    large marker. Anchor weapons render thinner, dashed, and muted grey so they
    read as a reference line, not a member of the class.
    """
    from matplotlib.lines import Line2D

    # Normalise class names — patches CSV has both "AR" and "Assault Rifle", etc.
    CLASS_NORM = {
        "AR": "AR", "Assault Rifle": "AR",
        "SMG": "SMG", "Submachine Gun": "SMG",
        "Shotgun": "Shotgun",
        "Pistol": "Pistol",
        "Marksman": "Marksman",
        "LMG": "LMG",
        "Sniper": "Sniper",
    }

    import math as _math

    inputs = pd.read_csv("data/weapon_stats_for_ettk.csv")
    weapon_class_raw = dict(zip(inputs["weapon"], inputs["class"]))
    weapon_class = {w: CLASS_NORM.get(c, c) for w, c in weapon_class_raw.items()}
    shots_landed = dict(
        zip(inputs["weapon"], pd.to_numeric(inputs["y6_shots_hit"], errors="coerce"))
    )
    input_stats = {row["weapon"]: row for _, row in inputs.iterrows()}

    def _t_down_at_accuracy(weapon, accuracy, *, head=False):
        """t_down at a given accuracy, optionally with head_multiplier-boosted
        damage. Returns None if unreachable in one mag."""
        s = input_stats.get(weapon)
        if s is None:
            return None
        try:
            dmg = float(s["damage"])
            rpm = float(s["rpm_4"])
            mag = int(s["magazine_4"])
        except (ValueError, TypeError):
            return None
        pellets = 1
        if str(s.get("pellets_per_shot", "")).strip() not in ("", "nan"):
            pellets = max(1, int(float(s["pellets_per_shot"])))
        try:
            head_mult = float(s.get("head_multiplier") or 1.0)
        except (ValueError, TypeError):
            head_mult = 1.0
        try:
            evo_mult = float(s.get("evo_damage_multiplier") or 1.0)
        except (ValueError, TypeError):
            evo_mult = 1.0
        try:
            non_evo_mult = float(s.get("non_evo_damage_multiplier") or 1.0)
        except (ValueError, TypeError):
            non_evo_mult = 1.0
        eff_dmg = dmg * (head_mult if head else 1.0)
        bullets = _bullets_to_down(eff_dmg, pellets, accuracy, evo_mult, non_evo_mult)
        if bullets is None or bullets > mag:
            return None
        try:
            bpb = int(float(s.get("bullets_per_burst") or 0))
        except (ValueError, TypeError):
            bpb = 0
        try:
            bfd = float(s.get("burst_fire_delay") or 0)
        except (ValueError, TypeError):
            bfd = 0.0
        shot_interval = 60.0 / rpm
        if bpb <= 0 or bfd <= 0:
            return (bullets - 1) * shot_interval
        bursts = _math.ceil(bullets / bpb)
        within = bullets - bursts
        between = bursts - 1
        return within * shot_interval + between * bfd

    def _head_curve(weapon):
        """Return list of (accuracy_pct, t_down_head) across the chart range."""
        out = []
        for acc_pct in range(5, 100):
            acc = acc_pct / 100.0
            t = _t_down_at_accuracy(weapon, acc, head=True)
            if t is not None:
                out.append((acc_pct, t))
        return out

    all_weapons = list(results["weapon"])

    # Stable (color, dash, marker) per weapon across the combined figure.
    palette = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    dash_patterns = ["-", "--", "-."]
    marker_shapes = ["o", "s", "^", "D", "v", "P", "X"]
    style_map = {
        w: (
            palette[i % len(palette)],
            dash_patterns[i % len(dash_patterns)],
            marker_shapes[i % len(marker_shapes)],
        )
        for i, w in enumerate(all_weapons)
    }

    # Per-class panels use a stronger, more differentiated palette so small
    # panels are readable without all 25 colors competing.
    small_panel_palette = [
        "#0077BB", "#CC3311", "#009988", "#EE7733", "#33BBEE",
        "#EE3377", "#228833", "#BBBBBB", "#AA3377", "#66CCEE",
    ]

    # Class grouping and per-class anchor.
    CLASS_CONFIG = [
        ("AR",       "Assault Rifle",  "R-99 SMG",         "ar"),
        ("SMG",      "Submachine Gun", "Hemlok Breach AR", "smg"),
        ("Shotgun",  "Shotgun",        "R-99 SMG",         "shotgun"),
        ("Pistol",   "Pistol",         "R-99 SMG",         "pistol"),
        ("Marksman", "Marksman Rifle", "Hemlok Breach AR", "marksman"),
        ("LMG",      "LMG",            "Hemlok Breach AR", "lmg"),
        ("Sniper",   "Sniper",         "Hemlok Breach AR", "sniper"),
    ]

    x_min, x_max = 30, 95   # wider — high-damage weapons reveal their story above 75%
    y_min, y_max = 0.3, 5.5

    def _marker_kwargs(n_points):
        if n_points <= 8:
            return {"markevery": 2}
        return {"markevery": max(2, n_points // 8)}

    def plot_class_panel(class_key, class_display, anchor_weapon, outname):
        """One per-class figure: t_down curves (top) + shots-landed bars (bottom)."""
        class_weapons = [w for w in all_weapons if weapon_class.get(w) == class_key]
        if not class_weapons:
            logger.warning(f"skip {outname}: no {class_key} weapons in scope")
            return
        plot_panel(
            class_weapons,
            anchor_weapon if anchor_weapon in all_weapons and anchor_weapon not in class_weapons else None,
            f"Down time vs accuracy — {class_display}",
            outname,
        )

    def plot_panel(weapons, anchor, title, outname, figsize=(10, 9)):
        fig, (ax, ammo_ax) = plt.subplots(
            2,
            1,
            figsize=figsize,
            constrained_layout=False,
            gridspec_kw={"height_ratios": [3.3, 1.5]},
        )
        small_style_map = {
            w: (
                small_panel_palette[i % len(small_panel_palette)],
                "-",
                marker_shapes[i % len(marker_shapes)],
            )
            for i, w in enumerate(weapons)
        }
        handles = []
        any_head_drawn = False
        for w in weapons:
            sub = curves[
                (curves["weapon"] == w) & curves["t_down"].notna()
            ].sort_values("accuracy")
            if sub.empty:
                continue
            color, ls, mk = small_style_map[w]
            # Body floor: solid line + markers (current behaviour).
            ax.plot(
                sub["accuracy"] * 100,
                sub["t_down"],
                color=color,
                linestyle=ls,
                linewidth=2.8,
                alpha=0.95,
                marker=mk,
                markersize=7.2,
                markeredgecolor="white",
                markeredgewidth=1.0,
                zorder=4,
                **_marker_kwargs(len(sub)),
            )
            handles.append(
                Line2D(
                    [0], [0],
                    color=color, linestyle=ls, marker=mk,
                    markersize=7.6, markeredgecolor="white",
                    markeredgewidth=1.0, linewidth=2.8, label=w,
                )
            )

            # (Headshot dimension intentionally not shown on per-class panels —
            # crowds the comparison. Covered separately in the headshot
            # dividend bar chart and as a scorecard column.)

        # Anchor weapon: muted grey, dashed, thinner, behind class curves. Reads
        # as a reference line the reader can compare class members against.
        if anchor is not None:
            sub = curves[
                (curves["weapon"] == anchor) & curves["t_down"].notna()
            ].sort_values("accuracy")
            if not sub.empty:
                ax.plot(
                    sub["accuracy"] * 100, sub["t_down"],
                    color="#888888", linestyle=(0, (5, 2)), linewidth=1.6,
                    alpha=0.85, marker="o", markersize=5.5,
                    markerfacecolor="#AAAAAA", markeredgecolor="white",
                    markeredgewidth=0.7, zorder=3,
                    **_marker_kwargs(len(sub)),
                )
                handles.append(Line2D(
                    [0], [0], color="#888888", linestyle=(0, (5, 2)),
                    linewidth=1.6, marker="o", markersize=5.5,
                    markerfacecolor="#AAAAAA", markeredgecolor="white",
                    markeredgewidth=0.7,
                    label=f"{anchor}  (anchor)",
                ))

        _ = any_head_drawn  # kept variable for future re-introduction

        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        ax.set_xlabel("accuracy (%)")
        ax.set_ylabel("time to down (seconds)")
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.22)
        ax.legend(
            handles=handles,
            loc="upper right",
            fontsize=9,
            frameon=True,
            facecolor="white",
            edgecolor="#ccc",
            borderpad=0.5,
            labelspacing=0.5,
            handlelength=2.6,
        )

        bar_weapons = weapons + ([anchor] if anchor else [])
        rows = [
            (w, shots_landed.get(w))
            for w in bar_weapons
            if pd.notna(shots_landed.get(w)) and float(shots_landed.get(w)) > 0
        ]
        if rows:
            ordered_weapons = [
                w for w, _ in sorted(rows, key=lambda item: item[1], reverse=True)
            ]
            values = [shots_landed[w] for w in ordered_weapons]
            y = np.arange(len(ordered_weapons))
            colors = [
                "#AAAAAA" if w == anchor else small_style_map.get(w, (small_panel_palette[0],))[0]
                for w in ordered_weapons
            ]
            ammo_ax.barh(y, values, color=colors, edgecolor="none", height=0.7)
            for idx, value in enumerate(values):
                ammo_ax.text(
                    value * 1.01,
                    idx,
                    f"{int(value):,}",
                    va="center",
                    fontsize=8.5,
                    color="#333333",
                )
            ammo_ax.set_yticks(y)
            ammo_ax.set_yticklabels([
                f"{w} (anchor)" if w == anchor else w for w in ordered_weapons
            ])
            ammo_ax.invert_yaxis()
            ammo_ax.set_xscale("log")
            ammo_ax.set_xlim(min(values) * 0.8, max(values) * 1.25)
            ammo_ax.set_xlabel("shots landed in latest tournament (log scale)")
            ammo_ax.set_title("Shots landed")
            ammo_ax.grid(True, axis="x", alpha=0.22)
        else:
            ammo_ax.axis("off")

        fig.tight_layout()
        _save(fig, outname)
        plt.close(fig)
        logger.info(f"wrote {outname}")

    # Emit one figure per class.
    suffix_map = {}
    for class_key, class_display, anchor_weapon, suffix in CLASS_CONFIG:
        suffix_map[class_key] = suffix

    letters = "abcdefg"
    for (class_key, class_display, anchor_weapon, suffix), letter in zip(
        CLASS_CONFIG, letters
    ):
        plot_class_panel(
            class_key,
            class_display,
            anchor_weapon,
            f"05{letter}_t_down_{suffix}",
        )

    # Combined: four rows = time curves, rank curves, shots-landed companion,
    # legend footer.
    fig, (ax, rank_ax, volume_ax, legend_ax) = plt.subplots(
        4,
        1,
        figsize=(14, 13.8),
        constrained_layout=False,
        gridspec_kw={"height_ratios": [12, 8, 4.5, 3]},
    )
    for w in all_weapons:
        sub = curves[(curves["weapon"] == w) & curves["t_down"].notna()].sort_values(
            "accuracy"
        )
        if sub.empty:
            continue
        color, ls, mk = style_map[w]
        ax.plot(
            sub["accuracy"] * 100,
            sub["t_down"],
            color=color,
            linestyle=ls,
            linewidth=3.0,
            alpha=0.95,
            marker=mk,
            markersize=6.2,
            markeredgecolor="white",
            markeredgewidth=0.8,
            zorder=4,
            **_marker_kwargs(len(sub)),
        )
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel("accuracy (%)", fontsize=11)
    ax.set_ylabel("time to down (seconds)", fontsize=11)
    ax.set_title("Down time vs accuracy — all weapons")
    ax.grid(True, axis="y", alpha=0.22)
    ax.tick_params(labelsize=10)

    rank_df = curves[curves["t_down"].notna()].copy()
    rank_df["rank"] = rank_df.groupby("accuracy")["t_down"].rank(method="min")
    for w in all_weapons:
        sub = rank_df[rank_df["weapon"] == w].sort_values("accuracy")
        if sub.empty:
            continue
        color, ls, mk = style_map[w]
        rank_ax.plot(
            sub["accuracy"] * 100,
            sub["rank"],
            color=color,
            linestyle=ls,
            linewidth=2.8,
            alpha=0.95,
            marker=mk,
            markersize=5.6,
            markeredgecolor="white",
            markeredgewidth=0.8,
            zorder=4,
            **_marker_kwargs(len(sub)),
        )
    rank_ax.set_xlim(x_min, x_max)
    rank_ax.set_ylim(rank_df["rank"].max() + 0.5, 0.5)
    rank_ax.set_xlabel("accuracy (%)", fontsize=11)
    rank_ax.set_ylabel("rank by t_down", fontsize=11)
    rank_ax.set_title("Rank vs accuracy — all weapons")
    rank_ax.grid(True, axis="y", alpha=0.22)
    rank_ax.tick_params(labelsize=10)

    volume_rows = [
        (w, shots_landed.get(w))
        for w in all_weapons
        if pd.notna(shots_landed.get(w)) and float(shots_landed.get(w)) > 0
    ]
    ordered_weapons = [
        w for w, _ in sorted(volume_rows, key=lambda item: item[1], reverse=True)
    ]
    values = [shots_landed[w] for w in ordered_weapons]
    y = np.arange(len(ordered_weapons))
    colors = [style_map[w][0] for w in ordered_weapons]
    volume_ax.barh(y, values, color=colors, edgecolor="none", height=0.7)
    for idx, value in enumerate(values):
        volume_ax.text(
            value * 1.01,
            idx,
            f"{int(value):,}",
            va="center",
            fontsize=8.5,
            color="#333333",
        )
    volume_ax.set_yticks(y)
    volume_ax.set_yticklabels(ordered_weapons)
    volume_ax.invert_yaxis()
    volume_ax.set_xscale("log")
    volume_ax.set_xlim(min(values) * 0.8, max(values) * 1.25)
    volume_ax.set_xlabel("shots landed in latest tournament (log scale)")
    volume_ax.set_title("Shots landed")
    volume_ax.grid(True, axis="x", alpha=0.22)

    all_handles = [
        Line2D(
            [0],
            [0],
            color=style_map[w][0],
            linestyle=style_map[w][1],
            marker=style_map[w][2],
            markersize=7.5,
            markeredgecolor="white",
            markeredgewidth=0.8,
            linewidth=3.0,
            label=w,
        )
        for w in all_weapons
    ]
    legend_ax.axis("off")
    legend_ax.legend(
        handles=all_handles,
        loc="center",
        ncol=4,
        fontsize=9.5,
        frameon=True,
        facecolor="white",
        edgecolor="#ccc",
        columnspacing=2.2,
        handlelength=3.0,
        handletextpad=0.6,
    )
    fig.subplots_adjust(left=0.07, right=0.98, top=0.95, bottom=0.06, hspace=0.28)
    _save(fig, "05h_t_down_all")
    plt.close(fig)
    logger.info("wrote 05h_t_down_all")


def _weapon_abbrev(name):
    """Short 2-4 char code for a weapon, used to label dense scatter plots."""
    table = {
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
    if name in table:
        return table[name]
    parts = name.replace("-", " ").split()
    return (parts[0][:2] + (parts[1][:1] if len(parts) > 1 else "")).upper()


def _class_palette():
    """Distinct colour + marker per weapon class. Normalised so 'AR' / 'Assault
    Rifle' map to the same entry."""
    norm = {
        "AR": "AR", "Assault Rifle": "AR",
        "SMG": "SMG", "Submachine Gun": "SMG",
        "Shotgun": "Shotgun",
        "Pistol": "Pistol",
        "Marksman": "Marksman",
        "LMG": "LMG",
        "Sniper": "Sniper",
    }
    style = {
        "AR":       ("#0077BB", "o"),    # blue circle
        "SMG":      ("#EE7733", "s"),    # orange square
        "Shotgun":  ("#CC3311", "D"),    # red diamond
        "Pistol":   ("#AA3377", "P"),    # magenta plus
        "Marksman": ("#009988", "^"),    # teal triangle-up
        "LMG":      ("#EECC66", "v"),    # gold triangle-down
        "Sniper":   ("#222222", "*"),    # black star
    }
    return norm, style


def _load_weapon_classes():
    inputs = pd.read_csv("data/weapon_stats_for_ettk.csv")
    norm, _ = _class_palette()
    raw = dict(zip(inputs["weapon"], inputs["class"]))
    return {w: norm.get(c, c) for w, c in raw.items()}


def fig_target_strips(results, objectives):
    """Scatter companion to the scorecard. One 2D scatter strip per objective:

      x = objective value on its native axis (accuracy %, seconds, or HP)
      y = shots landed in the latest tournament (log) — adoption

    Reading each strip:
      - top-right (le) / top-left (ge) of target line  =  popular AND failing → balance problem
      - top side of pass band                           =  popular AND passing → good meta
      - bottom                                          =  niche regardless

    Dots coloured + shaped by weapon class. Labels are short codes; class
    legend at the bottom maps codes to weapon names.
    """
    # (name, x_label, scale_pct, pass_side, display_name)
    # scale_pct: True → multiply value by 100 for display (accuracy %). False keeps native.
    # pass_side: "le" → pass left of target, "ge" → pass right of target.
    # Order: accuracy group, then time group, then damage. Same grouping as
    # the scorecard so a reader can cross-reference column-by-strip.
    obj_order = [
        # accuracy group
        ("crack_at_q50",          "a_crack (accuracy %)",       True,  "le", "crack at q50"),
        ("down_at_50",            "a_down (accuracy %)",        True,  "le", "down at 50"),
        ("down_at_q75",           "a_down (accuracy %)",        True,  "le", "down at q75"),
        ("down_feasible_at_100",  "a_down (accuracy %)",        True,  "le", "down feasible at 100"),
        # time group
        ("crack_fast_at_q50",     "t_crack at q50 (seconds)",   False, "le", "crack fast at q50"),
        ("down_fast_at_q75",      "t_down at q75 (seconds)",    False, "le", "down fast at q75"),
        ("peak_speed_at_q100",    "t_down at q100 (seconds)",   False, "le", "peak speed at q100"),
        # damage group
        ("peek_100ms_at_q75",     "peek damage at q75 (HP)",    False, "ge", "peek 100ms at q75"),
    ]
    present_objs = set(objectives["objective"].unique())
    obj_order = [o for o in obj_order if o[0] in present_objs]
    n_strips = len(obj_order)
    if n_strips == 0:
        logger.warning("fig_target_strips: no objectives present, skipping")
        return

    weapons = list(results["weapon"])
    weapon_class = _load_weapon_classes()
    _, class_style = _class_palette()
    shots_landed = dict(zip(results["weapon"],
                            pd.to_numeric(results["y6_shots_hit"], errors="coerce")))

    # y-axis range: shared across all strips so position is comparable.
    y_vals = [v for v in shots_landed.values() if pd.notna(v) and v > 0]
    y_min = max(50, min(y_vals) * 0.7)
    y_max = max(y_vals) * 1.4

    # Explicit vertical budget (inches): title band + 8 strip rows + class legend.
    title_band_in = 0.7
    strip_height_in = 2.4         # taller now: 2D plot per strip needs vertical room
    legend_band_in = 0.9
    fig_height = title_band_in + strip_height_in * n_strips + legend_band_in
    fig = plt.figure(figsize=(13, fig_height), constrained_layout=False)

    gs = fig.add_gridspec(
        n_strips + 2, 1,
        height_ratios=[title_band_in] + [strip_height_in] * n_strips + [legend_band_in],
        left=0.07, right=0.97, top=0.99, bottom=0.02,
        hspace=0.55,
    )
    title_ax = fig.add_subplot(gs[0, 0])
    title_ax.axis("off")
    axes = [fig.add_subplot(gs[i + 1, 0]) for i in range(n_strips)]
    legend_ax = fig.add_subplot(gs[-1, 0])
    legend_ax.axis("off")

    for ax, (obj, xlabel, scale_pct, pass_side, display_name) in zip(axes, obj_order):
        sub = objectives[objectives["objective"] == obj].copy()
        if sub.empty:
            ax.axis("off")
            continue
        target = float(sub.iloc[0]["target"])
        scale = 100.0 if scale_pct else 1.0
        unit = "%" if scale_pct else ("s" if "seconds" in xlabel else " HP")

        imposs_mask = sub["impossible"].astype(str).str.lower() == "true"
        finite = sub[~imposs_mask].copy()
        imposs = sub[imposs_mask].copy()
        finite["val"] = pd.to_numeric(finite["value"], errors="coerce") * scale
        finite = finite[finite["val"].notna()].sort_values("val")

        x_tgt = target * scale
        max_val = finite["val"].max() if len(finite) else x_tgt
        min_val = finite["val"].min() if len(finite) else 0.0
        x_left = max(0, min_val * 0.9)
        x_right = max(max_val, x_tgt) * 1.15
        if len(imposs):
            x_imposs = x_right * 1.02
            x_right = x_imposs * 1.08

        # Shaded pass / fail bands. Direction depends on pass_side.
        if pass_side == "le":
            ax.axvspan(x_left, x_tgt, color="#E3F3DC", alpha=0.55, zorder=1)
            ax.axvspan(x_tgt, x_right, color="#FBE4E4", alpha=0.40, zorder=1)
        else:
            ax.axvspan(x_left, x_tgt, color="#FBE4E4", alpha=0.40, zorder=1)
            ax.axvspan(x_tgt, x_right, color="#E3F3DC", alpha=0.55, zorder=1)
        ax.axvline(x_tgt, color="#CC3311", linestyle="--", linewidth=1.6,
                   alpha=0.85, zorder=3)
        ax.text(x_tgt, y_max * 0.85, f"target {x_tgt:.2g}{unit}",
                ha="center", va="top", fontsize=8, color="#CC3311",
                fontweight="bold",
                bbox=dict(facecolor="white", edgecolor="none",
                          boxstyle="round,pad=0.2", alpha=0.85),
                zorder=4)

        # Finite weapons: x = value, y = shots_landed (log), shape & color by class.
        for _, r in finite.iterrows():
            w = r["weapon"]
            x = r["val"]
            y = shots_landed.get(w)
            if pd.isna(y) or y <= 0:
                continue
            cls = weapon_class.get(w, "AR")
            color, marker = class_style.get(cls, ("#666", "o"))
            ax.scatter(x, y, s=110, color=color, marker=marker,
                       edgecolor="white", linewidth=0.9, zorder=5)
            ax.annotate(_weapon_abbrev(w), (x, y),
                        xytext=(7, 0), textcoords="offset points",
                        fontsize=7.2, color="#222",
                        va="center", ha="left",
                        bbox=dict(facecolor="white", edgecolor="none",
                                  boxstyle="round,pad=0.1", alpha=0.6),
                        zorder=6)

        # Impossible weapons clustered at right edge with X marker.
        if len(imposs):
            for _, r in imposs.iterrows():
                w = r["weapon"]
                y = shots_landed.get(w)
                if pd.isna(y) or y <= 0:
                    continue
                cls = weapon_class.get(w, "AR")
                color, _mk = class_style.get(cls, ("#666", "o"))
                ax.scatter(x_imposs, y, s=110, color=color, marker="X",
                           edgecolor="white", linewidth=0.9, zorder=5)
                ax.annotate(_weapon_abbrev(w), (x_imposs, y),
                            xytext=(7, 0), textcoords="offset points",
                            fontsize=7.2, color="#222",
                            va="center", ha="left",
                            bbox=dict(facecolor="white", edgecolor="none",
                                      boxstyle="round,pad=0.1", alpha=0.6),
                            zorder=6)
            ax.text(x_imposs, y_max * 0.85, "impossible",
                    ha="center", va="top", fontsize=7.5, color="#666",
                    fontstyle="italic",
                    bbox=dict(facecolor="white", edgecolor="none",
                              boxstyle="round,pad=0.2", alpha=0.85),
                    zorder=4)

        ax.set_yscale("log")
        ax.set_ylim(y_min, y_max)
        ax.set_xlim(x_left, x_right)
        ax.set_xlabel(xlabel, fontsize=8.5)
        ax.set_ylabel("shots landed (log)", fontsize=8)
        ax.set_title(display_name, fontsize=10, loc="left", fontweight="bold",
                     color="#222")
        ax.grid(True, which="major", alpha=0.22)
        ax.tick_params(labelsize=7.5)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    # Suptitle lives in title_ax so it cannot collide with any strip title.
    title_ax.text(
        0.0, 0.3,
        "Target strips — every objective × adoption per weapon  "
        "(x = score, y = shots landed log, colour/shape = class)",
        fontsize=12, fontweight="bold",
        transform=title_ax.transAxes, va="bottom", ha="left", color="#222",
    )

    # Class legend: one entry per class (colour + shape), not per weapon.
    # Per-weapon identity is conveyed by the abbreviation labels on dots.
    from matplotlib.lines import Line2D
    classes_present = sorted({weapon_class.get(w, "AR") for w in weapons})
    handles = [
        Line2D([0], [0], color=class_style[c][0], marker=class_style[c][1],
               markersize=10, markeredgecolor="white", markeredgewidth=0.8,
               linestyle="", label=c)
        for c in classes_present if c in class_style
    ]
    handles.append(
        Line2D([0], [0], color="#666", marker="X", markersize=10,
               markeredgecolor="white", markeredgewidth=0.8, linestyle="",
               label="impossible (off-axis)")
    )
    legend_ax.legend(
        handles=handles, loc="center", ncol=len(handles), fontsize=9,
        frameon=True, facecolor="white", edgecolor="#ccc",
        columnspacing=2.0, handlelength=1.4, handletextpad=0.5,
        borderaxespad=0.2,
    )

    _save(fig, "02_target_strips")
    plt.close(fig)
    logger.info("wrote 02_target_strips")


def fig3_rebalance(results, recs):
    """Dumbbell of a_down before/after recommended change, per weapon."""
    df = results.merge(recs, on="weapon", how="left", suffixes=("", "_rec"))
    # Replace None (impossible) with 1.05 for plotting, mark specially
    df["current_plot"] = df["current_a_down"].fillna(1.05)
    df["projected_plot"] = df["projected_a_down"].fillna(1.05)
    df = df.sort_values("current_plot", ascending=True).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(9, 0.40 * len(df) + 1.4))
    y = np.arange(len(df))

    for i, row in df.iterrows():
        quad_col = QUADRANT_COLORS.get(row["quadrant"], "#888")
        current = row["current_plot"]
        projected = row["projected_plot"]
        is_hold = "HOLD" in str(row["recommendation"])
        change = projected - current

        ax.plot(current, i, "o", color=quad_col, markersize=9, zorder=3)

        if not is_hold and abs(change) > 0.005:
            # For a_down: RAISING is a nerf, LOWERING is a buff
            arrow_color = "#009988" if change < 0 else "#CC3311"
            ax.annotate(
                "",
                xy=(projected, i),
                xytext=(current, i),
                arrowprops=dict(
                    arrowstyle="->", color=arrow_color, linewidth=2, alpha=0.85
                ),
            )
            ax.plot(projected, i, "o", color=arrow_color, markersize=7, zorder=3)
            lbl = (
                str(row["recommendation"])
                .split(":", 1)[-1]
                .strip()
                .split("(insufficient")[0]
                .strip()
            )
            x_anchor = max(current, projected)
            ax.text(x_anchor + 0.015, i, lbl, va="center", fontsize=8, color="#333")
        else:
            note = str(row["recommendation"]).split(";")[0].replace("HOLD", "hold")
            ax.text(
                current + 0.015,
                i,
                note,
                va="center",
                fontsize=8,
                color="#888",
                fontstyle="italic",
            )

        if pd.isna(row["current_a_down"]):
            ax.text(-0.02, i, "∞", ha="right", va="center", fontsize=9, color="#CC3311")

    ax.set_yticks(y)
    ax.set_yticklabels(df["weapon"])
    ax.invert_yaxis()
    ax.axvline(A_DOWN_TARGET, color="#CC3311", linestyle=":", alpha=0.6, linewidth=1.2)

    ax.set_xlim(0, 1.15)
    ax.set_xticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xticklabels(["20%", "40%", "60%", "80%", "100%"])
    ax.set_xlabel("accuracy required to one-clip down")
    ax.set_title("Rebalance suggestions")

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles = [
        # Starting-dot colour = weapon's quadrant
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=QUADRANT_COLORS["meta_dominant"],
            markersize=8,
            linestyle="",
            label="start dot: meta dominant",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=QUADRANT_COLORS["skill_reward"],
            markersize=8,
            linestyle="",
            label="start dot: skill reward",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=QUADRANT_COLORS["underrated"],
            markersize=8,
            linestyle="",
            label="start dot: underrated",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=QUADRANT_COLORS["outclassed"],
            markersize=8,
            linestyle="",
            label="start dot: outclassed",
        ),
        # Arrow direction
        Patch(facecolor="#009988", label="arrow: buff"),
        Patch(facecolor="#CC3311", label="arrow: nerf"),
        Patch(facecolor="#999", label="no change"),
        # Reference line
        Line2D(
            [0],
            [0],
            color="#CC3311",
            linestyle=":",
            linewidth=1.5,
            label=f"target ({int(A_DOWN_TARGET * 100)}%)",
        ),
    ]
    ax.legend(
        handles=handles,
        loc="upper right",
        fontsize=7.5,
        frameon=True,
        facecolor="white",
        edgecolor="#ccc",
        ncol=1,
        borderpad=0.4,
        labelspacing=0.35,
    )

    _save(fig, "08_rebalance_dumbbell")
    plt.close(fig)
    logger.info("wrote 08_rebalance_dumbbell")


def fig4_quadrants(results):
    """Scatter: a_down vs pick rate (log), coloured by quadrant, with light
    quadrant-coloured background shading and the quadrant meanings explained
    in a legend in the top-right corner.
    """
    df = results.copy()
    df["a_down_plot"] = df["a_down"].fillna(1.10)

    fig, ax = plt.subplots(figsize=(9, 6))

    pick_median = df["y6_shots_hit"].median()

    # Pre-plot: need axis limits before we can shade. Do a phantom scatter to
    # let autoscale compute the bounds, then shade, then real scatter on top.
    ax.scatter(df["a_down_plot"], df["y6_shots_hit"], alpha=0.0)
    ax.set_yscale("log")
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()

    # Shade the four quadrants
    shade_alpha = 0.10
    # Meta-dominant: a_down < target, pick > median  → top-left
    ax.add_patch(
        plt.Rectangle(
            (xmin, pick_median),
            A_DOWN_TARGET - xmin,
            ymax - pick_median,
            facecolor=QUADRANT_COLORS["meta_dominant"],
            alpha=shade_alpha,
            zorder=0,
        )
    )
    # Comfort pick: a_down >= target, pick > median → top-right
    ax.add_patch(
        plt.Rectangle(
            (A_DOWN_TARGET, pick_median),
            xmax - A_DOWN_TARGET,
            ymax - pick_median,
            facecolor=QUADRANT_COLORS["skill_reward"],
            alpha=shade_alpha,
            zorder=0,
        )
    )
    # Underrated: a_down < target, pick <= median → bottom-left
    ax.add_patch(
        plt.Rectangle(
            (xmin, ymin),
            A_DOWN_TARGET - xmin,
            pick_median - ymin,
            facecolor=QUADRANT_COLORS["underrated"],
            alpha=shade_alpha,
            zorder=0,
        )
    )
    # Outclassed: a_down >= target, pick <= median → bottom-right
    ax.add_patch(
        plt.Rectangle(
            (A_DOWN_TARGET, ymin),
            xmax - A_DOWN_TARGET,
            pick_median - ymin,
            facecolor=QUADRANT_COLORS["outclassed"],
            alpha=shade_alpha,
            zorder=0,
        )
    )

    # Real points on top
    for _, row in df.iterrows():
        color = QUADRANT_COLORS.get(row["quadrant"], "#888")
        ax.scatter(
            row["a_down_plot"],
            row["y6_shots_hit"],
            s=110,
            color=color,
            edgecolor="black",
            linewidth=0.4,
            zorder=3,
        )
        label = row["weapon"]
        if pd.isna(row["a_down"]):
            label = row["weapon"] + "  (a_down = ∞)"
        ax.annotate(
            label,
            (row["a_down_plot"], row["y6_shots_hit"]),
            xytext=(7, 5),
            textcoords="offset points",
            fontsize=8.5,
            color="#333",
        )

    ax.axvline(A_DOWN_TARGET, color="#CC3311", linestyle=":", alpha=0.65, linewidth=1.2)
    ax.axhline(pick_median, color="#888", linestyle=":", alpha=0.5)

    ax.set_xticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xticklabels(["20%", "40%", "60%", "80%", "100%"])
    ax.set_xlabel("accuracy required to one-clip down")
    ax.set_ylabel("shots landed in Y6 (log)")
    ax.set_title("Weapon meta map")
    ax.grid(True, linestyle=":", alpha=0.3)

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles = [
        Patch(
            facecolor=QUADRANT_COLORS["meta_dominant"],
            alpha=0.35,
            label="meta dominant  (one-clip + picked)",
        ),
        Patch(
            facecolor=QUADRANT_COLORS["skill_reward"],
            alpha=0.35,
            label="skill reward  (picked, hard to one-clip, but fastest when you do)",
        ),
        Patch(
            facecolor=QUADRANT_COLORS["underrated"],
            alpha=0.35,
            label="underrated  (one-clip-capable but neglected)",
        ),
        Patch(
            facecolor=QUADRANT_COLORS["outclassed"],
            alpha=0.35,
            label="outclassed  (slow + avoided)",
        ),
        Line2D(
            [0],
            [0],
            color="#CC3311",
            linestyle=":",
            linewidth=1.5,
            label=f"a_down target ({int(A_DOWN_TARGET * 100)}%)",
        ),
        Line2D(
            [0],
            [0],
            color="#888",
            linestyle=":",
            linewidth=1.2,
            label=f"pick-rate median ({int(pick_median):,} shots)",
        ),
    ]
    ax.legend(
        handles=handles,
        loc="upper right",
        fontsize=8,
        frameon=True,
        facecolor="white",
        edgecolor="#ccc",
        ncol=1,
        borderpad=0.6,
        labelspacing=0.45,
    )

    _save(fig, "04_quadrants")
    plt.close(fig)
    logger.info("wrote 04_quadrants")


def fig5_volume_relationship(results):
    """Scatter: ammo used vs shots landed, latest tournament only."""
    inputs = pd.read_csv("data/weapon_stats_for_ettk.csv")
    df = results.merge(
        inputs[["weapon", "y6_ammo_used_sum", "y6_accuracy_median"]],
        on="weapon",
        how="left",
        suffixes=("", "_input"),
    )
    df["y6_shots_hit"] = pd.to_numeric(df["y6_shots_hit"], errors="coerce")
    df["y6_ammo_used_sum"] = pd.to_numeric(df["y6_ammo_used_sum"], errors="coerce")
    df = df[
        df["y6_shots_hit"].notna()
        & df["y6_ammo_used_sum"].notna()
        & (df["y6_ammo_used_sum"] > 0)
    ]
    df = df[df["y6_shots_hit"] > 0]
    if df.empty:
        logger.warning("Skipping 09_fired_vs_landed: no positive ammo/shots rows")
        return

    fig, ax = plt.subplots(figsize=(9, 6.5))
    for _, row in df.iterrows():
        color = QUADRANT_COLORS.get(row["quadrant"], "#888")
        ax.scatter(
            row["y6_ammo_used_sum"],
            row["y6_shots_hit"],
            s=110,
            color=color,
            edgecolor="black",
            linewidth=0.4,
            zorder=3,
        )
        acc = row["y6_accuracy_median"]
        label = (
            row["weapon"]
            if pd.isna(acc)
            else f"{row['weapon']} ({int(round(acc * 100))}%)"
        )
        ax.annotate(
            label,
            (row["y6_ammo_used_sum"], row["y6_shots_hit"]),
            xytext=(7, 5),
            textcoords="offset points",
            fontsize=8.5,
            color="#333",
        )

    max_val = max(df["y6_ammo_used_sum"].max(), df["y6_shots_hit"].max())
    ax.plot(
        [1, max_val],
        [1, max_val],
        linestyle="--",
        color="#888",
        linewidth=1.2,
        alpha=0.7,
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(df["y6_ammo_used_sum"].min() * 0.8, df["y6_ammo_used_sum"].max() * 1.25)
    ax.set_ylim(df["y6_shots_hit"].min() * 0.8, df["y6_shots_hit"].max() * 1.25)
    ax.set_xlabel("ammo used in latest tournament")
    ax.set_ylabel("shots landed in latest tournament")
    ax.set_title("Fired vs landed volume")
    ax.grid(True, which="major", alpha=0.22)

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles = [
        Patch(facecolor=QUADRANT_COLORS["meta_dominant"], label="meta dominant"),
        Patch(facecolor=QUADRANT_COLORS["skill_reward"], label="skill reward"),
        Patch(facecolor=QUADRANT_COLORS["underrated"], label="underrated"),
        Patch(facecolor=QUADRANT_COLORS["outclassed"], label="outclassed"),
        Line2D([0], [0], color="#888", linestyle="--", linewidth=1.2, label="1:1 line"),
    ]
    _style_legend(ax, handles, ncol=3)

    _save(fig, "09_fired_vs_landed")
    plt.close(fig)
    logger.info("wrote 09_fired_vs_landed")


def fig6_scorecard(results, objectives):
    """Multi-objective balance scorecard with SIGNED gap per cell.

    Every non-impossible cell shows the signed gap on its column's native
    scale: negative = margin below target (pass), positive = shortfall (fail).
    Color is a continuous diverging ramp (green below 0, red above) so every
    weapon carries a quantitative comparison, not just the failing ones.

    Grey "∞" cells = impossible (weapon cannot reach the milestone at all).
    Summary column shows count of passes / total.
    """
    import matplotlib.colors as mcolors
    from matplotlib.patches import Patch

    # Grouped by native unit: accuracy objectives first, then time, then damage.
    # Mixing units column-by-column made the +%/−% glyph carry different
    # quantities in adjacent cells; grouping keeps each band's unit stable.
    obj_order_by_spec = [
        # accuracy (4)
        "crack_at_q50",
        "down_at_50",
        "down_at_q75",
        "down_feasible_at_100",
        # time (3)
        "crack_fast_at_q50",
        "down_fast_at_q75",
        "peak_speed_at_q100",
        # damage (1)
        "peek_100ms_at_q75",
    ]
    present = set(objectives["objective"].unique())
    obj_names = [o for o in obj_order_by_spec if o in present]
    obj_display_names = {
        "crack_at_q50":         "crack@q50\n(acc)",
        "down_at_50":           "down@50\n(acc)",
        "down_at_q75":          "down@q75\n(acc)",
        "down_feasible_at_100": "down feasible@100\n(acc)",
        "crack_fast_at_q50":    "crack fast@q50\n(time)",
        "down_fast_at_q75":     "down fast@q75\n(time)",
        "peak_speed_at_q100":   "peak speed@q100\n(time)",
        "peek_100ms_at_q75":    "peek 100ms@q75\n(damage)",
    }

    weapons_order = results.sort_values("a_down", ascending=True, na_position="last")[
        "weapon"
    ].tolist()
    n_objectives = len(obj_names)

    # Diverging color ramp centred at gap=0. Clamp to ±150% so a single
    # extreme cell (e.g. EVA-8 +6900%) doesn't wash out the rest of the grid.
    GAP_CLAMP = 1.5
    cmap = plt.get_cmap("RdYlGn_r")
    norm = mcolors.Normalize(vmin=-GAP_CLAMP, vmax=GAP_CLAMP)
    impossible_color = "#999999"

    def _cell_color(gap):
        return cmap(norm(max(-GAP_CLAMP, min(GAP_CLAMP, gap))))

    def _fg_for_bg(bg_rgba):
        # Simple luminance check — dark text on light cells, white on dark.
        r, g, b = bg_rgba[:3]
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        return "#111" if lum > 0.55 else "#fff"

    # Explicit GridSpec: one tall row for the scorecard, one short row for the
    # colorbar/swatch band. The gridspec bottom is pushed up so the colorbar
    # sits close to the chart's bottom — with the correction to dataset after
    # the p99 bug fix, rows list more weapons and the band was floating far
    # below the last row.
    chart_rows_in = 0.42 * len(weapons_order) + 1.2     # header + rows (tighter)
    bottom_band_in = 0.9                                # colorbar + swatch
    total_height = chart_rows_in + bottom_band_in + 0.2  # + small bottom pad
    fig = plt.figure(
        figsize=(1.55 * n_objectives + 4.0, total_height),
        constrained_layout=False,
    )
    gs = fig.add_gridspec(
        2, 1,
        height_ratios=[chart_rows_in, bottom_band_in],
        left=0.18, right=0.98, top=0.96, bottom=0.04,
        hspace=0.08,
    )
    ax = fig.add_subplot(gs[0, 0])
    band_ax = fig.add_subplot(gs[1, 0])
    band_ax.axis("off")

    for i, weapon in enumerate(weapons_order):
        for j, obj in enumerate(obj_names):
            row = objectives[
                (objectives["weapon"] == weapon) & (objectives["objective"] == obj)
            ]
            if row.empty:
                continue
            r = row.iloc[0]
            if bool(r["impossible"]):
                color = impossible_color
                text = "∞"
                text_col = "white"
            else:
                gap = float(r["gap_pct"])
                color = _cell_color(gap)
                text_col = _fg_for_bg(color)
                text = f"{gap * 100:+.0f}%"
            ax.add_patch(
                plt.Rectangle(
                    (j - 0.5, i - 0.5), 1, 1,
                    facecolor=color, edgecolor="white", linewidth=2,
                )
            )
            ax.text(
                j, i, text, ha="center", va="center",
                fontsize=9, color=text_col, fontweight="bold",
            )

    # Summary column: passes / N objectives per weapon, coloured by pass fraction.
    for i, weapon in enumerate(weapons_order):
        passes_count = int(
            objectives[
                (objectives["weapon"] == weapon)
                & (objectives["passes"].astype(str).str.lower() == "true")
            ].shape[0]
        )
        frac = passes_count / n_objectives
        # Map pass fraction to the same ramp so summary matches cell colors.
        sum_color = cmap(norm(-GAP_CLAMP + (1 - frac) * 2 * GAP_CLAMP))
        sum_text_col = _fg_for_bg(sum_color)
        ax.add_patch(
            plt.Rectangle(
                (n_objectives + 0.1 - 0.5, i - 0.5), 1, 1,
                facecolor=sum_color, edgecolor="white", linewidth=2,
            )
        )
        ax.text(
            n_objectives + 0.1, i, f"{passes_count}/{n_objectives}",
            ha="center", va="center",
            fontsize=9.5, color=sum_text_col, fontweight="bold",
        )

    ax.set_xlim(-0.5, n_objectives + 0.6)
    ax.set_ylim(-0.5, len(weapons_order) - 0.5)
    ax.invert_yaxis()
    xtick_positions = list(np.arange(n_objectives)) + [n_objectives + 0.1]
    xtick_labels = [
        obj_display_names.get(o, o.replace("_", "\n")) for o in obj_names
    ] + ["total\npassed"]
    ax.set_xticks(xtick_positions)
    ax.set_xticklabels(xtick_labels, fontsize=8.5)
    ax.tick_params(axis="x", length=0)
    ax.set_yticks(np.arange(len(weapons_order)))
    ax.set_yticklabels(weapons_order)
    ax.tick_params(axis="y", length=0)
    ax.set_title("Multi-objective balance scorecard  —  signed gap from target per cell",
                 loc="left", pad=12, fontweight="bold")

    # Colorbar lives inside the explicit bottom band. Use inset_axes to carve
    # the exact rectangle inside band_ax.
    cbar_ax = band_ax.inset_axes([0.05, 0.55, 0.60, 0.22])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cb = fig.colorbar(sm, cax=cbar_ax, orientation="horizontal", extend="both")
    cb.set_ticks([-1.5, -0.75, 0, 0.75, 1.5])
    cb.set_ticklabels(["-150%\n(comfortable pass)", "-75%", "0%\n(at target)",
                        "+75%", "+150%\n(3-way miss)"])
    cb.ax.tick_params(labelsize=7.5)
    cb.outline.set_edgecolor("#bbb")
    cb.set_label("gap from target on column's native scale (accuracy points or seconds)",
                 fontsize=8.5, color="#333", labelpad=6)

    # Impossible swatch to the right of the colorbar, same band.
    swatch_ax = band_ax.inset_axes([0.72, 0.55, 0.04, 0.22])
    swatch_ax.axis("off")
    swatch_ax.add_patch(plt.Rectangle((0, 0), 1, 1, facecolor=impossible_color,
                                       edgecolor="#bbb"))
    swatch_ax.set_xlim(0, 1)
    swatch_ax.set_ylim(0, 1)
    band_ax.text(0.77, 0.66, "∞ = impossible (can't reach milestone at all)",
                 transform=band_ax.transAxes, va="center", ha="left",
                 fontsize=7.5, color="#333")

    _save(fig, "01_scorecard")
    plt.close(fig)
    logger.info("wrote 01_scorecard")


def fig7_skill_metrics():
    """Scatter: threshold gap vs peak speed at q100. Mathematical summary of
    the skill-reward archetype. Coloured + shaped by weapon class for visual
    discrimination; outliers above Y_CLIP plotted at the top edge with an
    off-chart marker.
    """
    from adjustText import adjust_text
    from matplotlib.lines import Line2D

    df = pd.read_csv(SKILL_METRICS_CSV)
    df = df[df["threshold_gap_vs_q75"].notna() & df["ceiling_speed_q100"].notna()].copy()

    weapon_class = _load_weapon_classes()
    _, class_style = _class_palette()

    Y_CLIP = 5.0
    df["clipped"] = df["ceiling_speed_q100"] > Y_CLIP
    df["y_plot"] = df["ceiling_speed_q100"].clip(upper=Y_CLIP)

    fig, ax = plt.subplots(figsize=(11, 7.5))

    # Light quadrant-style background shading. Pass corner = lower-right
    # (positive threshold gap means hard, low y means fast).
    ax.axvspan(-50, 0, ymin=0.0, ymax=(1.2 / Y_CLIP), alpha=0.06,
               color="#0077BB", zorder=0)
    ax.axvspan(0, 50, ymin=0.0, ymax=(1.2 / Y_CLIP), alpha=0.10,
               color="#EE7733", zorder=0)
    ax.axvspan(-50, 0, ymin=(1.2 / Y_CLIP), ymax=1.0, alpha=0.04,
               color="#999", zorder=0)

    texts = []
    for _, row in df.iterrows():
        w = row["weapon"]
        cls = weapon_class.get(w, "AR")
        color, marker = class_style.get(cls, ("#666", "o"))
        x = row["threshold_gap_vs_q75"] * 100
        y = row["y_plot"]
        if row["clipped"]:
            ax.scatter(x, y, s=200, color=color, edgecolor="black",
                       linewidth=1.5, marker="^", zorder=3)
            label = f"{_weapon_abbrev(w)} ({row['ceiling_speed_q100']:.1f}s, off-chart)"
        else:
            ax.scatter(x, y, s=140, color=color, edgecolor="white",
                       linewidth=1.0, marker=marker, zorder=3)
            label = _weapon_abbrev(w)
        texts.append(ax.text(x, y, label, fontsize=8.5, color="#222",
                             fontweight="bold", zorder=5))

    adjust_text(
        texts, ax=ax,
        expand_points=(1.4, 1.6),
        expand_text=(1.1, 1.3),
        arrowprops=dict(arrowstyle="-", color="#999", linewidth=0.6, alpha=0.6),
        only_move={"text": "xy", "points": "y"},
    )

    ax.axvline(0, color="#888", linestyle="--", linewidth=1.2, alpha=0.7, zorder=1)
    ax.axhline(1.2, color="#CC3311", linestyle=":", linewidth=1.2, alpha=0.7, zorder=1)
    ax.set_xlabel("threshold gap vs q75 (accuracy points)")
    ax.set_ylabel("peak speed at q100 (seconds)")
    ax.set_title("Skill reward: hard threshold, fast peak", loc="left",
                 fontweight="bold", pad=10)
    ax.set_ylim(0.3, Y_CLIP)
    ax.grid(True, alpha=0.22)

    classes_present = sorted({weapon_class.get(w, "AR") for w in df["weapon"]
                              if w in weapon_class})
    handles = [
        Line2D([0], [0], color=class_style[c][0], marker=class_style[c][1],
               markersize=10, markeredgecolor="white", markeredgewidth=0.8,
               linestyle="", label=c)
        for c in classes_present if c in class_style
    ]
    handles += [
        Line2D([0], [0], color="#888", linestyle="--", linewidth=1.2,
               label="threshold = q75"),
        Line2D([0], [0], color="#CC3311", linestyle=":", linewidth=1.2,
               label="q100 speed target (1.2s)"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor="#666",
               markeredgecolor="black", markersize=10, linestyle="",
               label="off-chart (y > 5s)"),
    ]
    ax.legend(handles=handles, loc="upper right",
              fontsize=8, frameon=True, facecolor="white",
              edgecolor="#ccc", ncol=1, borderpad=0.5, labelspacing=0.4)

    # Footnote with abbreviation key — small, bottom-left, not in the way.
    abbrev_pairs = sorted(
        ((_weapon_abbrev(w), w) for w in df["weapon"]),
        key=lambda x: x[0],
    )
    abbrev_text = " · ".join(f"{ab}={n}" for ab, n in abbrev_pairs)
    fig.text(0.02, 0.005, abbrev_text, fontsize=6.5, color="#666",
             ha="left", va="bottom", wrap=True)

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _save(fig, "03_skill_metrics")
    plt.close(fig)
    logger.info("wrote 03_skill_metrics")


def fig_proposal(weapon_name, current_stats, proposed_stats, anchors,
                 out_name, subtitle=None):
    """Single-weapon before/after overlay on the skill-metrics scatter.

    current_stats / proposed_stats: dicts with damage, mag, pellets, rpm,
    burst_bullets, burst_delay. The function computes (a_down, t_down at
    100% accuracy) from the stats.

    Plot: grey background dots for other weapons, class-coloured markers for
    the anchor weapons, filled marker at the subject's current position, hollow
    marker at the proposed position, and an arrow between them. Delta summary
    in a footer box. Follows research_vibrant: concise title, no subtitle,
    short axis labels.
    """
    from matplotlib.lines import Line2D
    import math as _math

    def _stats_to_point(s):
        pellets = max(1, int(s.get("pellets", 1) or 1))
        dmg = float(s["damage"])
        mag = int(s["mag"])
        rpm = float(s["rpm"])
        evo_mult = float(s.get("evo_mult", 1.0) or 1.0)
        non_evo_mult = float(s.get("non_evo_mult", 1.0) or 1.0)
        # Phase-aware capability check at 100% accuracy.
        full_acc_bullets = _bullets_to_down(dmg, pellets, 1.0, evo_mult, non_evo_mult)
        if full_acc_bullets is None or full_acc_bullets > mag:
            return float("nan"), float("nan")
        # a_down: smallest accuracy where phase-summed bullets fits in mag.
        a_down = float("nan")
        for a_pct in range(1, 101):
            a = a_pct / 100.0
            n = _bullets_to_down(dmg, pellets, a, evo_mult, non_evo_mult)
            if n is not None and n <= mag:
                a_down = a
                break
        shot_interval = 60.0 / rpm
        bpb = int(s.get("burst_bullets", 0) or 0)
        bfd = float(s.get("burst_delay", 0.0) or 0.0)
        is_burst = bpb > 0 and bfd > 0
        bullets_needed = full_acc_bullets   # peak speed = at 100% accuracy
        if not is_burst:
            return a_down, (bullets_needed - 1) * shot_interval
        bursts = _math.ceil(bullets_needed / bpb)
        within = bullets_needed - bursts
        between = bursts - 1
        return a_down, within * shot_interval + between * bfd

    df = pd.read_csv(SKILL_METRICS_CSV)
    df = df[df["threshold_gap_vs_q75"].notna() & df["ceiling_speed_q100"].notna()].copy()
    q75 = 0.44
    Y_CLIP = 4.5
    df["y_plot"] = df["ceiling_speed_q100"].clip(upper=Y_CLIP)

    weapon_class = _load_weapon_classes()
    _, class_style = _class_palette()

    fig, ax = plt.subplots(figsize=(10, 6.5))

    # Grey background: every other weapon as a small faded dot.
    for _, r in df.iterrows():
        if r["weapon"] == weapon_name or r["weapon"] in anchors:
            continue
        ax.scatter(r["threshold_gap_vs_q75"] * 100, r["y_plot"],
                   s=36, color="#D0D0D0", edgecolor="none", zorder=2)

    # Anchors: class-coloured, small, labelled by weapon name only.
    for a_name in anchors:
        a_row = df[df["weapon"] == a_name]
        if a_row.empty:
            continue
        a = a_row.iloc[0]
        cls = weapon_class.get(a_name, "AR")
        color, marker = class_style.get(cls, ("#666", "o"))
        x, y = a["threshold_gap_vs_q75"] * 100, a["y_plot"]
        ax.scatter(x, y, s=90, color=color, marker=marker,
                   edgecolor="white", linewidth=0.8, alpha=0.9, zorder=3)
        ax.annotate(a_name, (x, y), xytext=(8, 4),
                    textcoords="offset points", fontsize=8, color="#555",
                    zorder=5)

    # Subject weapon — current (filled) + proposed (hollow) + arrow.
    cls = weapon_class.get(weapon_name, "AR")
    color, marker = class_style.get(cls, ("#CC3311", "o"))
    cur_a_down, cur_peak = _stats_to_point(current_stats)
    prop_a_down, prop_peak = _stats_to_point(proposed_stats)
    cur_x = (cur_a_down - q75) * 100 if not _math.isnan(cur_a_down) else 40
    cur_y = cur_peak if not _math.isnan(cur_peak) else Y_CLIP * 0.95
    prop_x = (prop_a_down - q75) * 100 if not _math.isnan(prop_a_down) else 40
    prop_y = prop_peak if not _math.isnan(prop_peak) else Y_CLIP * 0.95

    ax.scatter(cur_x, cur_y, s=220, color=color, marker=marker,
               edgecolor="black", linewidth=1.4, zorder=6)
    ax.scatter(prop_x, prop_y, s=220, facecolor="white", marker=marker,
               edgecolor=color, linewidth=2.5, zorder=6)
    ax.annotate("", xy=(prop_x, prop_y), xytext=(cur_x, cur_y),
                arrowprops=dict(arrowstyle="->", lw=2, color=color,
                                shrinkA=13, shrinkB=13),
                zorder=5)

    # Reference lines (no legend entries for these — self-evident).
    ax.axvline(0, color="#888", linestyle="--", linewidth=1, alpha=0.6, zorder=1)
    ax.axhline(1.2, color="#888", linestyle=":", linewidth=1, alpha=0.6, zorder=1)

    ax.set_xlabel("accuracy gap above q75 (points)")
    ax.set_ylabel("time to down at 100% accuracy (s)")
    ax.set_title(f"{weapon_name}: proposed change")
    ax.set_ylim(0.4, Y_CLIP)
    ax.set_xlim(-45, 45)
    ax.grid(True, axis="y", alpha=0.22)

    # Legend kept to two entries — current vs proposed. Anchors are labelled
    # inline; grey dots are self-evident; reference lines are self-evident.
    handles = [
        Line2D([0], [0], marker=marker, color=color, markersize=11,
               markeredgecolor="black", markeredgewidth=1.1, linestyle="",
               label="current"),
        Line2D([0], [0], marker=marker, color="white", markersize=11,
               markeredgecolor=color, markeredgewidth=2, linestyle="",
               label="proposed"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=9,
              frameon=True, facecolor="white", edgecolor="#ccc",
              borderpad=0.4)

    # Delta summary as a clean bottom-left footer.
    deltas = []
    for key in ("damage", "mag", "rpm", "pellets"):
        a, b = current_stats.get(key), proposed_stats.get(key)
        if a is None or b is None or a == b:
            continue
        sign = "+" if b > a else ""
        deltas.append(f"{key} {a}→{b} ({sign}{b - a:g})")
    if deltas:
        ax.text(0.02, 0.03, " · ".join(deltas),
                transform=ax.transAxes, fontsize=9, color="#222",
                va="bottom", ha="left")

    fig.tight_layout()
    _save(fig, out_name)
    plt.close(fig)
    logger.info(f"wrote {out_name}")


def fig_design_space():
    """RPM x per-trigger-damage scatter, log-log, bubble area = mag size,
    with iso-DPS reference diagonals. Identifies empty regions of the design
    space — gaps where no weapon currently sits, suggesting design openings.

    On log-log axes, constant DPS = a straight line of slope -1 because
    DPS = (RPM/60) * per-trigger-damage. Lines drawn at 100/200/400 DPS.
    """
    from matplotlib.lines import Line2D

    inputs = pd.read_csv("data/weapon_stats_for_ettk.csv")
    weapon_class = _load_weapon_classes()
    _, class_style = _class_palette()

    rows = []
    for _, r in inputs.iterrows():
        try:
            rpm = float(r["rpm_4"])
            dmg = float(r["damage"])
            mag = int(r["magazine_4"])
        except (ValueError, TypeError):
            continue
        if rpm <= 0 or dmg <= 0 or mag <= 0:
            continue
        pellets = 1
        if str(r["pellets_per_shot"]).strip() not in ("", "nan"):
            pellets = max(1, int(float(r["pellets_per_shot"])))
        rows.append({
            "weapon": r["weapon"],
            "class": weapon_class.get(r["weapon"], "AR"),
            "rpm": rpm,
            "per_trigger": dmg * pellets,
            "mag": mag,
        })
    df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(11, 7.5))

    # Iso-DPS reference diagonals on log-log axes.
    rpm_grid = np.array([20, 2000])
    for dps_value, label_pos in [(100, 70), (200, 200), (400, 600)]:
        per_trigger_curve = (dps_value * 60) / rpm_grid
        ax.plot(rpm_grid, per_trigger_curve, linestyle=":",
                color="#888", linewidth=1, alpha=0.5, zorder=1)
        ax.text(label_pos, (dps_value * 60) / label_pos * 1.06,
                f"{dps_value} DPS",
                fontsize=8, color="#666", rotation=-32,
                rotation_mode="anchor", ha="left", va="bottom",
                zorder=2)

    # Empty-region annotations restricted to AR / SMG / Pistol classes that
    # are also empty in absolute terms (no weapon of any class in the box).
    # Snipers + marksmen excluded — already over-served relative to pick rate.
    # Wingman occupies the hand-cannon role; a second one fragments the niche.
    # The SMG class is densely packed near 200 DPS — gaps within it are
    # feel/recoil/mag differentiation, not RPM x damage; not boxed.
    EMPTY_ZONES = [
        # (xmin, xmax, ymin, ymax, label, label_pos)
        (350, 500, 24, 32, "heavy AR\n(slower cadence,\nbigger per-shot)", (415, 31)),
        (240, 400, 28, 40, "mid-cadence pistol\n(big mag, mid dmg —\nbridges P2020 to Wingman)", (310, 39)),
    ]
    for xmin, xmax, ymin, ymax, label, label_xy in EMPTY_ZONES:
        ax.add_patch(plt.Rectangle((xmin, ymin), xmax - xmin, ymax - ymin,
                                    facecolor="#EE7733", alpha=0.10,
                                    edgecolor="#EE7733", linewidth=1.3,
                                    linestyle="--", zorder=1.5))
        ax.text(label_xy[0], label_xy[1], label,
                fontsize=8, color="#883300", ha="center", va="top",
                fontstyle="italic", zorder=2,
                bbox=dict(facecolor="white", edgecolor="none", pad=1, alpha=0.7))

    # Plot weapons. Bubble size = mag (s is area in pt^2; 8x scaling).
    for _, r in df.iterrows():
        cls = r["class"]
        color, marker = class_style.get(cls, ("#666", "o"))
        size = r["mag"] * 14    # scale so smallest mag (~4) is visible, largest (~50) not too big
        ax.scatter(r["rpm"], r["per_trigger"], s=size,
                   color=color, marker=marker,
                   edgecolor="white", linewidth=0.9, alpha=0.85, zorder=4)
        ax.annotate(_weapon_abbrev(r["weapon"]),
                    (r["rpm"], r["per_trigger"]),
                    xytext=(0, np.sqrt(size) / 2 + 4),
                    textcoords="offset points",
                    fontsize=8.5, color="#222", ha="center", va="bottom",
                    zorder=5)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(20, 2000)
    ax.set_ylim(8, 250)
    ax.set_xlabel("RPM (log)")
    ax.set_ylabel("damage per trigger pull (damage x pellets, log)")
    ax.set_title("Weapon design space: RPM x per-trigger damage  —  bubble area = mag size")
    ax.grid(True, which="major", alpha=0.22)
    ax.grid(True, which="minor", alpha=0.10)

    classes_present = sorted({r["class"] for _, r in df.iterrows()
                              if r["class"] in class_style})
    handles = [
        Line2D([0], [0], marker=class_style[c][1], color=class_style[c][0],
               markersize=11, markeredgecolor="white", markeredgewidth=0.8,
               linestyle="", label=c)
        for c in classes_present
    ]
    # Mag-size scale chip in the legend (three reference bubbles).
    for ref_mag in (5, 20, 40):
        handles.append(Line2D([0], [0], marker="o", color="#666",
                              markersize=np.sqrt(ref_mag * 14),
                              markeredgecolor="white", markeredgewidth=0.8,
                              linestyle="", alpha=0.6,
                              label=f"mag {ref_mag}"))
    handles.append(Line2D([0], [0], color="#EE7733", linestyle="--",
                          linewidth=1.3, label="empty design region"))

    ax.legend(handles=handles, loc="lower left", fontsize=8.5,
              frameon=True, facecolor="white", edgecolor="#ccc",
              borderpad=0.5, labelspacing=0.6)

    # Abbreviation key footer
    abbrev_pairs = sorted(
        ((_weapon_abbrev(w), w) for w in df["weapon"]),
        key=lambda x: x[0],
    )
    abbrev_text = " · ".join(f"{ab}={n}" for ab, n in abbrev_pairs)
    fig.text(0.02, 0.005, abbrev_text, fontsize=6.5, color="#666",
             ha="left", va="bottom")

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _save(fig, "10_design_space")
    plt.close(fig)
    logger.info("wrote 10_design_space")


def _bullet_times_for_entry(entry, base_stats):
    """Per-bullet cumulative timing for one fig_story entry.

    Returns list of (accuracy_pct, bullet_index, t_after_bullet) for every
    bullet that fits in the magazine at every accuracy from 30%..99%. The
    "line" of t_down is the top of each accuracy's column. Useful for
    visualising the actual shot cadence (burst gaps, RPM density) instead of
    a smooth t_down envelope.
    """
    import math as _math
    name = entry["name"]
    base = base_stats.get(name)
    if base is None:
        return []
    overrides = entry.get("overrides", {}) or {}

    def _stat(key, default=None):
        if key in overrides:
            return overrides[key]
        return base.get(key, default)

    try:
        dmg = float(_stat("damage"))
        rpm = float(_stat("rpm_4"))
        mag = int(_stat("magazine_4"))
    except (ValueError, TypeError):
        return []
    pellets = 1
    p_raw = _stat("pellets_per_shot", "")
    if str(p_raw).strip() not in ("", "nan", "None"):
        try:
            pellets = max(1, int(float(p_raw)))
        except (ValueError, TypeError):
            pass
    try:
        head_mult = float(base.get("head_multiplier") or 1.0)
    except (ValueError, TypeError):
        head_mult = 1.0
    if entry.get("head_mode"):
        dmg = dmg * head_mult
    try:
        evo_mult = float(base.get("evo_damage_multiplier") or 1.0)
    except (ValueError, TypeError):
        evo_mult = 1.0
    try:
        non_evo_mult = float(base.get("non_evo_damage_multiplier") or 1.0)
    except (ValueError, TypeError):
        non_evo_mult = 1.0
    if "evo_mult" in overrides:
        evo_mult = float(overrides["evo_mult"])
    if "non_evo_mult" in overrides:
        non_evo_mult = float(overrides["non_evo_mult"])
    try:
        bpb = int(float(base.get("bullets_per_burst") or 0))
    except (ValueError, TypeError):
        bpb = 0
    try:
        bfd = float(base.get("burst_fire_delay") or 0)
    except (ValueError, TypeError):
        bfd = 0.0
    is_burst = bpb > 0 and bfd > 0
    shot_interval = 60.0 / rpm

    def _t_after(i):
        """Cumulative time after firing the i-th bullet (1-indexed). Bullet 1 is at t=0."""
        if i <= 1:
            return 0.0
        if not is_burst:
            return (i - 1) * shot_interval
        bursts = _math.ceil(i / bpb)
        within = i - bursts
        between = bursts - 1
        return within * shot_interval + between * bfd

    # Emit ONE dot per accuracy where the bullet count changes vs the previous
    # accuracy. Each dot sits at (acc, t_down) — the time of the LAST bullet
    # needed to reach 200 HP at that accuracy. R-99 cycles through more bullet
    # counts (16..27 in the displayed range), so it has more dots; Wingman
    # cycles through few (2..5), so it has fewer dots.
    out = []
    prev_n = None
    for acc_pct in range(5, 100):
        acc = acc_pct / 100.0
        n = _bullets_to_down(dmg, pellets, acc, evo_mult, non_evo_mult)
        if n is None or n > mag:
            prev_n = n
            continue
        if n != prev_n:
            out.append((acc_pct, n, _t_after(n)))
            prev_n = n
    return out


def _curve_for_entry(entry, base_stats):
    """Compute the (accuracy_pct, t_down) list for one fig_story entry.

    entry can specify:
        name (str): base weapon to look up in base_stats
        overrides (dict): patch-style overrides for damage/mag/rpm/pellets
        head_mode (bool): apply head_multiplier to damage (precision ceiling)
    """
    import math as _math
    name = entry["name"]
    base = base_stats.get(name)
    if base is None:
        return []
    # Pull primitive stats with override fallback.
    overrides = entry.get("overrides", {}) or {}

    def _stat(key, default=None):
        if key in overrides:
            return overrides[key]
        return base.get(key, default)

    try:
        dmg = float(_stat("damage"))
        rpm = float(_stat("rpm_4"))
        mag = int(_stat("magazine_4"))
    except (ValueError, TypeError):
        return []
    pellets = 1
    p_raw = _stat("pellets_per_shot", "")
    if str(p_raw).strip() not in ("", "nan", "None"):
        try:
            pellets = max(1, int(float(p_raw)))
        except (ValueError, TypeError):
            pass
    try:
        head_mult = float(base.get("head_multiplier") or 1.0)
    except (ValueError, TypeError):
        head_mult = 1.0
    if entry.get("head_mode"):
        dmg = dmg * head_mult
    try:
        evo_mult = float(base.get("evo_damage_multiplier") or 1.0)
    except (ValueError, TypeError):
        evo_mult = 1.0
    try:
        non_evo_mult = float(base.get("non_evo_damage_multiplier") or 1.0)
    except (ValueError, TypeError):
        non_evo_mult = 1.0
    # Per-entry override of the shield/health phase multipliers.
    if "evo_mult" in overrides:
        evo_mult = float(overrides["evo_mult"])
    if "non_evo_mult" in overrides:
        non_evo_mult = float(overrides["non_evo_mult"])
    try:
        bpb = int(float(base.get("bullets_per_burst") or 0))
    except (ValueError, TypeError):
        bpb = 0
    try:
        bfd = float(base.get("burst_fire_delay") or 0)
    except (ValueError, TypeError):
        bfd = 0.0
    is_burst = bpb > 0 and bfd > 0
    shot_interval = 60.0 / rpm
    out = []
    for acc_pct in range(5, 100):
        acc = acc_pct / 100.0
        bullets = _bullets_to_down(dmg, pellets, acc, evo_mult, non_evo_mult)
        if bullets is None or bullets > mag:
            continue
        if not is_burst:
            t = (bullets - 1) * shot_interval
        else:
            bursts = _math.ceil(bullets / bpb)
            within = bullets - bursts
            between = bursts - 1
            t = within * shot_interval + between * bfd
        out.append((acc_pct, t))
    return out


def _bullets_to_down(damage, pellets, accuracy, evo_mult=1.0, non_evo_mult=1.0,
                    shield_hp=100, health_hp=100):
    """Bullets-fired count using game-accurate overspill on the
    shield-breaking bullet, then `ceil(hits / accuracy)`. Mirrors
    analyze_ettk.bullets_for_milestone."""
    import math as _math
    if damage <= 0 or pellets <= 0 or accuracy <= 0:
        return None
    per_raw = damage * pellets
    if per_raw <= 0 or evo_mult <= 0 or non_evo_mult <= 0:
        return None
    n_s_full = _math.floor(shield_hp / (per_raw * evo_mult))
    shield_left = shield_hp - n_s_full * per_raw * evo_mult
    raw_used = shield_left / evo_mult
    raw_left = per_raw - raw_used
    overspill_health = raw_left * non_evo_mult
    n_s = n_s_full + 1
    health_remaining = max(0.0, health_hp - overspill_health)
    n_h = _math.ceil(health_remaining / (per_raw * non_evo_mult))
    hits_needed = n_s + n_h
    return _math.ceil(hits_needed / accuracy)


def fig_story(spec):
    """Story-driven t_down chart. Each entry in spec["weapons"] is one curve.

    Spec keys:
        title (str)
        outname (str): without extension; saved under output/ettk_figs/
        weapons (list): see _curve_for_entry. Plus per-entry visual keys:
            label (str): legend label (defaults to name)
            style (str): "default" | "anchor" | "highlight"
            color, linestyle, marker (optional): full overrides
        figsize (tuple, optional): default (10, 6.5)
        x_min, x_max (optional): default 30, 95
        y_min, y_max (optional): default 0.3, 5.5
        ref_lines (list of dicts, optional): additional vertical refs,
            each {"x": float_pct, "label": str, "color": str}
    """
    from matplotlib.lines import Line2D

    inputs = pd.read_csv("data/weapon_stats_for_ettk.csv")
    base_stats = {row["weapon"]: row for _, row in inputs.iterrows()}

    palette = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    # All solid lines by default — colour + marker carry the differentiation,
    # not dash patterns. Keeps the chart readable when anchors and overrides
    # also need their own stroke styles.
    default_markers = ["o", "s", "^", "D", "v", "P", "X"]

    figsize = spec.get("figsize", (10, 6.5))

    fig, ax = plt.subplots(figsize=figsize)

    # First pass: compute curves so we can auto-fit both axes to actual data.
    drawn = []
    for entry in spec["weapons"]:
        pts = _curve_for_entry(entry, base_stats)
        if not pts:
            continue
        drawn.append((entry, pts))

    palette_idx = 0
    anchor_idx = 0  # cycles markers across anchors so overlapping grey curves
                    # remain distinguishable by dot shape

    # Auto x-axis: x_min just below the leftmost drawn point (the lowest
    # a_down across the included weapons), x_max at 95 by default. Without
    # this, weapons with low a_down (Spitfire ~18%, Rampage unrevved ~20%)
    # have most of their curve clipped off the left edge.
    all_xs = [x for _entry, pts in drawn for x, _y in pts]
    if all_xs:
        auto_x_min = max(5, min(all_xs) - 2)
    else:
        auto_x_min = 30
    x_min = spec.get("x_min", int(auto_x_min))
    x_max = spec.get("x_max", 95)

    # Auto y-axis: tight padding around min/max of all drawn curves, with
    # gentle floor/ceiling. Caller can still override via spec["y_min"/"y_max"].
    all_ys = [y for _entry, pts in drawn for _x, y in pts]
    if all_ys:
        data_min, data_max = min(all_ys), max(all_ys)
        auto_y_min = max(0.3, data_min - 0.15)
        auto_y_max = data_max + 0.25
    else:
        auto_y_min, auto_y_max = 0.3, 5.5
    y_min = spec.get("y_min", round(auto_y_min, 2))
    y_max = spec.get("y_max", round(auto_y_max, 2))

    scatter_bullets = spec.get("scatter_bullets", False)
    handles = []
    for entry, pts in drawn:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]

        style = entry.get("style", "default")
        label = entry.get("label", entry["name"])

        if style == "anchor":
            color = entry.get("color", "#AAAAAA")
            ls = entry.get("linestyle", "-")
            mk = entry.get("marker",
                           default_markers[anchor_idx % len(default_markers)])
            lw = 1.4
            ms = 4.5
            face = "#BBBBBB"
            alpha = 0.85
            zorder = 3
            anchor_idx += 1
        elif style == "highlight":
            color = entry.get("color", "#CC3311")
            ls = entry.get("linestyle", "-")
            mk = entry.get("marker", "D")
            lw = 3.2
            ms = 8.5
            face = color
            alpha = 1.0
            zorder = 5
        else:
            color = entry.get("color", palette[palette_idx % len(palette)])
            ls = entry.get("linestyle", "-")
            mk = entry.get("marker", default_markers[palette_idx % len(default_markers)])
            lw = 2.8
            ms = 7.2
            face = color
            alpha = 0.95
            zorder = 4
            palette_idx += 1

        if scatter_bullets:
            # Step line for t_down (integer bullets → step function), with one
            # dot at each step transition: the t_down value at the accuracy
            # where the bullet count just changed. R-99 cycles through 16-27
            # bullets across the visible range → many dots; Wingman cycles
            # through 2-5 → few dots. Dot count = "shot complexity" of the
            # weapon at this engagement scale.
            ax.step(xs, ys, where="post", color=color, linestyle=ls,
                    linewidth=lw, alpha=alpha, zorder=zorder)
            transitions = _bullet_times_for_entry(entry, base_stats)
            if transitions:
                tx = [p[0] for p in transitions]
                ty = [p[2] for p in transitions]
                ax.scatter(tx, ty, s=ms ** 2 * 0.7, color=color,
                           edgecolor="white", linewidth=0.8,
                           marker=mk, alpha=alpha, zorder=zorder + 0.5)
            handles.append(Line2D([0], [0], color=color, linestyle=ls,
                                  marker=mk, markersize=ms, markerfacecolor=color,
                                  markeredgecolor="white", markeredgewidth=0.8,
                                  alpha=alpha, linewidth=lw, label=label))
        else:
            markevery = max(2, len(xs) // 8) if len(xs) > 8 else 2
            ax.plot(xs, ys, color=color, linestyle=ls, linewidth=lw, alpha=alpha,
                    marker=mk, markersize=ms, markerfacecolor=face,
                    markeredgecolor="white", markeredgewidth=0.9,
                    markevery=markevery, zorder=zorder)
            handles.append(Line2D([0], [0], color=color, linestyle=ls,
                                  marker=mk, markersize=ms, markerfacecolor=face,
                                  markeredgecolor="white", markeredgewidth=0.9,
                                  linewidth=lw, label=label))

    # Reference lines (optional).
    for ref in spec.get("ref_lines", []):
        rx = ref["x"]
        ax.axvline(rx, color=ref.get("color", "#888"), linestyle=":",
                   linewidth=1, alpha=0.6, zorder=1)
        ax.text(rx, y_max * 0.96, ref.get("label", ""),
                fontsize=8, color=ref.get("color", "#666"),
                ha="center", va="top",
                bbox=dict(facecolor="white", edgecolor="none",
                          boxstyle="round,pad=0.2", alpha=0.8))

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel("accuracy (%)")
    ax.set_ylabel("time to down (s)")
    ax.set_title(spec["title"])
    ax.grid(True, axis="y", alpha=0.22)
    ax.legend(handles=handles, loc="upper right", fontsize=9,
              frameon=True, facecolor="white", edgecolor="#ccc",
              borderpad=0.5, labelspacing=0.5, handlelength=2.6)

    fig.tight_layout()
    _save(fig, spec["outname"])
    plt.close(fig)
    logger.info(f"wrote {spec['outname']}")


def base_class_for(weapon, results_df=None):
    """Return the normalised class of a weapon for filtering."""
    classes = _load_weapon_classes()
    return classes.get(weapon, "")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    results = pd.read_csv(RESULTS_CSV)
    curves = pd.read_csv(CURVES_CSV)
    recs = pd.read_csv(RECS_CSV)
    objectives = pd.read_csv(OBJECTIVES_CSV)
    logger.info(f"Loaded {len(results)} weapons")
    # Narrative order: overview → paradox → deep dive → reference → recs → sidebar.
    fig6_scorecard(results, objectives)        # 01_scorecard
    fig_target_strips(results, objectives)     # 02_target_strips
    fig7_skill_metrics()                       # 03_skill_metrics
    fig4_quadrants(results)                    # 04_quadrants
    fig2_tdown_curves(results, curves)         # 05[a-h]_t_down_*
    fig2_capability_heatmap(results, curves)   # 06_capability_heatmap
    fig1_thresholds(results)                   # 07_thresholds_bar
    fig3_rebalance(results, recs)              # 08_rebalance_dumbbell
    fig5_volume_relationship(results)          # 09_fired_vs_landed
    fig_design_space()                         # 10_design_space

    # --- Per-weapon proposal overlays (one-shot posts) ---
    fig_proposal(
        "R-99 SMG",
        current_stats={"damage": 13, "mag": 27, "rpm": 1080, "pellets": 1},
        proposed_stats={"damage": 12, "mag": 30, "rpm": 1080, "pellets": 1},
        anchors=["Hemlok Breach AR", "Alternator SMG", "Wingman"],
        out_name="proposal_r99",
        subtitle="paired −1 damage / +3 mag (preserves capability, softens pro ceiling)",
    )

    # --- R-99 post: three story beats via fig_story ---
    smg_weapons = [w for w in results["weapon"]
                   if str(base_class_for(w, results)) in ("SMG", "Submachine Gun")]
    # Beat 1: SMG class as-is (intro to eTTK framework). Each dot = one shot,
    # so high-RPM weapons show dense rainfall under their line, slower-firing
    # weapons show sparser dots.
    fig_story({
        "title": "SMG: time to down",
        "outname": "story_r99_beat1_smg",
        "weapons": [{"name": w} for w in smg_weapons],
        "scatter_bullets": True,
    })
    # Beat 2: 11/29 purple-mag proposal in context of Volt. (gold-tier
    # equivalent is +5 mag across all tiers, i.e. 32 gold mag.)
    fig_story({
        "title": "R-99 proposed vs Volt",
        "outname": "story_r99_beat2_volt_context",
        "weapons": [
            {"name": "R-99 SMG", "label": "R-99 current", "style": "anchor"},
            {"name": "R-99 SMG", "label": "R-99 proposed (-2 dmg, +5 mag)",
             "overrides": {"damage": 11, "magazine_4": 32},
             "style": "highlight"},
            {"name": "Volt SMG", "label": "Volt"},
        ],
        "scatter_bullets": True,
    })
    # Beat 3: cross-class anchors including Wingman head-mode as
    # precision-reward ceiling.
    fig_story({
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
        "scatter_bullets": True,
    })

    # --- Long-range auto post: one chart per weapon, Hemlok+Volt as fixed
    # anchors so every chart shares a class-baseline reference. Each weapon
    # cycles through current vs proposed against the anchors. ARs and LMGs
    # never combine on the same chart — separate class identities.
    anchors = [
        {"name": "Hemlok Breach AR", "label": "Hemlok auto (AR baseline)",
         "style": "anchor"},
        {"name": "Volt SMG", "label": "Volt (SMG anchor)", "style": "anchor"},
    ]

    per_weapon = [
        ("flatline", "VK-47 Flatline", "Flatline",
         {"damage": 18, "magazine_4": 32}, "(-2 dmg, +3 mag)"),
        ("r301", "R-301 Carbine", "R-301",
         {"damage": 13, "magazine_4": 40}, "(-2 dmg, +9 mag)"),
        ("havoc", "HAVOC Rifle", "HAVOC",
         {"damage": 16, "magazine_4": 36}, "(-4 dmg, +4 mag)"),
        ("spitfire", "M600 Spitfire", "Spitfire",
         {"damage": 19, "magazine_4": 50}, "(-2 dmg, mag unchanged)"),
        ("lstar", "L-STAR EMG", "L-STAR",
         {"damage": 17, "magazine_4": 30}, "(-2 dmg, mag unchanged)"),
        ("rampage", "Rampage LMG", "Rampage (revved)",
         {"damage": 22, "magazine_4": 40, "rpm_4": 390}, "(-3 dmg, mag unchanged)"),
    ]

    for slug, base_name, short, overrides, change_label in per_weapon:
        # Rampage current is plotted in revved state to match the proposed line
        # (otherwise the proposed-revved sits below the current-unrevved and the
        # change reads as a buff). Same for any future weapon with a mode toggle.
        current_overrides = {"rpm_4": 390} if slug == "rampage" else None
        current_label = (f"{short} current"
                         + (" (revved)" if slug == "rampage" else ""))
        weapons = list(anchors)
        cur_entry = {"name": base_name, "label": current_label, "style": "anchor"}
        if current_overrides:
            cur_entry["overrides"] = current_overrides
        weapons.append(cur_entry)
        weapons.append({"name": base_name, "label": f"{short} proposed {change_label}",
                        "overrides": overrides, "style": "highlight"})
        fig_story({
            "title": f"{short}: current vs proposed",
            "outname": f"story_lra_{slug}",
            "weapons": weapons,
            "scatter_bullets": True,
        })

    # Final AR overview: Hemlok+Volt anchors, every proposed AR cycling.
    fig_story({
        "title": "Proposed ARs vs class anchors",
        "outname": "story_lra_overview_ar",
        "weapons": list(anchors) + [
            {"name": "VK-47 Flatline", "label": "Flatline proposed",
             "overrides": {"damage": 18, "magazine_4": 32}},
            {"name": "R-301 Carbine", "label": "R-301 proposed",
             "overrides": {"damage": 13, "magazine_4": 40}},
            {"name": "HAVOC Rifle", "label": "HAVOC proposed",
             "overrides": {"damage": 16, "magazine_4": 36}},
        ],
        "scatter_bullets": False,
    })

    # Final LMG overview: same anchors, LMG proposals only.
    fig_story({
        "title": "Proposed LMGs vs class anchors",
        "outname": "story_lra_overview_lmg",
        "weapons": list(anchors) + [
            {"name": "M600 Spitfire", "label": "Spitfire proposed",
             "overrides": {"damage": 19, "magazine_4": 50}},
            {"name": "L-STAR EMG", "label": "L-STAR proposed",
             "overrides": {"damage": 17, "magazine_4": 30}},
            {"name": "Rampage LMG", "label": "Rampage proposed (revved)",
             "overrides": {"damage": 22, "magazine_4": 40, "rpm_4": 390}},
        ],
        "scatter_bullets": False,
    })


if __name__ == "__main__":
    main()
