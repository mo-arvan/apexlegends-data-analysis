"""Find impactful plays beyond raw leverage. Five lists, each capturing a
different sense of "this play stood out":

  1. SURPRISE         realized attacker WPA minus the bin-expected WPA for
                      similar pre-event state. A play that succeeded much
                      more than the model expected.
  2. CLUTCH           attacker team had FEWER alive members than victim team
                      at the moment of the kill. The 1v3, 1v2, 2v3 wins.
  3. MULTI-KILL BURST per (game, attacker), kills summed in any rolling
                      30s window. Top players-bursts by combined WPA gain.
  4. LONG-RANGE       kill at >= 100m, sorted by leverage. Snipers.
  5. RAW LEVERAGE     reference list (same as analyze_top_wpa.py).

Output:
  output/wpa/impactful_plays.md
"""

import logging
import os
from argparse import ArgumentParser
from collections import defaultdict

import numpy as np
import pandas as pd

from analyze_top_wpa import (KILL_EVENTS, PRED_PARQUET, GAME_LIST, DAMAGE_DIR,
                              compute_wpa)

DOWN_EVENTS = "data/down_events.parquet"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OUT_MD = "output/wpa/impactful_plays.md"

LONG_RANGE_M = 100.0
BURST_WINDOW_S = 30
TOP_N = 10


def df_md(df, cols=None, max_rows=None):
    if cols is None:
        cols = list(df.columns)
    if max_rows:
        df = df.head(max_rows)
    rows = ["| " + " | ".join(str(c) for c in cols) + " |",
            "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if pd.isna(v):
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.2f}")
            else:
                cells.append(str(v))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def attach_downs_to_wpa(downs, kills, per_event_wpa):
    """For each down event, find the matching kill event (same victim,
    earliest kill at or after the down). Carry the kill's WPA leverage back
    to the down so we attribute leverage to the player who did the SKILL
    (the knock), not the player who registered the kill (sometimes a
    teammate's thirst, sometimes a Bleed Out timer expiring).
    """
    m = downs.merge(
        kills[["game_id", "event_id", "victim_hash", "gametimestamp",
               "attacker_hash", "weapon", "is_bleed_out"]],
        on=["game_id", "victim_hash"],
        suffixes=("_down", "_kill"),
    )
    m = m[m["gametimestamp_kill"] >= m["gametimestamp_down"]]
    m = m.sort_values(["game_id", "victim_hash", "gametimestamp_kill"]).drop_duplicates(
        ["game_id", "event_id_down"], keep="first"
    )
    m = m.rename(columns={"event_id_down": "down_event_id",
                          "event_id_kill": "kill_event_id",
                          "gametimestamp_down": "down_ts",
                          "gametimestamp_kill": "kill_ts",
                          "attacker_hash_down": "knock_attacker_hash",
                          "attacker_hash_kill": "kill_attacker_hash",
                          "weapon_down": "knock_weapon",
                          "weapon_kill": "kill_weapon"})
    # Attach leverage from the kill side.
    m = m.merge(
        per_event_wpa[["game_id", "event_id", "leverage", "atk_wpa", "vic_wpa",
                       "n_teams_alive", "time_in_game_s"]]
        .rename(columns={"event_id": "kill_event_id"}),
        on=["game_id", "kill_event_id"], how="left",
    )
    return m


def main():
    parser = ArgumentParser()
    parser.add_argument("--pred", default=PRED_PARQUET)
    parser.add_argument("--kills", default=KILL_EVENTS)
    parser.add_argument("--downs", default=DOWN_EVENTS)
    parser.add_argument("--damage-dir", default=DAMAGE_DIR)
    parser.add_argument("--game-list", default=GAME_LIST)
    parser.add_argument("--out-md", default=OUT_MD)
    parser.add_argument("--top-n", type=int, default=TOP_N)
    args = parser.parse_args()

    logger.info(f"Loading {args.pred}...")
    pred = pd.read_parquet(args.pred)
    pred = compute_wpa(pred).dropna(subset=["wpa_score"])
    logger.info(f"  WPA-scored rows: {len(pred):,}")

    # Per-event aggregation: one row per (game_id, event_id) with attacker
    # and victim team WPA shifts and pre-event state.
    per_event = pred.groupby(["game_id", "event_id"]).agg(
        ts=("ts", "first"),
        time_in_game_s=("time_in_game_s", "first"),
        n_teams_alive=("n_teams_alive", "first"),
    ).reset_index()

    # Attach kill-event context.
    kills = pd.read_parquet(args.kills)[
        ["game_id", "event_id", "attacker_hash", "victim_hash",
         "weapon", "distance_m"]
    ]
    per_event = per_event.merge(kills, on=["game_id", "event_id"], how="left")

    # Build name + team lookup.
    logger.info("Building player name/team lookup...")
    files = sorted(f for f in os.listdir(args.damage_dir) if f.endswith(".parquet"))
    name_team_rows = []
    in_scope_games = set(pred["game_id"])
    for f in files:
        df = pd.read_parquet(
            os.path.join(args.damage_dir, f),
            columns=["game_id", "player_hash", "player_name", "team_name"],
        )
        df = df[df["game_id"].isin(in_scope_games)]
        if not df.empty:
            name_team_rows.append(df.drop_duplicates(["game_id", "player_hash"]))
    name_team = pd.concat(name_team_rows, ignore_index=True).drop_duplicates(["game_id", "player_hash"])
    name_team_idx = name_team.set_index(["game_id", "player_hash"])

    def lookup(gid, h, col):
        try:
            return name_team_idx.loc[(gid, h), col]
        except KeyError:
            return None

    per_event["attacker_name"] = per_event.apply(
        lambda r: lookup(r["game_id"], r["attacker_hash"], "player_name"), axis=1)
    per_event["victim_name"] = per_event.apply(
        lambda r: lookup(r["game_id"], r["victim_hash"], "player_name"), axis=1)
    per_event["attacker_team"] = per_event.apply(
        lambda r: lookup(r["game_id"], r["attacker_hash"], "team_name"), axis=1)
    per_event["victim_team"] = per_event.apply(
        lambda r: lookup(r["game_id"], r["victim_hash"], "team_name"), axis=1)

    # Tournament/map metadata. Derive a per-(region, day) game number from
    # game_timestamp since some tournaments (Y6) have null game_num.
    games = pd.read_csv(args.game_list)[
        ["game_id", "tournament_full_name", "tournament_region",
         "game_map", "tournament_day", "game_num", "game_timestamp"]
    ].copy()
    games["derived_game_num"] = games.groupby(
        ["tournament_full_name", "tournament_region", "tournament_day"]
    )["game_timestamp"].rank(method="dense").astype("Int64")
    games["game_num_use"] = games["game_num"].fillna(games["derived_game_num"])
    games["game_date"] = pd.to_datetime(games["game_timestamp"], unit="s").dt.date.astype(str)
    per_event = per_event.merge(games, on="game_id", how="left")

    # Attacker / victim team state AFTER event.
    per_event = per_event.merge(
        pred[["game_id", "event_id", "team", "n_alive_team", "kills_so_far_team",
              "team_HP_sum", "wpa_score"]]
        .rename(columns={"team": "attacker_team",
                         "n_alive_team": "atk_alive_after",
                         "kills_so_far_team": "atk_kills_after",
                         "team_HP_sum": "atk_HP_after",
                         "wpa_score": "atk_wpa"}),
        on=["game_id", "event_id", "attacker_team"], how="left",
    )
    per_event = per_event.merge(
        pred[["game_id", "event_id", "team", "n_alive_team", "team_HP_sum", "wpa_score"]]
        .rename(columns={"team": "victim_team",
                         "n_alive_team": "vic_alive_after",
                         "team_HP_sum": "vic_HP_after",
                         "wpa_score": "vic_wpa"}),
        on=["game_id", "event_id", "victim_team"], how="left",
    )

    # Pre-event state: victim_team's alive count BEFORE the kill = after + 1.
    # Attacker's alive count before = after (kill didn't change attacker alive).
    per_event["atk_alive_before"] = per_event["atk_alive_after"]
    per_event["vic_alive_before"] = per_event["vic_alive_after"] + 1

    per_event["leverage"] = per_event["atk_wpa"].abs() + per_event["vic_wpa"].abs()

    def short(s, n=12):
        return str(s)[:n] if s is not None else ""

    def fmt_event(r):
        m = (r["game_map"] or "").replace("mp_rr_", "").replace(".png", "")
        t = int(r["time_in_game_s"]) if pd.notna(r["time_in_game_s"]) else 0
        gn = int(r["game_num_use"]) if pd.notna(r.get("game_num_use")) else None
        gn_s = f"G{gn}" if gn else "G?"
        region = r.get("tournament_region", "")
        date = r.get("game_date", "")
        teams = int(r["n_teams_alive"]) if pd.notna(r["n_teams_alive"]) else "?"
        return (f"{date} {region} {r['tournament_day']} {gn_s} {m} "
                f"@{t//60}:{t%60:02d} ({teams} teams alive)")

    sections = ["# Impactful Y6 plays — five lenses", ""]

    # Build down-attributed view UP FRONT so all four play-attribution lists
    # use the same player attribution.
    logger.info(f"Loading {args.downs} and attaching to kill WPA...")
    downs = pd.read_parquet(args.downs)
    downs = downs[downs["game_id"].isin(in_scope_games)]
    full_kills = pd.read_parquet(args.kills)
    down_view = attach_downs_to_wpa(downs, full_kills, per_event)
    down_view["knock_attacker_name"] = down_view.apply(
        lambda r: lookup(r["game_id"], r["knock_attacker_hash"], "player_name"), axis=1)
    down_view["knock_attacker_team"] = down_view.apply(
        lambda r: lookup(r["game_id"], r["knock_attacker_hash"], "team_name"), axis=1)
    down_view["victim_name"] = down_view.apply(
        lambda r: lookup(r["game_id"], r["victim_hash"], "player_name"), axis=1)
    down_view["victim_team"] = down_view.apply(
        lambda r: lookup(r["game_id"], r["victim_hash"], "team_name"), axis=1)
    down_view = down_view.merge(games, on="game_id", how="left")
    # Attach attacker/victim team alive counts AT THE KILL EVENT (closest
    # available state snapshot). For state at down moment, alive counts are
    # the same unless a teammate was eliminated between the down and the kill.
    state_cols = per_event[["game_id", "event_id",
                             "atk_alive_after", "vic_alive_after",
                             "atk_alive_before", "vic_alive_before",
                             "atk_HP_after", "vic_HP_after"]].rename(
        columns={"event_id": "kill_event_id"})
    down_view = down_view.merge(state_cols, on=["game_id", "kill_event_id"], how="left")

    # ---- 1. SURPRISE — using DOWN events for actor attribution ----
    # Bin DOWNS by (atk_alive_before, vic_alive_before, n_teams_alive bucket)
    # and compute mean leverage per bin. Surprise = actual - bin mean.
    dv = down_view.dropna(subset=["leverage", "atk_alive_before",
                                   "vic_alive_before"]).copy()
    dv["nta_bin"] = pd.cut(dv["n_teams_alive"], bins=[-1, 5, 10, 14, 18, 21],
                            labels=["1-5", "6-10", "11-14", "15-18", "19-20"])
    bin_mean = dv.groupby(
        ["atk_alive_before", "vic_alive_before", "nta_bin"], observed=True
    )["leverage"].mean().reset_index().rename(columns={"leverage": "expected_leverage"})
    dv = dv.merge(bin_mean, on=["atk_alive_before", "vic_alive_before", "nta_bin"], how="left")
    dv["surprise"] = dv["leverage"] - dv["expected_leverage"]
    surprise_top = dv.sort_values("surprise", ascending=False).head(args.top_n)

    sections += [
        "## 1. SURPRISE — succeeded more than the model expected",
        "",
        "Per DOWN event (the actual play moment, attributed to the knocker). "
        "Realized leverage minus the average leverage across all downs with "
        "similar pre-event state (attacker alive count, victim alive count, "
        "teams-alive bucket). Top entries outperformed the expected swing by "
        "the largest margin.",
        "",
        df_md(pd.DataFrame([
            {"#": i + 1,
             "where": fmt_event(r),
             "attacker": f"{r['knock_attacker_name']} ({r['knock_attacker_team']})",
             "victim": f"{r['victim_name']} ({r['victim_team']})",
             "atk_v_vic_alive": f"{int(r['atk_alive_before'])} v {int(r['vic_alive_before'])}",
             "knock_weapon": r["knock_weapon"],
             "actual_lev": r["leverage"],
             "expected_lev": r["expected_leverage"],
             "surprise": r["surprise"]}
            for i, (_, r) in enumerate(surprise_top.iterrows())
        ])),
        "",
    ]

    # ---- 2. CLUTCH — using DOWN events for actor attribution ----
    clutch = dv[dv["atk_alive_before"] < dv["vic_alive_before"]]
    clutch_top = clutch.sort_values("leverage", ascending=False).head(args.top_n)
    sections += [
        "## 2. CLUTCH — attacker outnumbered, won the trade",
        "",
        f"Per DOWN event (the actual play). Knocker's team had fewer alive "
        f"members than the victim's team at the moment. {len(clutch):,} "
        f"qualifying downs; top by leverage.",
        "",
        df_md(pd.DataFrame([
            {"#": i + 1,
             "where": fmt_event(r),
             "attacker": f"{r['knock_attacker_name']} ({r['knock_attacker_team']})",
             "victim": f"{r['victim_name']} ({r['victim_team']})",
             "atk_v_vic_alive": f"{int(r['atk_alive_before'])} v {int(r['vic_alive_before'])}",
             "knock_weapon": r["knock_weapon"],
             "atk_HP_sum": r["atk_HP_after"],
             "leverage": r["leverage"]}
            for i, (_, r) in enumerate(clutch_top.iterrows())
        ])),
        "",
    ]

    # ---- 3. MULTI-KNOCK BURSTS (per attacker player, 30s window — using DOWNS) ----
    dv_sorted = down_view.dropna(subset=["knock_attacker_hash", "leverage"]).sort_values(
        ["game_id", "knock_attacker_hash", "down_ts"]
    )
    burst_rows = []
    for (gid, ah), g in dv_sorted.groupby(["game_id", "knock_attacker_hash"]):
        if pd.isna(ah) or len(g) < 2:
            continue
        ts_arr = g["down_ts"].values
        wpa_arr = g["leverage"].fillna(0).values  # use total leverage per kill
        for i in range(len(g)):
            j = i
            while j > 0 and ts_arr[i] - ts_arr[j - 1] <= BURST_WINDOW_S:
                j -= 1
            count = i - j + 1
            if count < 2:
                continue
            window = g.iloc[j:i + 1]
            last = window.iloc[-1]
            burst_rows.append({
                "game_id": gid,
                "attacker_hash": ah,
                "attacker_name": last["knock_attacker_name"],
                "attacker_team": last["knock_attacker_team"],
                "ts_start": int(ts_arr[j]),
                "ts_end": int(ts_arr[i]),
                "knocks_in_window": count,
                "burst_wpa": float(wpa_arr[j:i + 1].sum()),
                "weapons": ", ".join(window["knock_weapon"].dropna().unique()[:3]),
                "tournament_day": last["tournament_day"],
                "tournament_region": last.get("tournament_region", ""),
                "game_map": last["game_map"],
                "game_num_use": last.get("game_num_use", None),
                "game_date": last.get("game_date", ""),
                "n_teams_alive": last["n_teams_alive"],
                "time_in_game_s": last["time_in_game_s"],
            })
    bursts = pd.DataFrame(burst_rows)
    if not bursts.empty:
        bursts = bursts.sort_values("knocks_in_window", ascending=False)
        bursts = bursts.drop_duplicates(["game_id", "attacker_hash"], keep="first")
        bursts = bursts.sort_values("burst_wpa", ascending=False)
    bursts_top = bursts.head(args.top_n)
    sections += [
        f"## 3. MULTI-KNOCK BURSTS — single player, {BURST_WINDOW_S}s window",
        "",
        f"Now using DOWN events (the actual skill moments), not kill events. "
        f"Per (game, knocker), longest knock streak inside any rolling "
        f"{BURST_WINDOW_S}-second window. Sorted by total leverage across the streak. "
        f"Weapons are the WEAPONS THAT CAUSED THE KNOCKS, not the (often-Bleed-Out) "
        f"finishers.",
        "",
        df_md(pd.DataFrame([
            {"#": i + 1,
             "where": fmt_event(r),
             "player": f"{r['attacker_name']} ({r['attacker_team']})",
             "knocks_in_window": int(r["knocks_in_window"]),
             "knock_weapons": r["weapons"],
             "burst_wpa": r["burst_wpa"]}
            for i, (_, r) in enumerate(bursts_top.iterrows())
        ])),
        "",
    ]

    # ---- 4. LONG-RANGE (using DOWN events for the actual long-range hit) ----
    long_d = down_view[
        (down_view["distance_m"] >= LONG_RANGE_M)
        & (down_view["leverage"].notna())
    ]
    long_top = long_d.sort_values("leverage", ascending=False).head(args.top_n)
    sections += [
        f"## 4. LONG-RANGE EXECUTION — knocks at >= {LONG_RANGE_M:.0f}m",
        "",
        f"Now using DOWN events. {len(long_d):,} long-range knocks in the test "
        "set. The KNOCK weapon and KNOCK distance are shown (the actual hit "
        "that did the work, not whatever later registered the kill).",
        "",
        df_md(pd.DataFrame([
            {"#": i + 1,
             "where": fmt_event(r),
             "attacker": f"{r['knock_attacker_name']} ({r['knock_attacker_team']})",
             "victim": f"{r['victim_name']} ({r['victim_team']})",
             "knock_weapon": r["knock_weapon"],
             "distance_m": r["distance_m"],
             "leverage": r["leverage"]}
            for i, (_, r) in enumerate(long_top.iterrows())
        ])),
        "",
    ]

    # ---- 5. RAW LEVERAGE (reference) ----
    raw_top = per_event.sort_values("leverage", ascending=False).head(args.top_n)
    sections += [
        "## 5. RAW LEVERAGE (reference)",
        "",
        "Largest absolute swings in expected score. Same as `top_events.md`. "
        "Mostly final-ring eliminations — pivotal MOMENTS, not necessarily "
        "remarkable PLAYS.",
        "",
        df_md(pd.DataFrame([
            {"#": i + 1,
             "where": fmt_event(r),
             "attacker": f"{r['attacker_name']} ({r['attacker_team']})",
             "victim": f"{r['victim_name']} ({r['victim_team']})",
             "weapon": r["weapon"],
             "leverage": r["leverage"]}
            for i, (_, r) in enumerate(raw_top.iterrows())
        ])),
        "",
    ]

    sections += [
        "## How to read these lists",
        "",
        "- **SURPRISE** is the most novel: it asks which events outperformed the "
        "model's prior expectation. A 1v3 win where the attacker was given <10% "
        "chance of escaping the trade rises to the top here.",
        "- **CLUTCH** is a hard-filter version of SURPRISE focused on the alive-"
        "count disadvantage axis. Easier to verify ('they were 1v3 and they won').",
        "- **MULTI-KILL BURSTS** is player-centric, not team-centric. The carry play.",
        "- **LONG-RANGE** highlights snipers who decided fights from outside the "
        "knock zone.",
        "- **RAW LEVERAGE** is the original list: high-stakes moments. Use it for "
        "'these games were decided here,' not 'these are highlight plays.'",
    ]

    os.makedirs(os.path.dirname(args.out_md), exist_ok=True)
    with open(args.out_md, "w") as fh:
        fh.write("\n".join(sections) + "\n")
    logger.info(f"Wrote {args.out_md}")


if __name__ == "__main__":
    main()
