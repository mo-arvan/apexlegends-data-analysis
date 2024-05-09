import logging

import numpy as np
import streamlit as st
import altair as alt

import src.data_helper as data_helper
import src.streamtlit_helper as streamlit_helper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

st.set_page_config(
    page_title="ALGS Fights Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        # 'Get Help': 'https://www.extremelycoolapp.com/help',
        # 'Report a bug': "https://www.extremelycoolapp.com/bug",
        # 'About': "# This is a header. This is an *extremely* cool app!"
    }
)


def get_player_ranking(input_df, minimum_damage, top_k):
    higher_than_threshold_data = input_df.loc[
        damage_events_filtered_df["damage_sum"] >= minimum_damage]

    player_ranking_data = damage_events_filtered_df[["player_name", "team_name", "input", "hit_count", "damage_sum"]]

    player_hit_count = player_ranking_data.groupby(["player_name", "team_name", "input"]).agg(
        total_fights=("hit_count", "count"),
    ).reset_index()

    high_hit_count_players = player_ranking_data.loc[player_ranking_data["damage_sum"] >= minimum_damage]

    high_hit_count_players_ranking = high_hit_count_players.groupby(["player_name", "team_name", "input"]).agg(
        high_hit_count=("hit_count", "count"),
    ).reset_index()

    high_hit_count_players_ranking = high_hit_count_players_ranking.merge(player_hit_count, on=[
        "player_name",
        "team_name",
        "input"
    ], how="inner")

    high_hit_count_players_ranking["high_hit_count_percentage"] = 100 * high_hit_count_players_ranking[
        "high_hit_count"] / \
                                                                  high_hit_count_players_ranking["total_fights"]

    high_hit_count_players_ranking["high_hit_count_percentage"] = high_hit_count_players_ranking[
        "high_hit_count_percentage"].apply(
        lambda x: np.round(x, 2))

    high_hit_count_players_ranking["high_hit_count_percentage_str"] = high_hit_count_players_ranking[
        "high_hit_count_percentage"].apply(
        lambda x: f"{x:.2f} %")

    high_hit_count_players_ranking = high_hit_count_players_ranking.sort_values(by=["high_hit_count",
                                                                                    "high_hit_count_percentage"
                                                                                    ],
                                                                                ascending=False)
    input_to_emoji_dict = {
        "Mouse & Keyboard": "💻",
        "Controller": "🎮",
    }
    keyboard_emoji = "⌨️"
    controller_emoji = "🎮"

    high_hit_count_players_ranking["input"] = high_hit_count_players_ranking["input"].apply(
        lambda x: input_to_emoji_dict.get(x, "?"))

    high_hit_count_players_ranking["high_hit_count_rank"] = range(1, len(high_hit_count_players_ranking) + 1)

    high_hit_count_players_ranking_head = high_hit_count_players_ranking.head(top_k)

    height = 800
    if top_k > 20:
        height = 800 + (top_k - 20) * 30

    title = alt.TitleParams(f"Top Players Ranked based on # High Damage Encounters",
                            subtitle=[f"Minimum Damage Dealt: {minimum_damage}, color is input type.",
                                      ""],
                            subtitleColor="#FFFFFF",
                            fontSize=24,
                            subtitleFontSize=16,
                            anchor='start',
                            dx=50,
                            dy=25)

    rank_bar_plot = alt.Chart(high_hit_count_players_ranking_head,
                              title=title).mark_bar().encode(
        x=alt.X("high_hit_count:Q",
                # axis=alt.Axis(title="Count"),
                axis=None,
                scale=alt.Scale(zero=False)),
        y=alt.Y("player_name:N",
                axis=alt.Axis(title='',
                              offset=35,
                              ticks=False,
                              domain=False
                              ),
                sort=None,
                ),
        color=alt.Color("input:N",
                        legend=None,
                        # scale=alt.Scale(scheme='yelloworangered')
                        # use category10 for colors
                        scale=alt.Scale(scheme='dark2')

                        ),
        tooltip=alt.Tooltip(
            [
                'player_name',
                # "weapon_name",
                # "damage_sum:Q",
                # 'shots',
                # 'hits',
                # "accuracy",
                # "high_accuracy_count",
                # "total_fights",
                # "tournament_full_name",
                # "tournament_region",
                # "tournament_day",
                # "game_title"
            ]),
    ).properties(
        # width=100,
        width=600,

        height=height,
    )

    # rank_bar_plot = rank_bar_plot.interactive()

    #
    bar_plot_input_text = rank_bar_plot.mark_text(align="center",
                                                  baseline="middle",
                                                  # color="white",
                                                  fontStyle="bold",
                                                  fontSize=20,
                                                  dx=-20).encode(
        x=alt.value(-5),
        text="input:N",
        # text="damage_dealt:Q",
        # color=alt.value("black")
    )

    bar_plot_count_text = rank_bar_plot.mark_text(align="center",
                                                  baseline="middle",
                                                  # color="white",
                                                  fontStyle="bold",
                                                  fontSize=20,
                                                  dx=-20).encode(
        x=alt.X("high_hit_count:Q"),
        # y=alt.Y("player_name:N"),
        text="high_hit_count:Q",
        color=alt.value("white")
    )

    bar_plot_percentage_text = rank_bar_plot.mark_text(align="center",
                                                       baseline="middle",
                                                       # color="white",
                                                       fontStyle="bold",
                                                       fontSize=12,
                                                       dx=0).encode(
        x=alt.value(35),
        # text="high_hit_count_percentage:Q",
        # add percentage sign
        text=alt.Text("high_hit_count_percentage_str:N",
                      # format=".2 %",
                      ),

        color=alt.value("white")
    ).transform_calculate(label='datum.text + " %"')

    # bottom_title = alt.TitleParams(
    #     ['This is a fake footer.', 'If you want multiple lines,', 'you can put them in a list.'],
    #     baseline='bottom',
    #     orient='bottom',
    #     anchor='end',
    #     fontWeight='normal',
    #     fontSize=10
    # )

    # + bar_plot_count_text
    rank_bar_plot = rank_bar_plot + bar_plot_input_text
    rank_bar_plot = rank_bar_plot + bar_plot_count_text
    rank_bar_plot = rank_bar_plot + bar_plot_percentage_text

    rank_bar_plot = alt.concat(rank_bar_plot).properties(
        title=alt.TitleParams(
            ['Source: apexlegends-data-analysis.streamlit.app'],
            baseline='bottom',
            orient='bottom',
            anchor='start',
            fontWeight='normal',
            fontSize=10,
            dx=15,
            dy=15
        ),
    )

    # rank_bar_plot = alt.concat(rank_bar_plot).properties(
    #     title=alt.TitleParams(
    #         ['This is a fake footer.', 'If you want multiple lines,', 'you can put them in a list.'],
    #         baseline='bottom',
    #         orient='bottom',
    #         anchor='end',
    #         fontWeight='normal',
    #         fontSize=10
    #     ))
    # rank_bar_plot = alt.concat([rank_bar_plot, bottom_attribution])

    selected_df = high_hit_count_players_ranking.rename(columns={"player_name": "Name",
                                                                 "team_name": "Team",
                                                                 "input": "Input",
                                                                 "high_hit_count_rank": "Rank",
                                                                 "high_hit_count": "Count",
                                                                 "total_fights": "Total",
                                                                 "high_hit_count_percentage": "Percentage"})

    selected_df = selected_df[["Rank", "Name", "Input", "Count", "Total", "Percentage"]]

    response = (rank_bar_plot, selected_df, higher_than_threshold_data)

    return response


def get_team_ranking():
    team_ranking_data = high_hit_count_players_ranking.groupby("team_name").agg(
        high_hit_count=("high_hit_count", "sum"),
        total_fights=("total_fights", "sum"),
    ).reset_index()

    team_ranking_data["high_hit_count_percentage"] = 100 * team_ranking_data["high_hit_count"] / team_ranking_data[
        "total_fights"]

    team_ranking_data["high_hit_count_percentage"] = team_ranking_data["high_hit_count_percentage"].apply(
        lambda x: np.round(x, 2))

    team_ranking_data = team_ranking_data.sort_values(by="high_hit_count", ascending=False)

    team_ranking_data["rank"] = range(1, len(team_ranking_data) + 1)

    team_ranking_data.rename(columns={"team_name": "Name",
                                      "rank": "Rank",
                                      "high_hit_count": "Count",
                                      "total_fights": "Total",
                                      "high_hit_count_percentage": "Percentage"}, inplace=True)


# with st.spinner("Loading data..."):
algs_games_df = data_helper.get_algs_games()
gun_stats_df, _, _ = data_helper.get_gun_stats()


damage_events_filtered_df, selected_tournament, selected_region, selected_days, selected_weapons = streamlit_helper.common_filters(
    algs_games_df, gun_stats_df)

hit_count_median = int(damage_events_filtered_df["hit_count"].median())

# median_damage_dealt = int(damage_events_filtered_df["damage_sum"].median())

minimum_damage = st.sidebar.number_input("Minimum Damage Dealt",
                                         min_value=1,
                                         max_value=1000,
                                         value=100,
                                         key="high_hit_count")

top_k = st.sidebar.number_input("Top K Players",
                                min_value=1,
                                max_value=100,
                                value=20,
                                key="top_k")

hash_to_input_dict = data_helper.get_hash_to_input_dict()

damage_events_filtered_df["input"] = damage_events_filtered_df["player_hash"].apply(
    lambda x: hash_to_input_dict.get(x, "?"))

filter_input_nan = damage_events_filtered_df[damage_events_filtered_df["input"].isna()]

filter_input_nan_grouped = filter_input_nan.groupby(["player_name", "player_hash", "team_name"]).agg(
    count=("player_name", "count"),
).reset_index()

filter_input_nan_grouped = filter_input_nan_grouped.sort_values(by="count", ascending=False)

print(filter_input_nan_grouped[["player_name", "team_name", "count"]][:10])

bar_plot, high_hit_count_players_ranking, higher_than_threshold_data = get_player_ranking(damage_events_filtered_df,
                                                                                          minimum_damage,
                                                                                          top_k)

st.altair_chart(bar_plot, use_container_width=True)

#
# st.write("Team Rankings")
#
# st.dataframe(team_ranking_data[["Rank", "Name", "Count", "Total", "Percentage"]]
#              , hide_index=True, use_container_width=True)

expander = st.expander(label='Raw Data')
expander.dataframe(higher_than_threshold_data[[
    "player_name",
    "input",
    "team_name",
    "tournament_full_name",
    "tournament_day",
    "game_title",
    "game_map",
    "event_start_time",
    "weapon_name",
    # "class",
    "target",
    "distance_median",
    "hit_count",
    "damage_sum",
    "ammo_used",
    "distance",
    "damage",
    "event_time",
    "player_hash",
    "game_id",
]]
                   )
expander.dataframe(high_hit_count_players_ranking,
                   hide_index=True, use_container_width=True)
